#!/usr/bin/env -S uv run --with polars --with pyarrow python3

import os
import struct
import shutil
from pathlib import Path

import polars as pl

BRONZE_DIR = Path(os.getenv("BRONZE_DIR", "bronze"))
SILVER_DIR = Path(os.getenv("SILVER_DIR", "silver"))
GOLD_DIR = Path(os.getenv("GOLD_DIR", "."))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
COMPRESSION = os.getenv("PARQUET_COMPRESSION", "zstd")

SAMPLE_METADATA_ACCESSIONS = [
    "acquisition:type",
    "info:instrument_name",
    "ms2:isolation_window_avg",
    "ms2:peak_count_avg",
    "ms1:peak_count_avg",
    "ms2:spectrum_count",
    "ms1:spectrum_count",
    "summary:spectrum_count",
    "summary:total_run_time_seconds",
]

SCAN_METADATA_ACCESSIONS = [
    "peak_intensity:median",
    "peak_separation:median",
]


def parquet_path(table_name: str) -> Path:
    path = SILVER_DIR / table_name
    return path if path.is_dir() else path.with_suffix(".parquet")


def get_gzip_sizes(
    replicate_id_bytes: bytes,
) -> tuple[int | None, int | None]:
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

        with path.open("rb") as f:
            f.seek(-4, 2)
            data = f.read(4)

        if len(data) != 4:
            return compressed_size, None

        uncompressed_size = struct.unpack("<I", data)[0]
        return compressed_size, uncompressed_size

    except OSError as exc:
        print(f"{path} exception: {exc}")
        return None, None


def iter_batches(items: list, batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def load_core_silver() -> pl.DataFrame:
    replicates_path = parquet_path("replicates")
    files_path = parquet_path("files")

    replicates = pl.scan_parquet(replicates_path)
    files = pl.scan_parquet(files_path).select(
        [
            "replicate_id",
            "repository_id",
            pl.col("size_bytes").alias("raw_size_bytes"),
        ]
    )

    core = replicates.join(
        files,
        on="replicate_id",
        how="left",
    ).collect(engine="streaming")

    compressed_sizes = []
    normalized_sizes = []

    for rid in core["replicate_id"].to_list():
        compressed, normalized = get_gzip_sizes(rid)
        compressed_sizes.append(compressed)
        normalized_sizes.append(normalized)

    return core.with_columns(
        [
            pl.Series(
                "compressed_size_bytes",
                compressed_sizes,
                dtype=pl.Int64,
            ),
            pl.Series(
                "normalized_size_bytes",
                normalized_sizes,
                dtype=pl.Int64,
            ),
        ]
    )


def process_sample_metadata_for_ids(
    replicate_ids: list,
) -> pl.LazyFrame:
    schema = {
        "replicate_id": pl.Binary,
        **{
            acc: pl.String if acc in (
                "acquisition:type",
                "info:instrument_name",
            ) else pl.Float64
            for acc in SAMPLE_METADATA_ACCESSIONS
        },
    }

    if not replicate_ids:
        return pl.DataFrame(schema=schema).lazy()

    df = pl.scan_parquet(parquet_path("sample_metadata"))

    filtered = df.filter(
        pl.col("replicate_id").is_in(replicate_ids)
        & pl.col("accession")
        .cast(pl.String)
        .is_in(SAMPLE_METADATA_ACCESSIONS)
    )

    expressions = []

    for acc in SAMPLE_METADATA_ACCESSIONS:
        value = (
            pl.col("value")
            .filter(pl.col("accession").cast(pl.String) == acc)
            .first()
        )

        if acc in ("acquisition:type", "info:instrument_name"):
            expr = value.cast(pl.String).alias(acc)
        else:
            expr = (
                value.cast(pl.String)
                .cast(pl.Float64, strict=False)
                .alias(acc)
            )

        expressions.append(expr)

    return filtered.group_by("replicate_id").agg(expressions)


def process_scan_metadata_for_ids(
    table_name: str,
    prefix: str,
    replicate_ids: list,
) -> pl.LazyFrame:
    schema = {"replicate_id": pl.Binary}

    for acc in SCAN_METADATA_ACCESSIONS:
        schema[f"{prefix}_{acc}_median"] = pl.Float64
        schema[f"{prefix}_{acc}_std"] = pl.Float64

    if not replicate_ids:
        return pl.DataFrame(schema=schema).lazy()

    df = pl.scan_parquet(parquet_path(table_name))

    filtered = (
        df.filter(
            pl.col("replicate_id").is_in(replicate_ids)
            & pl.col("accession")
            .cast(pl.String)
            .is_in(SCAN_METADATA_ACCESSIONS)
        )
        .with_columns(
            pl.col("value")
            .cast(pl.Float64, strict=False)
            .alias("numeric_value")
        )
    )

    expressions = []

    for acc in SCAN_METADATA_ACCESSIONS:
        values = pl.col("numeric_value").filter(
            pl.col("accession").cast(pl.String) == acc
        )

        expressions.extend(
            [
                values.median().alias(f"{prefix}_{acc}_median"),
                values.std().alias(f"{prefix}_{acc}_std"),
            ]
        )

    return filtered.group_by("replicate_id").agg(expressions)


def process_batch(core_batch: pl.DataFrame) -> pl.LazyFrame:
    replicate_ids = core_batch["replicate_id"].to_list()

    sample_meta = process_sample_metadata_for_ids(replicate_ids)
    ms1_meta = process_scan_metadata_for_ids(
        "ms1_metadata", "ms1", replicate_ids
    )
    ms2_meta = process_scan_metadata_for_ids(
        "ms2_metadata", "ms2", replicate_ids
    )

    return (
        core_batch.lazy()
        .join(sample_meta, on="replicate_id", how="left")
        .join(ms1_meta, on="replicate_id", how="left")
        .join(ms2_meta, on="replicate_id", how="left")
    )


def main():
    if BATCH_SIZE < 1:
        raise ValueError("BATCH_SIZE must be at least 1")

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    output_path = GOLD_DIR / "replicates_gold.parquet"
    parts_dir = GOLD_DIR / "_replicates_gold_parts"

    if parts_dir.exists():
        shutil.rmtree(parts_dir)

    parts_dir.mkdir(parents=True)

    print("Loading core silver tables...")
    core = load_core_silver()

    replicate_ids = core["replicate_id"].to_list()
    total = len(replicate_ids)

    print(f"Processing {total} replicates in batches of {BATCH_SIZE}...")

    for batch_number, ids in enumerate(
        iter_batches(replicate_ids, BATCH_SIZE)
    ):
        print(
            f"Processing batch {batch_number + 1}: "
            f"{len(ids)} replicates"
        )

        core_batch = core.filter(
            pl.col("replicate_id").is_in(ids)
        )

        result = process_batch(core_batch)

        part_path = parts_dir / f"part_{batch_number:06d}.parquet"

        result.sink_parquet(
            part_path,
            compression=COMPRESSION,
            engine="streaming",
        )

        del result, core_batch

    print("Combining batch files into final gold table...")

    part_files = sorted(parts_dir.glob("part_*.parquet"))

    if part_files:
        pl.scan_parquet(part_files).sink_parquet(
            output_path,
            compression=COMPRESSION,
            engine="streaming",
        )
    else:
        core.head(0).write_parquet(output_path, compression=COMPRESSION)

    shutil.rmtree(parts_dir)

    print(f"Gold table written to {output_path}")


if __name__ == "__main__":
    main()
