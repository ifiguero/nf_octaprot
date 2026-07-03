#!/usr/bin/env -S uv run --with polars python3.12

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)

def human_readable(bytes_size) -> str:
    if bytes_size == "" or bytes_size is None:
        return ""

    try:
        size = int(bytes_size)
    except (ValueError, TypeError):
        return str(bytes_size)

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def main() -> int:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name}  <input.parquet>")

    parquet_path = Path(sys.argv[1])

    if not parquet_path.exists():
        fail(f"Input file not found: {parquet_path}")

    try:
        df = pl.read_parquet(parquet_path)
    except Exception as exc:
        fail(f"Failed to read parquet: {exc}")

    required_columns = {"id","repository_id","remote_path","size_bytes",}

    missing = required_columns - set(df.columns)

    if missing:
        fail( "Missing required columns: " + ", ".join(sorted(missing)))

    repository_ids = ( df.select("repository_id").unique().to_series().to_list() )

    if len(repository_ids) != 1:
        fail( f"Expected exactly one repository_id but found {len(repository_ids)}" )

    repository_id = repository_ids[0]

    samples_df = (
        df.filter(pl.col("id").is_not_null())
        .with_columns(
            [
                pl.lit(None).cast(pl.String).alias("organism"),
                pl.lit(None).cast(pl.String).alias("source_type"),
                pl.lit(None).cast(pl.String).alias("material"),
                pl.lit(None).cast(pl.String).alias("condition"),
                (pl.lit("sample-") + (pl.int_range(pl.len()) + 1).cast(pl.String).str.zfill(4)).alias("sample_group"),
                pl.col("size_bytes")
                  .map_elements(human_readable, return_dtype=pl.String)
                  .alias("size"),
            ]
        )
        .sort("remote_path")
        .select(
            ["id", "organism", "source_type", "material", "condition", "sample_group", "size_bytes", "size", "remote_path"]
        )
    )
    other_df = (
        df.filter(pl.col("id").is_null())
        .with_columns(
            [
                pl.col("size_bytes")
                  .map_elements(human_readable, return_dtype=pl.String)
                  .alias("size"),
            ])
        .sort("remote_path")
        .select([ "size", "size_bytes", "remote_path" ])
    )

    samples_csv = Path(
        f"samples_{repository_id}.csv"
    )

    other_csv = Path(
        f"other_{repository_id}.csv"
    )

    samples_df.write_csv(samples_csv)
    other_df.write_csv(other_csv)

    print(f"Wrote {samples_df.height} rows to {samples_csv}")
    print(f"Wrote {other_df.height} rows to  {other_csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
