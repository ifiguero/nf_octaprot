#!/usr/bin/env -S uv run --with polars --with pymzml --with matplotlib python3.12
from __future__ import annotations

import argparse
import logging
import sys
import math
from pathlib import Path
from typing import Any
from math import log10
import traceback

import polars as pl
from pymzml.run import Reader

import re
from typing import Union

import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)



SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "sample_metadata": SILVER_ROOT / "metadata",
    "replicates": SILVER_ROOT / "replicates",
}


def load_table(table_name: str) -> pl.DataFrame:
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
def get_accession(metadata_df: pl.DataFrame, accession: str, basename: str) -> str:
    df_search = (
        metadata_df.filter(pl.col("basename") == basename, pl.col('accession') == accession )
          .select("value")
    )
    if df_search.height != 1:
        return 'Not Present'

    return df_searchd.item()

def load_sample(sample_id: str) -> dict:

    df_replicate = (
        load_table("replicates")
        .filter(pl.col("id") == sample_id)
        .select("id", "organism", "source_type", "material")
    )

    if replicate.height != 1:
        fail(f"Replicate '{sample_id}' not found")

    sample = row.row(0, named=True)

    df_metadata = load_table("sample_metadata")

    sample['dia'] = get_accession(df_metadata, 'acquisition:type', sample_id )
    sample['window_size'] = get_accession(df_metadata, 'ms2:isolation_window_avg', sample_id )
    sample['instrument_name'] = get_accession(df_metadata, 'info:instrument_name', sample_id )

    return sample


def create_scan_summary_png(
    parquet_file: Union[str, Path],
    binning: str,
    title: str
) -> Path:
    if binning not in {"linear", "percentile"}:
        raise ValueError("binning must be either 'linear' or 'percentile'")

    parquet_file = Path(parquet_file)
    basename = Path(parquet_file).stem
    output_file = Path(f"{basename}.png")

    df = (
        pl.scan_parquet(parquet_file)
        .collect()
        .sort(["ms_level", "scan_number"])
    )

    if df.is_empty():
        raise ValueError(
            f"No rows found for basename={basename!r} in {parquet_file}"
        )

    # ------------------------------------------------------------------
    # LINEAR HISTOGRAM
    # ------------------------------------------------------------------
    if binning == "linear":
        ibin_columns = [
            c for c in df.columns
            if c.startswith("ibin_")
        ]

        if not ibin_columns:
            raise ValueError(
                "No columns matching 'ibin_*' were found in the Parquet file."
            )

        def ibin_value(column: str) -> float:
            return float(column[len("ibin_"):])

        ibin_columns.sort(key=ibin_value)

        # Sum counts and count zeros for every ms_level.
        agg_exprs = []

        for column in ibin_columns:
            agg_exprs.append(
                pl.col(column).sum().alias(column)
            )
            agg_exprs.append(
                (pl.col(column) == 0).sum().alias(f"__zero__{column}")
            )

        aggregated = (
            df.group_by("ms_level")
            .agg(agg_exprs)
            .sort("ms_level")
        )

        ms_levels = aggregated["ms_level"].to_list()
        x = np.array([ibin_value(c) for c in ibin_columns], dtype=float)

        fig, ax = plt.subplots(figsize=(13, 8))

        for row in aggregated.iter_rows(named=True):
            ms_level = row["ms_level"]

            y = np.array(
                [row[c] for c in ibin_columns],
                dtype=float,
            )

            # A logarithmic axis cannot display zero.
            y_plot = np.where(y > 0, y, np.nan)

            zero_counts = np.array(
                [row[f"__zero__{c}"] for c in ibin_columns],
                dtype=int,
            )


            ax.plot(
                x,
                y_plot,
                marker="o",
                markersize=3,
                linewidth=1.5,
                label=f"MS {ms_level} "
            )

        ax.set_yscale("log")
        ax.set_xlabel("Intensity bin")
        ax.set_ylabel("Summed peak count")
        ax.set_title(
            f"Scan histogram summary — {basename}"
            f"{title}"
            f"Log binning"
        )
        ax.grid(True, which="both", alpha=0.25)
        ax.legend()
        fig.tight_layout()

    # ------------------------------------------------------------------
    # PERCENTILE HISTOGRAM
    # ------------------------------------------------------------------
    else:
        percentile_columns = [
            c for c in df.columns
            if re.fullmatch(r"p-?\d+(?:\.\d+)?", c)
        ]

        if not percentile_columns:
            raise ValueError(
                "No percentile columns matching 'p<value>' were found."
            )

        def percentile_value(column: str) -> float:
            return float(column[1:])

        percentile_columns.sort(key=percentile_value)

        x = np.array(
            [percentile_value(c) for c in percentile_columns],
            dtype=float,
        )

        # Compute Q1, median, Q3 across scans for each ms_level.
        aggregation = []
        for column in percentile_columns:
            aggregation.extend(
                [
                    pl.col(column).min().alias(
                        f"__min__{column}"
                    ),
                    pl.col(column).quantile(0.25).alias(
                        f"__q1__{column}"
                    ),
                    pl.col(column).median().alias(
                        f"__median__{column}"
                    ),
                    pl.col(column).quantile(0.75).alias(
                        f"__q3__{column}"
                    ),
                    pl.col(column).max().alias(
                        f"__max__{column}"
                    ),
                ]
            )

        aggregated = (
            df.group_by("ms_level")
            .agg(aggregation)
            .sort("ms_level")
        )

        fig, ax = plt.subplots(figsize=(13, 8))

        for row in aggregated.iter_rows(named=True):
            ms_level = row["ms_level"]

            vmin = np.array(
                [row[f"__min__{c}"] for c in percentile_columns],
                dtype=float,
            )
            q1 = np.array(
                [row[f"__q1__{c}"] for c in percentile_columns],
                dtype=float,
            )
            median = np.array(
                [row[f"__median__{c}"] for c in percentile_columns],
                dtype=float,
            )
            q3 = np.array(
                [row[f"__q3__{c}"] for c in percentile_columns],
                dtype=float,
            )
            vmax = np.array(
                [row[f"__max__{c}"] for c in percentile_columns],
                dtype=float,
            )

            # Main series: median.
            line = ax.plot(
                x,
                median,
                linewidth=2,
                label=f"MS {ms_level}",
            )[0]

            color = line.get_color()

            # Quartiles.
            ax.plot(
                x,
                q1,
                linestyle="--",
                linewidth=1,
                color=color,
                alpha=0.8,
            )
            ax.plot(
                x,
                q3,
                linestyle="--",
                linewidth=1,
                color=color,
                alpha=0.8,
            )

            # Minimum / maximum.
            ax.plot(
                x,
                vmin,
                linestyle=":",
                linewidth=1,
                color=color,
                alpha=0.7,
            )
            ax.plot(
                x,
                vmax,
                linestyle=":",
                linewidth=1,
                color=color,
                alpha=0.7,
            )

            # Optional: retain the IQR shading.
            ax.fill_between(
                x,
                q1,
                q3,
                color=color,
                alpha=0.15,
            )

            # Optional: show the full min/max envelope.
            ax.fill_between(
                x,
                vmin,
                vmax,
                color=color,
                alpha=0.05,
            )

            ax.set_xlabel("Percentile")
            ax.set_ylabel("log10(intensity)")
            ax.set_title(
                f"Scan percentile summary — {basename}"
                f"{title}"
                f"Median and IQR across scans"
            )
            ax.grid(True, alpha=0.25)
            ax.legend()

            fig.tight_layout()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_file, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return output_file

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract mzML scan metadata into a Parquet file."
    )

    parser.add_argument(
        "parquet_file",
        type=Path,
        help="Input parquet file",
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

    if not args.parquet_file.is_file():
        parser.error(f"File does not exist: {args.parquet_file}")

    try:
        sample_info = load_sample(args.parquet_file.basename)
        title = f"""
        Sample: ({sample_info['organism']}, {sample_info['source_type']}, {sample_info['material']})
        Instrument: {sample_info['instrument_name']}. Mode: {sample_info['dia']} ({sample_info['window_size']}),)
        """
        create_scan_summary_png(
            parquet_file=args.parquet_file,
            binning=args.binning,
            title=title
        )
    except Exception as exc:
        logger.error("%s", exc)
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
