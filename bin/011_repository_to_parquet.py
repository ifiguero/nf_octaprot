#!/usr/bin/env -S uv run --with polars python3.12

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import polars as pl

import sys



@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    nullable: bool = True

REPOSITORY_SCHEMA = {
    "table": "repositories",
    "description": "Repository inventory",
    "columns": [
        Column("id", "string", False),
        Column("url", "string", False),
        Column("doi", "string", False)
    ],
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def polars_dtype(dtype: str) -> pl.DataType:
    mapping = {
        "string": pl.Utf8,
    }

    try:
        return mapping[dtype]
    except KeyError:
        fail(f"Unsupported schema dtype: {dtype}")


def main() -> int:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name} <repositories.csv>")

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        fail(f"Input file does not exist: {csv_path}")

    columns = REPOSITORY_SCHEMA["columns"]

    required_columns = [c.name for c in columns]
    non_nullable_columns = [c.name for c in columns if not c.nullable]

    # Read only schema-defined columns. Extra columns are ignored.
    try:
        df = pl.read_csv(csv_path)
    except Exception as exc:
        fail(f"Failed to read CSV: {exc}")

    missing_columns = sorted(set(required_columns) - set(df.columns))
    if missing_columns:
        fail(f"Missing required columns: {', '.join(missing_columns)}")

    df = df.select(required_columns)

    # Enforce schema types.
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

    # Reject nulls in any schema-defined column.
    null_counts = (
        df.select(
            [pl.col(col).null_count().alias(col) for col in required_columns]
        )
        .row(0, named=True)
    )

    columns_with_nulls = [
        col for col, count in null_counts.items() if count > 0
    ]
    if columns_with_nulls:
        fail(
            "Null values found in required columns: "
            + ", ".join(columns_with_nulls)
        )

    # Reject empty strings in non-nullable columns.
    for col in non_nullable_columns:
        empty_count = (
            df.filter(pl.col(col).str.strip_chars() == "")
            .height
        )
        if empty_count > 0:
            fail(f"Empty values found in required column: {col}")

    # Reject duplicate rows.
    if df.height != df.unique().height:
        fail("Duplicate rows detected")

    # Reject duplicate repository IDs.
    if df.height != df.unique(subset=["id"]).height:
        duplicate_ids = (
            df.group_by("id")
            .len()
            .filter(pl.col("len") > 1)
            .get_column("id")
            .to_list()
        )
        fail(f"Duplicate repository ids detected: {duplicate_ids}")
    # Validate all required non-nullable columns contain values.
    for col in non_nullable_columns:
        if (
            df.filter(pl.col(col).is_null())
            .height
            > 0
        ):
            fail(f"Missing values found in required column: {col}")

    # All validation passed. Only now write parquet files.
    schema = {
        c.name: polars_dtype(c.dtype)
        for c in columns
    }

    for row in df.iter_rows(named=True):
        repository_id = row["id"]

        parquet_df = pl.DataFrame(
            [row],
            schema=schema,
        )

        parquet_df.write_parquet(f"repo_{repository_id}.parquet")

    return 0


if __name__ == "__main__":
    sys.exit(main())
