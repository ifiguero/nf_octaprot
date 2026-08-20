#!/usr/bin/env -S uv run --with polars --with ftputil python3

from __future__ import annotations
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse
from ftplib import FTP_TLS
from pathlib import Path
import ftputil.session
import polars as pl

import ftputil
import hashlib
import logging
import time
import sys
import os


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    nullable: bool = True



logger = logging.getLogger(__name__)


SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "repositories": SILVER_ROOT / "repositories",
    "files": SILVER_ROOT / "files",
    "replicates": SILVER_ROOT / "replicates",
}


REPOSITORIES_SCHEMA = {
    "table": "repositories",
    "description": "Repository inventory",
    "columns": [
        Column("id", "string", False),
        Column("url", "string", False),
        Column("doi", "string", False),
    ],
}


FILES_SCHEMA = {
    "table": "files",
    "description": "Discovered repository files",
    "columns": [
        Column("id", "string"),
        Column("repository_id", "string", False),
        Column("remote_path", "string", False),
        Column("size_bytes", "int64"),
        Column("scan_timestamp", "timestamp"),
    ],
}

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


COMPRESSION_EXTENSIONS = [".gz", ".zip", ".7z", ".bz2", ".xz"]
SAMPLE_EXTENSIONS = [".raw", ".d", ".mgf", ".mzml", ".wiff", ".wiff2"]

MAX_RETRIES = 3

def output_name(sample_id, remote_path):

    name = Path(remote_path).name.lower()
    compression = None

    for ext in COMPRESSION_EXTENSIONS:
        if name.endswith(ext):
            compression =  ext.lstrip('.')
            name = name[:-len(comp_ext)]

    for ext in SAMPLE_EXTENSIONS:
        if name.endswith(ext):
            sample_id =  f"{sample_id}.{ext.lstrip('.')}"

    if compression is not None:
        sample_id =  f"{sample_id}.{compression}"

    return sample_id

def load_sample(sample_id: str) -> dict:
    df = load_table("files")

    row = (
        df.filter(pl.col("id") == sample_id)
          .select(
              "id",
              "repository_id",
              "remote_path",
              "size_bytes",
          )
    )

    if row.height != 1:
        fail(f"Sample '{sample_id}' not found")

    sample = row.row(0, named=True)

    repo = (
        load_table("repositories")
        .filter(pl.col("id") == sample["repository_id"])
        .select("url")
    )

    if repo.height != 1:
        fail(f"Repository '{sample['repository_id']}' not found")

    sample["ftp_url"] = repo.item()

    return sample

def parse_ftp_url(url: str):
    parsed = urlparse(url)

    return {
        "host": parsed.hostname,
        "port": parsed.port or 21,
        "user": parsed.username or "anonymous",
        "password": parsed.password or "",
        "path": parsed.path.rstrip("/") or "/",
    }

def open_ftp(info):

    if "massive-ftp.ucsd.edu" in info["host"]:
        session = ftputil.session.session_factory(
            base_class=FTP_TLS,
            port=info["port"],
            encoding="utf-8",
        )
    else:
        session = ftputil.session.session_factory(
            port=info["port"],
            encoding="utf-8",
        )

    return ftputil.FTPHost(
        info["host"],
        info["user"],
        info["password"],
        session_factory=session,
    )

def download_directory(ftp, remote_dir, output_dir):
    output_dir.mkdir(exist_ok=True)

    for name in ftp.listdir(remote_dir):
        remote = ftp.path.join(remote_dir, name)
        if not ftp.path.isfile(remote):
            continue

            download_file(ftp, remote, output_dir / name )

def download_file(ftp, remote_path, output_path):

    part = output_path.with_suffix(output_path.suffix + ".part")
    expected_size = ftp.path.getsize(remote_path)

    if output_path.exists():
        if output_path.stat().st_size == expected_size:
            logger.info("Already downloaded.")
            return

        output_path.unlink()

    offset = part.stat().st_size if part.exists() else 0

    mode = "ab" if offset else "wb"

    with ftp.open(remote_path, "rb", rest=offset) as src:
        with open(part, mode) as dst:

            while True:
                chunk = src.read(1024 * 1024)

                if not chunk:
                    break

                dst.write(chunk)

    if part.stat().st_size != expected_size:
        raise RuntimeError("Incomplete download")

    part.rename(output_path)
    logger.info(f"File {output_path.name} downloaded suscessfully")

def download_sample(sample, basepath='stage'):
    ftp_info = parse_ftp_url(sample["ftp_url"])
    basepath = Path(basepath)

    ftp_info["path"] = sample["remote_path"]

    last = None
    for attempt in range(MAX_RETRIES):
        try:
            with open_ftp(ftp_info) as ftp:
                if sample["remote_path"].lower().endswith(".d"):
                    output_path = basepath / 'raw' / f"{sample['id']}.d"
                    download_directory(ftp, sample["remote_path"], output_path )

                else:
                    output_path = basepath / 'raw' / output_name(sample["id"], sample["remote_path"])
                    download_file(ftp, sample["remote_path"], output_path)
                    if sample["remote_path"].lower().endswith(".wiff") and ftp.path.exists(f"{sample["remote_path"]}.scan"):
                        output_path_scan = output_path.parent / (output_path.name + ".scan")
                        download_file(ftp, f"{sample['remote_path']}.scan", output_path_scan)

                sample_output_filename = basepath / "sample_filename.txt"
                with open( sample_output_filename, 'w' ) as sample_out_file:
                    sample_out_file.write(output_path.as_posix()+ "\n")

                return

        except Exception as exc:
            last = exc
            logger.warning(
                "Attempt %d/%d failed: %s",
                attempt + 1,
                MAX_RETRIES,
                exc,
            )

            if attempt + 1 < MAX_RETRIES:
                time.sleep(2 ** attempt)

    raise RuntimeError(last)

def fail(message: str) -> None:
    logger.error(message)
    sys.exit(1)

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if len(sys.argv) != 2:
        fail(
            f"Usage: {Path(sys.argv[0]).name} "
            f"<sample_id>"
        )

    sample_data = load_sample(sys.argv[1])

    Path("stage/raw").mkdir(parents=True, exist_ok=True)
    Path("stage/mzml").mkdir(parents=True, exist_ok=True)

    download_sample(sample_data)

    return 0


if __name__ == "__main__":
    sys.exit(main())
