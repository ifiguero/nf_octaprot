#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "polars",
#     "pyarrow",
# ]
# ///

import os
from pathlib import Path
import struct
import polars as pl

BRONZE_DIR = Path(os.getenv("BRONZE_DIR", "bronze"))
SILVER_DIR = Path(os.getenv("SILVER_DIR", "silver"))
GOLD_DIR = Path(os.getenv("GOLD_DIR", "."))

# ==========================================
# GLOBAL CONFIGURATION FOR GOLD EXTENSIBILITY
# ==========================================
SAMPLE_METADATA_ACCESSIONS = [
    "acquisition:type",
    "ms2:isolation_window_avg",
    "ms2:peak_count_avg",
    "ms1:peak_count_avg",
    "ms2:spectrum_count",
    "ms1:spectrum_count",
    "summary:spectrum_count",
    "summary:total_run_time_seconds",
]

SCAN_METADATA_ACCESSIONS = [
    "MS:1000285",
    "peak_intensity:median",
    "peak_separation:median",
]


def get_gzip_sizes(replicate_id_bytes: bytes) -> tuple[int | None, int | None]:
    if isinstance(replicate_id_bytes, bytes):
        try:
            rep_str = replicate_id_bytes.decode("utf-8")
        except UnicodeDecodeError:
            rep_str = replicate_id_bytes.hex()
    else:
        rep_str = str(replicate_id_bytes)

    path = BRONZE_DIR / f"{rep_str}.mzML.gz"
    if not path.exists():
        path = BRONZE_DIR / f"{rep_str}.mzml.gz"

    if not path.exists():
        return None, None

    try:
        compressed_size = path.stat().st_size
        if compressed_size < 4:
            return compressed_size, None

        with open(path, "rb") as f:
            f.seek(-4, 2)
            data = f.read(4)
            if len(data) < 4:
                return compressed_size, None
            uncompressed_size = struct.unpack("<I", data)[0]
        return compressed_size, uncompressed_size
    except Exception as e:
        print(f"{path} exception: {e}")
        return None, None


def load_core_silver() -> pl.DataFrame:
    replicates_path = SILVER_DIR / "replicates"
    files_path = SILVER_DIR / "files"

    replicates = pl.read_parquet(replicates_path if replicates_path.is_dir() else f"{replicates_path}.parquet")
    files = pl.read_parquet(files_path if files_path.is_dir() else f"{files_path}.parquet")

    core = replicates.join(
        files.select(["replicate_id", "repository_id", pl.col("size_bytes").alias("raw_size_bytes")]),
        on="replicate_id",
        how="left"
    )

    rep_ids = core["replicate_id"].to_list()
    compressed_sizes = []
    normalized_sizes = []

    for rid in rep_ids:
        comp, norm = get_gzip_sizes(rid)
        compressed_sizes.append(comp)
        normalized_sizes.append(norm)

    core = core.with_columns([
        pl.Series("compressed_size_bytes", compressed_sizes, dtype=pl.Int64),
        pl.Series("normalized_size_bytes", normalized_sizes, dtype=pl.Int64),
    ])

    return core

def process_sample_metadata() -> pl.DataFrame:
    path = SILVER_DIR / "sample_metadata"
    df = pl.scan_parquet(path if path.is_dir() else f"{path}.parquet")

    filtered = df.filter(pl.col("accession").cast(pl.String).is_in(SAMPLE_METADATA_ACCESSIONS))
    collected = filtered.collect()

    if collected.height == 0:
        return pl.DataFrame(schema={"replicate_id": pl.Binary})

    agg_exprs = []
    for acc in SAMPLE_METADATA_ACCESSIONS:
        if acc == "acquisition:type":
            expr = (
                pl.col("value")
                .filter(pl.col("accession").cast(pl.String) == acc)
                .first()
                .cast(pl.String)
                .alias(acc)
            )
        else:
            expr = (
                pl.col("value")
                .filter(pl.col("accession").cast(pl.String) == acc)
                .first()
                .cast(pl.String)
                .cast(pl.Float64, strict=False)
                .alias(acc)
            )
        agg_exprs.append(expr)

    result = collected.group_by("replicate_id").agg(agg_exprs)
    return result

def process_scan_metadata(table_name: str, prefix: str) -> pl.DataFrame:
    path = SILVER_DIR / table_name
    df = pl.scan_parquet(path if path.is_dir() else f"{path}.parquet")

    filtered = df.filter(
        pl.col("accession").cast(pl.String).is_in(SCAN_METADATA_ACCESSIONS)
    ).with_columns(
        pl.col("value").cast(pl.Float64, strict=False).alias("numeric_value")
    )

    aggregated = (
        filtered.group_by(["replicate_id", "accession"])
        .agg([
            pl.col("numeric_value").median().alias("median"),
            pl.col("numeric_value").std().alias("std")
        ])
        .collect()
    )

    if aggregated.height == 0:
        return pl.DataFrame(schema={"replicate_id": pl.Binary})

    pivoted = aggregated.pivot(
        index="replicate_id",
        on="accession",
        values=["median", "std"]
    )

    rename_map = {
        col: f"{prefix}_{col}" for col in pivoted.columns if col != "replicate_id"
    }
    return pivoted.rename(rename_map)

def main():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading core silver tables...")
    gold_df = load_core_silver()

    print("Processing sample metadata...")
    sample_meta_df = process_sample_metadata()
    if not sample_meta_df.is_empty():
        gold_df = gold_df.join(sample_meta_df, on="replicate_id", how="left")

    print("Processing MS1 metadata...")
    ms1_df = process_scan_metadata("ms1_metadata", "ms1")
    if not ms1_df.is_empty():
        gold_df = gold_df.join(ms1_df, on="replicate_id", how="left")

    print("Processing MS2 metadata...")
    ms2_df = process_scan_metadata("ms2_metadata", "ms2")
    if not ms2_df.is_empty():
        gold_df = gold_df.join(ms2_df, on="replicate_id", how="left")

    output_path = GOLD_DIR / "replicates_gold.parquet"
    print(f"Writing gold table to {output_path}...")
    gold_df.write_parquet(output_path)
    print("Gold model generation complete.")

if __name__ == "__main__":
    main()
