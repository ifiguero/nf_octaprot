#!/usr/bin/env -S uv run --with polars python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

import polars as pl


def parse_time_output(path: Path) -> dict[str, any]:
    """Parses a GNU `time -v` output file into a dictionary."""
    data = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line.startswith("Command being timed:"):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    data["command"] = match.group(1)
            elif line.startswith("User time (seconds):"):
                data["user_time_seconds"] = float(line.split(":")[-1].strip())
            elif line.startswith("System time (seconds):"):
                data["system_time_seconds"] = float(line.split(":")[-1].strip())
            elif line.startswith("File system inputs:"):
                data["io_in"] = int(line.split(":")[-1].strip())
            elif line.startswith("File system output:"):
                data["io_out"] = float(line.split(":")[-1].strip())
            elif line.startswith("Percent of CPU this job got:"):
                val = line.split(":")[-1].strip().replace("%", "")
                data["cpu_percent"] = float(val)
            elif line.startswith("Elapsed (wall clock) time"):
                data["elapsed_time_str"] = line.split("):")[-1].strip()
            elif line.startswith("Maximum resident set size"):
                data["max_rss_kb"] = int(line.split(":")[-1].strip())
            elif line.startswith("Exit status:"):
                data["exit_status"] = int(line.split(":")[-1].strip())

    return data


def process(replicate_id: str, filename: Path) -> pl.DataFrame:
    """Processes the raw time file and returns a strongly-typed DataFrame."""
    parsed_data = parse_time_output(filename)
    parsed_data["replicate_id"] = replicate_id

    # Define strict schema for Parquet joining purposes
    schema = {
        "replicate_id": pl.String,
        "command": pl.String,
        "user_time_seconds": pl.Float64,
        "system_time_seconds": pl.Float64,
        "cpu_percent": pl.Float64,
        "elapsed_time_str": pl.String,
        "io_in": pl.Int64,
        "io_out": pl.Int64,
        "max_rss_kb": pl.Int64,
        "exit_status": pl.Int64,
    }

    # Ensure all schema keys exist (fill with None if missing)
    for col in schema:
        if col not in parsed_data:
            parsed_data[col] = None

    # Create DataFrame and ensure standard column order
    df = pl.DataFrame([parsed_data], schema=schema).select(list(schema.keys()))

    if df.is_empty():
        raise ValueError(f"No valid time metrics found in {filename}")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse GNU time outputs into canonical benchmarking Parquet."
    )

    parser.add_argument("id", help="Sample identifier (e.g., PXD010357_20160304)")
    parser.add_argument("filename", type=Path, help="Input time log file")

    args = parser.parse_args()

    if not args.filename.is_file():
        parser.error(f"Time metrics file does not exist: {args.filename}")

    metrics_df = process(args.id, args.filename)

    metrics_df.write_parquet(f"{args.id}.parquet", compression="zstd")



if __name__ == "__main__":
    main()
