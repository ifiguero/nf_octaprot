#!/usr/bin/env -S uv run --with polars python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import polars as pl


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


def main() -> int:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name} <replicates.csv>")

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        fail(f"Input file does not exist: {csv_path}")

    columns = REPLICATES_SCHEMA["columns"]

    required_columns = [c.name for c in columns]
    non_nullable_columns = [c.name for c in columns if not c.nullable]

    try:
        df = pl.read_csv(csv_path)
    except Exception as exc:
        fail(f"Failed to read CSV: {exc}")

    missing_columns = sorted(set(required_columns) - set(df.columns))
    if missing_columns:
        fail(f"Missing required columns: {', '.join(missing_columns)}")

    df = df.select(required_columns)

    try:
        df = df.cast(
            {
                c.name: polars_dtype(c.dtype)
                for c in columns
            },
            strict=True,
        )
    except Exception as exc:
        fail(f"Schema validation failed: {exc}")

    if df.height == 0:
        fail("CSV contains no rows")

    null_counts = (
        df.select(
            [pl.col(col).null_count().alias(col) for col in required_columns]
        )
        .row(0, named=True)
    )

    columns_with_nulls = [
        col for col, count in null_counts.items()
        if count > 0
    ]

    if columns_with_nulls:
        fail(
            "Null values found in required columns: "
            + ", ".join(columns_with_nulls)
        )

    for col in non_nullable_columns:
        if df.filter(pl.col(col).is_null()).height > 0:
            fail(f"Missing values found in required column: {col}")

        if df.schema[col] == pl.Utf8:
            empty_count = (
                df.filter(pl.col(col).str.strip_chars() == "")
                .height
            )
            if empty_count > 0:
                fail(f"Empty values found in required column: {col}")

    if df.height != df.unique(subset=["id"]).height:
        duplicate_ids = (
            df.group_by("id")
            .len()
            .filter(pl.col("len") > 1)
            .get_column("id")
            .to_list()
        )
        fail(f"Duplicate replicate ids detected: {duplicate_ids}")

    output_path = csv_path.with_suffix(".parquet")

    df.write_parquet(output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
