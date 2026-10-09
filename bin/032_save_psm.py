#!/usr/bin/env -S uv run --with polars  --with pyarrow python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

import polars as pl


SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "ms1_metadata": SILVER_ROOT / "ms1_metadata",
    "ms2_metadata": SILVER_ROOT / "ms2_metadata",
}

SOFTWARE = ("msfragger", "sage", "alphadia", "diann")

PSM_COLUMNS = [
    "replicate_id",
    "peptide",
    "charge",
    "software",
    "scan_number",
    "retention_time",
    "confidence",
]


def load_scan_rt_table(replicate_id: str) -> pl.DataFrame:
    tables = []

    for table_name, root in TABLE_TO_PARQUET.items():
        path = root / f"{replicate_id}.parquet"

        if path.exists():
            df = pl.read_parquet(path)

            required = {"accession", "scan_number", "value"}
            if not required.issubset(df.columns):
                continue

            tables.append(
                df.filter(pl.col("accession").cast(pl.String) == "MS:1000016", pl.col("replicate_id").cast(pl.String) == replicate_id)
                .select(
                    pl.col("scan_number").cast(pl.Int64, strict=False),
                    pl.col("value")
                    .cast(pl.Float64, strict=False)
                    .alias("retention_time"),
                )
            )

    if not tables:
        raise FileNotFoundError(
            f"No usable scan metadata found for sample {replicate_id!r} "
            f"under {SILVER_ROOT}"
        )

    scan_rt = (
        pl.concat(tables, how="diagonal_relaxed")
        .drop_nulls(["scan_number", "retention_time"])
        .unique(subset=["scan_number"], keep="first", maintain_order=True)
        .sort("scan_number")
    )

    if scan_rt.is_empty():
        raise ValueError(
            f"No MS:1000016 retention-time entries found for {replicate_id!r}"
        )

    return scan_rt


def require(df: pl.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def number(column: str, dtype: pl.DataType = pl.Float64) -> pl.Expr:
    return pl.col(column).cast(dtype, strict=False)


def empty_scan() -> pl.Expr:
    return pl.lit(None, dtype=pl.Int64)


def parse_msfragger(df: pl.DataFrame, replicate_id: str) -> pl.DataFrame:
    require(
        df,
        ["scannum", "retention_time", "charge", "peptide", "expectscore"],
    )

    return df.select(
        pl.lit(replicate_id).alias("replicate_id"),
        pl.col("peptide").cast(pl.String),
        number("charge", pl.Int16).alias("charge"),
        pl.lit("msfragger").alias("software"),
        number("scannum", pl.Int64).alias("scan_number"),
        number("retention_time").alias("retention_time"),
        number("expectscore").alias("confidence"),
    )


def parse_sage(df: pl.DataFrame, replicate_id: str) -> pl.DataFrame:
    require(df, ["scannr", "rt", "charge", "peptide", "posterior_error"])

    return df.select(
        pl.lit(replicate_id).alias("replicate_id"),
        pl.col("peptide").cast(pl.String),
        number("charge", pl.Int16).alias("charge"),
        pl.lit("sage").alias("software"),
        number("scannr", pl.Int64).alias("scan_number"),
        number("rt").alias("retention_time"),
        number("posterior_error").alias("confidence"),
    )


def parse_alphadia(df: pl.DataFrame, replicate_id: str) -> pl.DataFrame:
    require(
        df,
        [
            "precursor.rt.observed",
            "precursor.charge",
            "precursor.sequence",
            "precursor.proba",
        ],
    )

    return df.select(
        pl.lit(replicate_id).alias("replicate_id"),
        pl.col("precursor.sequence").cast(pl.String).alias("peptide"),
        number("precursor.charge", pl.Int16).alias("charge"),
        pl.lit("alphadia").alias("software"),
        empty_scan().alias("scan_number"),
        number("precursor.rt.observed").alias("retention_time"),
        number("precursor.proba").alias("confidence"),
    )


def parse_diann(df: pl.DataFrame, replicate_id: str) -> pl.DataFrame:
    require(
        df,
        ["Modified.Sequence", "Precursor.Charge", "RT", "PEP"],
    )

    return df.select(
        pl.lit(replicate_id).alias("replicate_id"),
        pl.col("Modified.Sequence").cast(pl.String).alias("peptide"),
        number("Precursor.Charge", pl.Int16).alias("charge"),
        pl.lit("diann").alias("software"),
        empty_scan().alias("scan_number"),
        number("RT").alias("retention_time"),
        number("PEP").alias("confidence"),
    )


def read_input(path: Path, software: str) -> pl.DataFrame:
    if software == "diann":
        if path.suffix.lower() != ".parquet":
            raise ValueError("DIA-NN input must be a Parquet file.")

        return pl.read_parquet(path, use_pyarrow=True)

    if path.suffix.lower() != ".tsv":
        raise ValueError(f"{software} input must be a TSV file.")

    return pl.read_csv(
        path,
        separator="\t",
        infer_schema_length=10000,
        try_parse_dates=False,
    )


def rt_to_scan(
    retention_times: pl.Series,
    scan_rt: pl.DataFrame,
) -> pl.Series:
    query = pl.DataFrame(
        {
            "_index": pl.Series(
                "_index", range(len(retention_times)), dtype=pl.UInt32
            ),
            "retention_time": retention_times.cast(pl.Float64, strict=False),
        }
    ).filter(pl.col("retention_time").is_not_null())

    if query.is_empty() or scan_rt.is_empty():
        return pl.Series("scan_number", [None] * len(retention_times), dtype=pl.Int64)

    matched = (
        query.sort("retention_time")
        .join_asof(
            scan_rt.sort("retention_time"),
            on="retention_time",
            strategy="nearest",
        )
        .select("_index", "scan_number")
    )

    return (
        pl.DataFrame(
            {"_index": pl.Series(range(len(retention_times)), dtype=pl.UInt32)}
        )
        .join(matched, on="_index", how="left")
        .sort("_index")
        .get_column("scan_number")
        .cast(pl.Int64)
    )


def scan_to_rt(
    scan_nums: pl.Series,
    scan_rt: pl.DataFrame,
) -> pl.Series:
    lookup = scan_rt.select("scan_number", "retention_time").unique("scan_number")

    return (
        pl.DataFrame(
            {
                "_index": pl.Series(range(len(scan_nums)), dtype=pl.UInt32),
                "scan_number": scan_nums.cast(pl.Int64, strict=False),
            }
        )
        .join(lookup, on="scan_number", how="left")
        .sort("_index")
        .get_column("retention_time")
    )


def normalize(psm: pl.DataFrame, scan_rt: pl.DataFrame) -> pl.DataFrame:
    needs_scan = (
        pl.col("scan_number").is_null()
        & pl.col("retention_time").is_not_null()
    )

    if psm.filter(needs_scan).height:
        scans = rt_to_scan(psm.get_column("retention_time"), scan_rt)

        psm = psm.with_columns(
            pl.when(pl.col("scan_number").is_null())
            .then(scans)
            .otherwise(pl.col("scan_number"))
            .alias("scan_number")
        )

    needs_rt = (
        pl.col("retention_time").is_null()
        & pl.col("scan_number").is_not_null()
    )

    if psm.filter(needs_rt).height:
        retention_times = scan_to_rt(psm.get_column("scan_number"), scan_rt)

        psm = psm.with_columns(
            pl.when(pl.col("retention_time").is_null())
            .then(retention_times)
            .otherwise(pl.col("retention_time"))
            .alias("retention_time")
        )

    return psm.select(
        pl.col("replicate_id").cast(pl.String),
        pl.col("peptide").cast(pl.String),
        pl.col("charge").cast(pl.Int16, strict=False),
        pl.col("software").cast(pl.String),
        pl.col("scan_number").cast(pl.Int64, strict=False),
        pl.col("retention_time").cast(pl.Float64, strict=False),
        pl.col("confidence").cast(pl.Float64, strict=False),
    ).select(PSM_COLUMNS)


def process(
    replicate_id: str,
    results_file: str,
    software: str
) -> pl.DataFrame:

    source = read_input(results_file, software)


    routines = {
        "msfragger": parse_msfragger,
        "sage": parse_sage,
        "alphadia": parse_alphadia,
        "diann": parse_diann,
    }

    raw_data = routines[software](source, replicate_id)

    scan_rt = load_scan_rt_table(replicate_id)

    normalized_data = normalize(raw_data, scan_rt)

    return normalized_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert search-engine results into canonical PSM Parquet."
    )

    mode = parser.add_mutually_exclusive_group(required=True)

    for software in SOFTWARE:
        mode.add_argument(
            f"--{software}",
            dest="software",
            action="store_const",
            const=software,
        )

    parser.add_argument("id", help="Sample identifier")
    parser.add_argument("results", type=Path, help="Existing results file")

    args = parser.parse_args()

    if not args.results.is_file():
        parser.error(f"Results file does not exist: {args.results}")

    psm = process(args.id, args.results, args.software)

    output_path = Path(f"{args.id}.parquet")

    psm.write_parquet(output_path, compression="zstd")


if __name__ == "__main__":
    main()
