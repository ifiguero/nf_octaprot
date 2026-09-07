#!/usr/bin/env -S uv run --with polars --with matplotlib python3.12

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import traceback
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database locations
# ---------------------------------------------------------------------------

SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "spec_intensity": SILVER_ROOT / "spec_intensity",
    "sample_metadata": SILVER_ROOT / "sample_metadata",
    "replicates": SILVER_ROOT / "replicates",
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def load_table(table_name: str) -> pl.DataFrame:
    """
    Load all parquet files belonging to one Silver table.
    """
    parquet_root = TABLE_TO_PARQUET[table_name]

    if not parquet_root.exists():
        return pl.DataFrame()

    parquet_files = sorted(parquet_root.rglob("*.parquet"))

    if not parquet_files:
        return pl.DataFrame()

    return pl.concat(
        [pl.read_parquet(path) for path in parquet_files],
        how="diagonal_relaxed",
    )


def get_replicates() -> pl.DataFrame:
    """
    Return all replicate records required for plotting.

    Expected columns in the replicates table:
        id
        organism
        source_type
        material
    """
    df = load_table("replicates")

    if df.is_empty():
        raise RuntimeError("Replicates table is empty or not present.")

    required = {"id"}
    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            f"Replicates table is missing required columns: {sorted(missing)}"
        )

    return df


def get_instrument_metadata() -> pl.DataFrame:
    """
    Extract instrument_name from the long-form sample_metadata table.

    The metadata structure used by the supplied code is:

        basename
        accession
        value

    Instrument name is stored under:
        info:instrument_name
    """
    df = load_table("sample_metadata")

    if df.is_empty():
        logger.warning("Sample metadata table is empty.")
        return pl.DataFrame(
            schema={
                "basename": pl.String,
                "instrument_name": pl.String,
            }
        )

    required = {"basename", "accession", "value"}
    missing = required - set(df.columns)

    if missing:
        raise RuntimeError(
            "Sample metadata table is missing required columns: "
            f"{sorted(missing)}"
        )

    return (
        df.filter(pl.col("accession") == "info:instrument_name")
        .select(
            pl.col("basename"),
            pl.col("value").alias("instrument_name"),
        )
        .unique(subset=["basename"], keep="first")
    )


def get_sample_records() -> pl.DataFrame:
    """
    Join all replicates with their instrument name.

    Missing/null/empty instrument names are mapped to 'not present'.
    """
    replicates = get_replicates()
    instruments = get_instrument_metadata()

    samples = (
        replicates
        .select("id")
        .unique()
        .join(
            instruments,
            left_on="id",
            right_on="basename",
            how="left",
        )
        .with_columns(
            pl.when(
                pl.col("instrument_name").is_null()
                | (pl.col("instrument_name").cast(pl.String).str.strip_chars() == "")
            )
            .then(pl.lit("not present"))
            .otherwise(pl.col("instrument_name").cast(pl.String))
            .alias("instrument_name")
        )
        .sort("instrument_name", "id")
    )

    return samples


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def create_combined_profile_plot(ms_level: int, output_file: Path,) -> Path:
    samples = get_sample_records()
    scans = load_table("spec_intensity")

    if samples.is_empty():
        raise RuntimeError("No replicates found.")

    logger.info(f"Found {samples.height} replicate(s) in the replicates table.")

    instruments = (
        samples
        .get_column("instrument_name")
        .unique()
        .sort()
        .to_list()
    )

    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    instrument_colors = {
        instrument: color_cycle[index % len(color_cycle)]
        for index, instrument in enumerate(instruments)
    }
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(15, 9))

    instrument_sample_counts: dict[str, int] = {
        instrument: 0
        for instrument in instruments
    }

    successful_profiles = 0
    total_scans = 0

    intensity = np.array([], dtype=float)
    ibin_columns = []
    n_bins = 100
    min_log_intensity = 1.0
    max_log_intensity = 9.0
    bin_width = (max_log_intensity - min_log_intensity) / n_bins

    ibin_columns.append("under")
    intensity = np.append(intensity, min_log_intensity-1)

    for index in range(n_bins):
        baseint = 1+(bin_width * (index+0.5))
        ibin_columns.append(f"ibin_{baseint:.1f}")
        intensity = np.append(intensity, baseint)

    ibin_columns.append("over")
    intensity = np.append(intensity, max_log_intensity+1)

    # Keep the actual legend handles separately.
    legend_handles = {}

    for sample in samples.iter_rows(named=True):
        sample_id = sample["id"]
        instrument = sample["instrument_name"]
        df = scans.filter(pl.col("ms_level") == ms_level, basename=sample_id)

        median = np.array(
            [
                df.get_column(column).median()
                for column in ibin_columns
            ],
            dtype=float,
        )

        q1 = np.array(
            [
                df.get_column(column)
                .quantile(0.25)
            for column in ibin_columns
            ],
            dtype=float,
        )

        q3 = np.array(
            [
                df.get_column(column)
                .quantile(0.75)
                for column in ibin_columns
            ],
            dtype=float,
        )

        color = instrument_colors[instrument]

        # --------------------------------------------------------------
        # Median
        # --------------------------------------------------------------

        line = ax.plot(
            intensity,
            median,
            color=color,
            linewidth=1.5,
            alpha=0.8,
        )[0]

        # --------------------------------------------------------------
        # IQR shadow
        #
        # 5% transparency = alpha=0.05
        # --------------------------------------------------------------

        ax.fill_between(
            intensity,
            q1,
            q3,
            color=color,
            alpha=0.05,
        )

        # Use the first successful series for an instrument as its
        # representative legend handle.
        if instrument not in legend_handles:
            legend_handles[instrument] = line

        instrument_sample_counts[instrument] += 1
        successful_profiles += 1
        total_scans += df.height

    if successful_profiles == 0:
        plt.close(fig)
        raise RuntimeError(
            f"No replicate profiles could be plotted for MS level {ms_level}."
        )

    # ------------------------------------------------------------------
    # Axes
    # ------------------------------------------------------------------
    ax.set_yscale("log")
    ax.set_xlabel("Log10(Intensity) ")
    ax.set_ylabel("counts/scan")

    # ------------------------------------------------------------------
    # Legend
    #
    # One entry per instrument, with the number of successfully plotted
    # samples in that instrument cluster.
    # ------------------------------------------------------------------

    legend_instruments = [
        instrument
        for instrument in instruments
        if instrument in legend_handles
    ]

    legend_labels = [
        f"{instrument} ({instrument_sample_counts[instrument]} samples)"
        for instrument in instruments if instrument in legend_handles
    ]

    ax.legend(
        [
            legend_handles[instrument]
            for instrument in legend_instruments
        ],
        legend_labels,
        title="Instrument",
        loc="best",
    )

    ax.grid(
        True,
        which="both",
        alpha=0.25,
    )

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------

    total_samples = samples.height
    plotted_samples = successful_profiles

    ax.set_title(
        f"Expected intensity profile — MS {ms_level}\n"
        f"{plotted_samples} of {total_samples} samples plotted; "
        f"{total_scans:,} scans"
    )

    fig.tight_layout()

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    logger.info(
        "Saved figure: %s",
        output_file,
    )

    return output_file


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a combined scan-intensity profile for all replicates, "
            "clustered by instrument."
        )
    )

    parser.add_argument(
        "lvl",
        type=int,
        nargs="?",
        default=2,
        choices=(1, 2),
        help=(
            "MS level used to filter scans "
            "(default: 2)"
        ),
    )



    args = parser.parse_args()

    output_file = Path(f"scan_intensity_profiles_ms{args.lvl}.png")

    try:
        create_combined_profile_plot(
            ms_level=args.lvl,
            output_file=output_file,
        )

    except Exception as exc:
        logger.error("%s", exc)
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
