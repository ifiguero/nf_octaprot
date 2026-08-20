#!/usr/bin/env -S uv run --with polars --with pymzml python3.12

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any
from math import log10
import traceback

import polars as pl
from pymzml.run import Reader


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def summarize_spectra(reader: Reader, basename: str, binning: str = "linear",) -> list[dict[str, Any]]:
    if binning not in {"linear", "percentile"}:
        raise ValueError(f"Unsupported binning mode {binning!r}; expected 'linear' or 'percentile'")

    rows: list[dict[str, Any]] = []
    total_spectra = 0

    n_bins = 100
    min_log_intensity = 1.0
    max_log_intensity = 9.0
    bin_width = (max_log_intensity - min_log_intensity) / n_bins

    for spectrum in reader:
        total_spectra += 1

        try:
            ms_level = int(spectrum.ms_level)
        except (TypeError, ValueError, AttributeError):
            continue

        scan_number = spectrum.ID

        try:
            intensities = [log10(1.0 + float(x))  for x in spectrum.i]
        except Exception:
            intensities = []

        try:
            mz_values = [float(x) for x in spectrum.mz]
            min_mz = min(mz_values) if mz_values else None
            max_mz = max(mz_values) if mz_values else None
        except Exception:
            min_mz = None
            max_mz = None

        row: dict[str, Any] = {
            "basename": basename,
            "scan_number": int(scan_number),
            "ms_level": ms_level,
            "peaks": len(intensities),
            "min_mz": min_mz,
            "max_mz": max_mz,
            "min_int": min(intensities),
            "max_int": max(intensities)

        }

        if binning == "linear":
            counts = [0] * n_bins

            row["under"] = 0
            row["over"] = 0

            for intensity in intensities:
                if intensity < min_log_intensity:
                    row["under"] += 1
                elif intensity >= max_log_intensity:
                    row["over"] += 1
                else:
                    index = int( (intensity - min_log_intensity) / bin_width )
                    index = min(index, n_bins - 1)
                    counts[index] += 1

            for index, count in enumerate(counts):
                baseint = 1+(bin_width * (index+0.5))
                row[f"ibin_{baseint:.1f}"] = count

        else:

            len_intensities = len(intensities)
            percentile_values = [i * (100.0 / n_bins) for i in range(n_bins + 1)]

            if  len_intensities > 1:
                sorted_intensities = sorted(intensities)
                constant = (len_intensities-1) / 100.0

                for percentile in percentile_values:
                    position = constant * percentile
                    index = int(position)
                    fraction = position - index
                    if index+1 < len_intensities:
                        row[f"p{percentile:.2f}"] = float((1 - fraction) * sorted_intensities[index] + fraction * sorted_intensities[index + 1])
                    else:
                        row[f"p{percentile:.2f}"] = float(sorted_intensities[len_intensities-1])
            else:
                for percentile in percentile_values:
                    row[f"p{percentile:.2f}"] = float(intensities[0])

        rows.append(row)

    logger.info(
        "Read %d scans",
        total_spectra,
    )

    return rows



def process(input_path: Path, binning: str) -> Path:
    name = input_path.name

    output = name

    for suffix in (".mzML.gz", ".mzml.gz", ".mzML", ".mzml"):
        if name.endswith(suffix):
            output = name[:-len(suffix)]
            break

    basename = output
    output_path = f"{basename}.parquet"

    logger.info(
        "Reading %s for %s binning of MS spectra metadata",
        input_path,
        binning,
    )

    reader = Reader(str(input_path))

    rows = summarize_spectra(
        reader=reader,
        basename=basename,
        binning=binning,
    )

    sample_keys = rows[0].keys() if rows else ["basename", "scan_number", "ms_level", "min_mz", "max_mz", "min_int", "max_int"]
    schema = {}
    for key in sample_keys:
        if key in ["basename"]:
            schema[key] = pl.String
        elif key in ["scan_number", "ms_level"]:
            schema[key] = pl.Int32
        elif key in ["min_mz", "max_mz", "min_int", "max_int"]:
            schema[key] = pl.Float32
        elif binning=='linear':
            schema[key] = pl.Int32
        elif binning=='percentile':
            schema[key] = pl.Float32

    df = pl.DataFrame(
        rows,
        schema=schema,
        strict=False
    ).sort(["basename", "scan_number"]).unique(subset=["basename", "scan_number"], keep="first", maintain_order=True)

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
        "binning",
        type=str,
        nargs="?",
        default="linear",
        choices=("linear", "percentile"),
        help="Binning method, linear log10-intensity or Percentile based (default: linear)",
    )

    args = parser.parse_args()

    if not args.mzml_file.is_file():
        parser.error(f"File does not exist: {args.mzml_file}")

    try:
        process(
            input_path=args.mzml_file,
            binning=args.binning,
        )
    except Exception as exc:
        logger.error("%s", exc)
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
