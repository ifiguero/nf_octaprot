#!/usr/bin/env -S uv run --with polars python3

from __future__ import annotations

from pathlib import Path
import sys

import polars as pl


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    if len(sys.argv) != 2:
        fail(f"Usage: {Path(sys.argv[0]).name} <replicates.parquet>")

    parquet_path = Path(sys.argv[1])

    if not parquet_path.exists():
        fail(f"Input file does not exist: {parquet_path}")

    try:
        df = pl.read_parquet(parquet_path)
    except Exception as exc:
        fail(f"Failed to read Parquet: {exc}")

    if "id" not in df.columns:
        fail("Missing required column: id")

    ids = (
        df.select("id")
        .drop_nulls()
        .get_column("id")
        .to_list()
    )

    if not ids:
        fail("No replicate ids found")

    for replicate_id in ids:
        print(replicate_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
