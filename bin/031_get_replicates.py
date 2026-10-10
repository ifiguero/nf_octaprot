#!/usr/bin/env -S uv run --with polars python3

from __future__ import annotations

import os
from pathlib import Path
import sys

import polars as pl


SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "sample_metadata": SILVER_ROOT / "sample_metadata",
    "replicates": SILVER_ROOT / "replicates",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


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


def get_acquisition(
    metadata_df: pl.DataFrame,
    replicate_id: str,
) -> str | None:
    if metadata_df.is_empty():
        return None

    required_columns = {"replicate_id", "accession", "value"}
    if not required_columns.issubset(metadata_df.columns):
        return None

    result = (
        metadata_df
        .filter(
            (pl.col("replicate_id") == replicate_id)
            & (pl.col("accession") == "acquisition:type")
        )
        .select("value")
    )

    if result.height != 1:
        return None

    return result.item()


def main() -> int:
    if len(sys.argv) != 3:
        fail(
            f"Usage: {Path(sys.argv[0]).name} [dia|dda] <replicates.parquet>"
        )

    mode = sys.argv[1].lower()
    parquet_path = Path(sys.argv[2])

    if mode not in {"dia", "dda"}:
        fail("Mode must be 'dia' or 'dda'")

    if not parquet_path.is_file():
        fail(f"Input file does not exist: {parquet_path}")

    try:
        df = pl.read_parquet(parquet_path)
    except Exception as exc:
        fail(f"Failed to read Parquet: {exc}")

    if "replicate_id" not in df.columns:
        fail("Missing required column: replicate_id")

    try:
        metadata_df = load_table("sample_metadata")
    except Exception as exc:
        fail(f"Failed to load sample_metadata: {exc}")

    if metadata_df.is_empty():
        fail("sample_metadata table is empty or does not exist")

    if not {"replicate_id", "accession", "value"}.issubset(
        metadata_df.columns
    ):
        fail(
            "sample_metadata must contain replicate_id, accession, and value"
        )

    ids = (
        df.select("replicate_id")
        .drop_nulls()
        .unique()
        .get_column("replicate_id")
        .to_list()
    )

    if not ids:
        fail("No replicate ids found")

    for replicate_id in ids:
        acquisition = get_acquisition(metadata_df, replicate_id)

        if acquisition is not None and acquisition.strip().lower() == mode:
            print(replicate_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
