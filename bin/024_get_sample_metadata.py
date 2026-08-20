#!/usr/bin/env -S uv run --with polars --with pymzml python3.12

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from math import log10
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

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
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def add_value(
    rows: list[dict[str, Any]],
    basename: str,
    accession: str,
    name: str,
    value: Any,
    group: str,
) -> None:
    rows.append(
        {
            "basename": basename,
            "accession": accession,
            "name": name,
            "value": scalar(value),
            "group": group,
        }
    )


def cv_name(reader: Reader, accession: str, fallback: str | None = None) -> str:
    try:
        value = reader.OT[accession]
        if isinstance(value, str):
            return value
    except Exception:
        pass

    return fallback or accession


def extract_cv_params(
    element: ET.Element | None,
    reader: Reader,
    basename: str,
    group: str,
    rows: list[dict[str, Any]],
) -> None:
    if element is None:
        return

    for cv in element.iter(f"{NS}cvParam"):
        accession = cv.get("accession")
        if not accession:
            continue

        name = cv.get("name") or cv_name(reader, accession)
        value = cv.get("value")

        if value is None:
            value = cv.get("name")

        add_value(
            rows,
            basename,
            accession,
            name,
            value,
            group,
        )


def extract_user_params(
    element: ET.Element | None,
    basename: str,
    group: str,
    rows: list[dict[str, Any]],
) -> None:
    if element is None:
        return

    for param in element.iter(f"{NS}userParam"):
        name = param.get("name") or "user_param"
        value = param.get("value")

        add_value(
            rows,
            basename,
            f"user:{group}:{name}",
            name,
            value,
            group,
        )


def extract_element_metadata(
    element: ET.Element | None,
    reader: Reader,
    basename: str,
    group: str,
    rows: list[dict[str, Any]],
) -> None:
    extract_cv_params(element, reader, basename, group, rows)
    extract_user_params(element, basename, group, rows)


def add_reader_info(
    reader: Reader,
    basename: str,
    rows: list[dict[str, Any]],
) -> None:
    excluded = {
        "file_description_element",
        "instrument_configuration_list_element",
        "data_processing_list_element",
        "run_element",
    }

    for key in sorted(reader.info):
        if key in excluded:
            continue

        value = reader.info.get(key)

        if not isinstance(value, (str, int, float, bool)) and value is not None:
            continue

        add_value(
            rows,
            basename,
            f"info:{key}",
            key,
            value,
            "file_metadata",
        )


def add_stat(
    rows: list[dict[str, Any]],
    basename: str,
    prefix: str,
    values: list[float],
    group: str = "summary",
) -> None:
    if not values:
        return

    add_value(
        rows,
        basename,
        f"{group}:{prefix}_min",
        f"{prefix}_min",
        round(min(values),3),
        group,
    )

    add_value(
        rows,
        basename,
        f"{group}:{prefix}_max",
        f"{prefix}_max",
        round(max(values),3),
        group,
    )

    add_value(
        rows,
        basename,
        f"{group}:{prefix}_avg",
        f"{prefix}_avg",
        round(statistics.fmean(values),3),
        group,
    )

    if len(values) > 1:
        add_value(
            rows,
            basename,
            f"{group}:{prefix}_std",
            f"{prefix}_std",
            round(statistics.stdev(values),3),
            group,
        )


def summarize_spectra(
    reader: Reader,
    basename: str,
    rows: list[dict[str, Any]],
) -> None:
    total_count = 0
    ms1_count = 0
    ms2_count = 0

    scan_times: list[float] = []
    total_ion_current: list[float] = []
    ms1_tic: list[float] = []
    ms2_tic: list[float] = []

    ms1_mz_low: list[float] = []
    ms1_mz_high: list[float] = []
    ms2_mz_low: list[float] = []
    ms2_mz_high: list[float] = []
    ms1_mz_window: list[float] = []
    ms2_mz_window: list[float] = []

    precursor_mz: list[float] = []
    collision_energy: list[float] = []

    isolation_targets: list[float] = []
    isolation_lower: list[float] = []
    isolation_upper: list[float] = []
    isolation_window: list[float] = []


    peak_count: list[float] = []
    ms1_peak_count: list[float] = []
    ms2_peak_count: list[float] = []
    peak_intensity_min: list[float] = []
    peak_intensity_max: list[float] = []
    peak_intensity_avg: list[float] = []
    peak_intensity_median: list[float] = []


    mz_delta_min: list[float] = []
    mz_delta_max: list[float] = []
    mz_delta_avg: list[float] = []
    mz_delta_median: list[float] = []

    for spectrum in reader:
        total_count += 1

        try:
            ms_level = int(spectrum.ms_level)
        except Exception:
            ms_level = None

        try:
            scan_time = numeric(spectrum.scan_time_in_minutes())
        except Exception:
            scan_time = None

        if scan_time is not None:
            scan_times.append(scan_time)


        try:
            intensities = [log10(1+float(x)) for x in spectrum.i]
        except Exception:
            intensities = []

        if intensities:
            peak_count.append(float(len(intensities)))
            peak_intensity_min.append(min(intensities))
            peak_intensity_max.append(max(intensities))
            peak_intensity_avg.append(statistics.fmean(intensities))
            peak_intensity_median.append(statistics.median(intensities))
        else:
            peak_count.append(0.0)

        try:
            mz_values = sorted(float(x) for x in spectrum.mz)
        except Exception:
            mz_values = []

        if len(mz_values) > 1:
            delta_mz = [high - low for low, high in zip(mz_values, mz_values[1:]) ]

            mz_delta_min.append(min(delta_mz))
            mz_delta_max.append(max(delta_mz))
            mz_delta_avg.append(statistics.fmean(delta_mz))
            mz_delta_median.append(statistics.median(delta_mz))

        cv_params: dict[str, str | None] = {}

        for cv in spectrum.element.iter(f"{NS}cvParam"):
            accession = cv.get("accession")
            if accession:
                cv_params[accession] = cv.get("value")

        tic = numeric(cv_params.get("MS:1000285"))

        if tic is not None:
            total_ion_current.append(tic)

        mz_low = numeric(cv_params.get("MS:1000501"))
        mz_high = numeric(cv_params.get("MS:1000500"))



        if ms_level == 1:
            ms1_count += 1
            ms1_peak_count.append(float(len(intensities)))

            if tic is not None:
                ms1_tic.append(tic)

            if mz_low is not None:
                ms1_mz_low.append(mz_low)

            if mz_high is not None:
                ms1_mz_high.append(mz_high)

            if mz_low is not None and mz_high is not None:
                ms1_mz_window.append(mz_high - mz_low)

        elif ms_level == 2:
            ms2_count += 1
            ms2_peak_count.append(float(len(intensities)))

            if tic is not None:
                ms2_tic.append(tic)

            if mz_low is not None:
                ms2_mz_low.append(mz_low)

            if mz_high is not None:
                ms2_mz_high.append(mz_high)

            if mz_low is not None and mz_high is not None:
                ms2_mz_window.append(mz_high - mz_low)


            precursor_list = spectrum.element.find(f"{NS}precursorList")

            if precursor_list is not None:
                for precursor in precursor_list.findall(f"{NS}precursor"):
                    isolation_up, isolation_down = None, None
                    for cv in precursor.iter(f"{NS}cvParam"):
                        accession = cv.get("accession")
                        value = numeric(cv.get("value"))

                        if accession == "MS:1000827" and value is not None:
                            isolation_targets.append(value)

                        elif accession == "MS:1000828" and value is not None:
                            isolation_down = value
                            isolation_lower.append(value)

                        elif accession == "MS:1000829" and value is not None:
                            isolation_up = value
                            isolation_upper.append(value)

                        elif accession == "MS:1000744" and value is not None:
                            precursor_mz.append(value)

                        elif accession == "MS:1000045" and value is not None:
                            collision_energy.append(value)

                    if isolation_down is not None and isolation_up is not None:
                        isolation_window.append(isolation_up + isolation_down)

    add_value(
        rows,
        basename,
        "summary:spectrum_count",
        "total_spectrum_count",
        total_count,
        "summary",
    )

    add_value(
        rows,
        basename,
        "ms1:spectrum_count",
        "ms1_spectrum_count",
        ms1_count,
        "ms1",
    )

    add_value(
        rows,
        basename,
        "ms2:spectrum_count",
        "ms2_spectrum_count",
        ms2_count,
        "ms2",
    )

    if scan_times:
        add_value(
            rows,
            basename,
            "summary:first_scan_time_minutes",
            "first_scan_time_minutes",
            round(min(scan_times),3),
            "summary",
        )

        add_value(
            rows,
            basename,
            "summary:last_scan_time_minutes",
            "last_scan_time_minutes",
            round(max(scan_times),3),
            "summary",
        )

        run_time = max(scan_times) - min(scan_times)

        add_value(
            rows,
            basename,
            "summary:total_run_time_seconds",
            "total_run_time_seconds",
            round(run_time*60, 3),
            "summary",
        )


    add_value(
        rows,
        basename,
        "ms1:mz_low_min",
        "ms1_mz_low_min",
        round(min(ms1_mz_low),3),
        "ms1",
    )
    add_value(
        rows,
        basename,
        "ms1:mz_high_max",
        "ms1_mz_high_max",
        round(max(ms1_mz_high),3),
        "ms1",
    )
    add_value(
        rows,
        basename,
        "ms1:mz_window_avg",
        "ms1_mz_window_avg",
        round(statistics.fmean(ms1_mz_window),3),
        "ms1",
    )

    add_value(
        rows,
        basename,
        "ms2:mz_low_min",
        "ms2_mz_low_min",
        round(min(ms2_mz_low),3),
        "ms2",
    )
    add_value(
        rows,
        basename,
        "ms2:mz_high_max",
        "ms2_mz_high_max",
        round(max(ms2_mz_high),3),
        "ms2",
    )
    add_value(
        rows,
        basename,
        "ms2:mz_window_avg",
        "ms2_mz_window_avg",
        round(statistics.fmean(ms2_mz_window),3),
        "ms2",
    )
    add_value(
        rows,
        basename,
        "ms2:isolation_lower_offset_min",
        "ms2_isolation_lower_offset_min",
        round(min(isolation_lower),3),
        "ms2",
    )
    add_value(
        rows,
        basename,
        "ms2:isolation_upper_offset_max",
        "ms2_isolation_upper_offset_max",
        round(max(isolation_upper),3),
        "ms2",
    )



    add_stat(rows, basename, "tic", total_ion_current, 'summary')
    add_stat(rows, basename, "tic", ms1_tic, 'ms1')
    add_stat(rows, basename, "tic", ms2_tic, 'ms2')

    add_stat(rows, basename, "precursor_mz", precursor_mz, 'summary')
    add_stat(rows, basename, "collision_energy", collision_energy, 'ms2')

    add_stat(rows, basename, "isolation_target_mz", isolation_targets, 'ms2')
    add_stat(rows, basename, "isolation_window", isolation_window, 'ms2')

    add_stat(rows, basename, "peak_count", peak_count, 'summary')
    add_stat(rows, basename, "peak_count", ms1_peak_count, 'ms1')
    add_stat(rows, basename, "peak_count", ms2_peak_count, 'ms2')

    add_value(
        rows,
        basename,
        "summary:peak_separation_min",
        "peak_separation_min",
        round(min(mz_delta_min),3),
        "summary",
    )
    add_value(
        rows,
        basename,
        "summary:peak_separation_max",
        "peak_separation_max",
        round(max(mz_delta_max),3),
        "summary",
    )

    add_value(
        rows,
        basename,
        "summary:peak_separation_avg",
        "peak_separation_avg",
        round(statistics.fmean(mz_delta_avg),3),
        "summary",
    )

    add_value(
        rows,
        basename,
        "summary:peak_separation_median",
        "peak_separation_median",
        round(statistics.fmean(mz_delta_median),3),
        "summary",
    )


    add_value(
        rows,
        basename,
        "summary:peak_intensity_min",
        "peak_intensity_min",
        round(min(peak_intensity_min),3),
        "summary",
    )
    add_value(
        rows,
        basename,
        "summary:peak_intensity_max",
        "peak_intensity_max",
        round(max(peak_intensity_max),3),
        "summary",
    )

    add_value(
        rows,
        basename,
        "summary:peak_intensity_avg",
        "peak_intensity_avg",
        round(statistics.fmean(peak_intensity_avg),3),
        "summary",
    )

    add_value(
        rows,
        basename,
        "summary:peak_intensity_median",
        "peak_intensity_median",
        round(statistics.fmean(peak_intensity_median),3),
        "summary",
    )


    if len(isolation_window) > 0:
        if len(isolation_window) >= 10 and statistics.fmean(isolation_window) >= 4:
            mode = "DIA"
        else:
            mode = "DDA"

        add_value(
            rows,
            basename,
            "acquisition:type",
            "Heuristic adquisition",
            mode,
            "acquisition",
        )


def process(input_path: Path) -> Path:
    name = input_path.name

    output = name

    for suffix in (".mzML.gz", ".mzml.gz", ".mzML", ".mzml"):
        if name.endswith(suffix):
            output = name[:-len(suffix)]
            break

    basename = output
    output_path = f"{basename}.parquet"

    logger.info("Reading %s", input_path)

    reader = Reader(str(input_path))
    rows: list[dict[str, Any]] = []

    add_reader_info(
        reader,
        basename,
        rows,
    )

    extract_element_metadata(
        reader.info.get("file_description_element"),
        reader,
        basename,
        "file_description",
        rows,
    )

    extract_element_metadata(
        reader.info.get("instrument_configuration_list_element"),
        reader,
        basename,
        "instrument",
        rows,
    )

    extract_element_metadata(
        reader.info.get("data_processing_list_element"),
        reader,
        basename,
        "data_processing",
        rows,
    )

    extract_element_metadata(
        reader.info.get("run_element"),
        reader,
        basename,
        "run",
        rows,
    )

    summarize_spectra(
        reader,
        basename,
        rows,
    )

    df = pl.DataFrame(
        rows,
        schema={
            "basename": pl.String,
            "accession": pl.String,
            "name": pl.String,
            "value": pl.String,
            "group": pl.String,
        },
        strict=False,
    ).sort(["basename", "group", "accession"]).unique(subset=["basename", "accession"], keep="first", maintain_order=True)

    df.write_parquet(
        output_path,
        compression="zstd",
    )

    logger.info(
        "Wrote %d metadata rows to %s",
        df.height,
        output_path,
    )

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mzml_file",
        type=Path,
    )

    args = parser.parse_args()

    if not args.mzml_file.exists():
        parser.error(f"File does not exist: {args.mzml_file}")

    try:
        process(args.mzml_file)
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
