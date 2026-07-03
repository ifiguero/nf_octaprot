#!/usr/bin/env -S uv run --with polars python3.12

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import os

import polars as pl


TARGET_BYTES = 10 * 1024**3

SILVER_ROOT = Path(os.environ["SILVER_DIR"])
FILES_GLOB = SILVER_ROOT / "files" / "*.parquet"


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    nullable: bool = True


REPLICATES_SCHEMA = {
    "table": "replicates",
    "description": "Input dataset",
    "columns": [
        Column("id", "string", False),
        Column("organism", "string", False),
        Column("source_type", "string", False),
        Column("material", "string", False),
        Column("condition", "string", False),
        Column("sample_group", "string", False),
    ],
}


STRATIFY_COLUMNS = [
    "organism",
    "source_type",
    "material",
    "condition",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def polars_dtype(dtype: str) -> pl.DataType:
    mapping = {
        "string": pl.Utf8,
        "int32": pl.Int32,
    }

    try:
        return mapping[dtype]
    except KeyError:
        fail(f"Unsupported schema dtype: {dtype}")


def load_files_table() -> pl.DataFrame:
    if not SILVER_ROOT.exists():
        fail(f"Silver mount not available: {SILVER_ROOT}")

    files = sorted((SILVER_ROOT / "files").glob("*.parquet"))

    if not files:
        fail(f"No parquet files found under {SILVER_ROOT / 'files'}")

    return (
        pl.scan_parquet(str(FILES_GLOB))
        .filter(pl.col("id").is_not_null() & (pl.col("id").str.strip_chars() != ""))
        .select(["id", "size_bytes"])
        .collect()
    )



def assign_splits(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        pl.concat_str(
            [pl.col(c).fill_null("NULL") for c in STRATIFY_COLUMNS],
            separator="|",
        ).alias("_stratum")
    )

    split_sizes: list[int] = [0]
    rows: list[dict] = []

    for stratum_df in df.partition_by("_stratum", maintain_order=False):
        stratum_df = (
            stratum_df
            .sample(fraction=1.0, shuffle=True, seed=42)
            .sort("size_bytes", descending=True)
        )

        for row in stratum_df.iter_rows(named=True):
            row_size = int(row["size_bytes"] or 0)

            candidate = min(
                range(len(split_sizes)),
                key=lambda i: split_sizes[i],
            )

            if (
                split_sizes[candidate] > 0
                and split_sizes[candidate] + row_size > TARGET_BYTES
            ):
                split_sizes.append(0)
                candidate = len(split_sizes) - 1

            split_sizes[candidate] += row_size
            row["split_id"] = candidate
            rows.append(row)

    return pl.DataFrame(rows)


def write_outputs(df: pl.DataFrame) -> None:
    baseName = Path(sys.argv[1]).with_suffix('')
    for split_df in df.partition_by("split_id", maintain_order=True):
        split_id = int(split_df["split_id"][0])

        output = Path(f"{baseName}_{split_id:03d}.csv")

        (
            split_df
            .drop(["split_id", "_stratum"], strict=False)
            .write_csv(output)
        )

        total_bytes = int(split_df["size_bytes"].sum())

        print(
            f"Wrote {output.name}: "
            f"rows={split_df.height:,} "
            f"bytes={total_bytes:,}",
            file=sys.stderr,
        )


def main() -> int:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name} <replicates.parquet>")

    parquet_path = Path(sys.argv[1])

    if not parquet_path.exists():
        fail(f"Input file does not exist: {parquet_path}")

    try:
        replicates = pl.read_parquet(parquet_path)
    except Exception as exc:
        fail(f"Failed to read parquet: {exc}")


    files = load_files_table()

    joined = replicates.join(
        files,
        on="id",
        how="inner",
    )

    missing = replicates.height - joined.height

    if missing:
        fail(f"WARNING: {missing} replicates missing size_bytes metadata")

    if joined.height == 0:
        fail("Join produced zero rows")

    split_df = assign_splits(joined)

    write_outputs(split_df)

    return 0


if __name__ == "__main__":
    sys.exit(main())
