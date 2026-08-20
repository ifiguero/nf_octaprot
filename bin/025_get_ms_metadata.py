#!/usr/bin/env -S uv run --with polars --with pymzml python3.12

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from math import log10
import traceback

import polars as pl
from pymzml.run import Reader


NS_URI = "http://psi.hupo.org/ms/mzml"
NS = f"{{{NS_URI}}}"


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def scalar(value: Any) -> str | None:
    """Convert an arbitrary metadata value to a string or None."""
    if value is None:
        return None

    if isinstance(value, bytes):
        return value.decode(errors="replace")

    return str(value)


def metadata_rows(spectrum: Any, basename: str, scan_number: int, last_ms1_scan: int,) -> list[dict[str, Any]]:

    rows: list[dict[str, Any]] = []
    seen_accessions: set[str] = set(['MS:1000521', 'MS:1000515', 'MS:1000514', 'MS:1000574', 'MS:1000579', 'MS:1000580', 'MS:1000795'])

    for cv in spectrum.element.iter(f"{NS}cvParam"):
        accession = cv.get("accession")

        if not accession:
            continue

        if accession in seen_accessions:
            continue

        seen_accessions.add(accession)

        rows.append(
            {
                "basename": basename,
                "scan_number": scan_number,
                "accession": accession,
                "name": cv.get("name"),
                "value": scalar(cv.get("value"))
            }
        )
    if spectrum.ms_level == 2:
        rows.append(
            {
                "basename": basename,
                "scan_number": scan_number,
                "accession": 'parent:ms1',
                "name": 'Parent MS1 scan',
                "value": last_ms1_scan
            }
        )


    return rows

def summarize_spectra(
    reader: Reader,
    basename: str,
    requested_ms_level: int,
) -> list[dict[str, Any]]:
    """
    Extract metadata for spectra matching the requested MS level.
    """
    rows: list[dict[str, Any]] = []
    total_spectra = 0
    selected_spectra = 0
    last_ms1_scan = 1

    for spectrum in reader:
        total_spectra += 1

        try:
            ms_level = int(spectrum.ms_level)
        except (TypeError, ValueError, AttributeError):
            logger.warning(
                "Could not determine MS level for spectrum %d",
                spectrum_index,
            )
            continue

        scan_number = spectrum.ID

        if ms_level == 1:
            last_ms1_scan = scan_number

        if ms_level != requested_ms_level:
            continue

        selected_spectra += 1

        rows.extend(
            metadata_rows(
                spectrum=spectrum,
                basename=basename,
                scan_number=scan_number,
                last_ms1_scan=last_ms1_scan,
            )
        )

        try:
            intensities = [log10(1+float(x)) for x in spectrum.i]
        except Exception:
            intensities = []

        rows.append({
            "basename": basename,
            "scan_number": scan_number,
            "accession": "peak_count",
            "name": "Number of peaks on the scan",
            "value": len(intensities),
        })
        if len(intensities)>0:
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_intensity:min",
                "name": "Min Intensity",
                "value": round(min(intensities),3),
            })
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_intensity:max",
                "name": "Max Intensity",
                "value": round(max(intensities),3),
            })
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_intensity:avg",
                "name": "Average Intensity",
                "value": round(statistics.fmean(intensities),3),
            })
            if len(intensities)>3:
                rows.append({
                    "basename": basename,
                    "scan_number": scan_number,
                    "accession": "peak_intensity:median",
                    "name": "Median Intensity",
                    "value": round(statistics.median(intensities),3),
                })

        try:
            mz_values = sorted(float(x) for x in spectrum.mz)
        except Exception:
            mz_values = []

        delta_mz = [high - low for low, high in zip(mz_values, mz_values[1:]) ]

        if len(delta_mz)>0:
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_separation:min",
                "name": "Min Separantion of peaks",
                "value": round(min(delta_mz),3),
            })
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_separation:max",
                "name": "Max Separantion of peaks",
                "value": round(max(delta_mz),3),
            })
            rows.append({
                "basename": basename,
                "scan_number": scan_number,
                "accession": "peak_separation:avg",
                "name": "Avg Separantion of peaks",
                "value": round(statistics.fmean(delta_mz),3),
            })
            if len(delta_mz)>3:
                rows.append({
                    "basename": basename,
                    "scan_number": scan_number,
                    "accession": "peak_separation:median",
                    "name": "Median Separantion of peaks",
                    "value": round(statistics.fmean(delta_mz),3),
                })




    logger.info(
        "Read %d spectra; selected %d MS%d spectra",
        total_spectra,
        selected_spectra,
        requested_ms_level,
    )

    return rows

def process(input_path: Path, ms_level: int) -> Path:
    name = input_path.name

    output = name

    for suffix in (".mzML.gz", ".mzml.gz", ".mzML", ".mzml"):
        if name.endswith(suffix):
            output = name[:-len(suffix)]
            break

    basename = output
    output_path = f"{basename}.parquet"

    logger.info(
        "Reading %s for MS%d spectra metadata",
        input_path,
        ms_level,
    )

    reader = Reader(str(input_path))

    rows = summarize_spectra(
        reader=reader,
        basename=basename,
        requested_ms_level=ms_level,
    )

    df = pl.DataFrame(
        rows,
        schema={
            "basename": pl.String,
            "scan_number": pl.Int64,
            "accession": pl.String,
            "name": pl.String,
            "value": pl.String
        },
        strict=False
    ).sort(["basename", "scan_number", "accession"]).unique(subset=["basename", "scan_number", "accession"], keep="first", maintain_order=True)

    df.write_parquet(
        output_path,
        compression="zstd",
    )

    logger.info(
        "Wrote %d metadata rows for %d scans to %s",
        df.height,
        df.select(["basename", "scan_number"]).unique().height,
        output_path,
    )

    return output_path

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract mzML scan metadata into a Parquet file."
    )

    parser.add_argument(
        "mzml_file",
        type=Path,
        help="Input mzML or mzML.gz file",
    )

    parser.add_argument(
        "ms_level",
        type=int,
        choices=(1, 2),
        help="MS level to extract: 1 or 2",
    )

    args = parser.parse_args()

    if not args.mzml_file.is_file():
        parser.error(f"File does not exist: {args.mzml_file}")

    try:
        process(
            input_path=args.mzml_file,
            ms_level=args.ms_level,
        )
    except Exception as exc:
        logger.error("%s", exc)
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
