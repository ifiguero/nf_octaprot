#!/usr/bin/env -S uv run --with polars --with ftputil python3

from __future__ import annotations
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

COMPRESSION_EXTENSIONS = [".gz", ".zip", ".7z", ".bz2", ".xz"]
SAMPLE_EXTENSIONS = [".raw", ".d", ".mgf", ".mzml", ".wiff", ".wiff2"]

MAX_RETRIES = 3
LARGE_FILE_THRESHOLD = 157286400  # 150 MiB

logger = logging.getLogger(__name__)

def fail(message: str) -> None:
    logger.error(message)
    sys.exit(1)

def polars_dtype(dtype: str) -> pl.DataType:
    mapping = {
        "string": pl.Utf8,
        "int64": pl.Int64,
        "timestamp": pl.Datetime(time_unit="us"),
    }

    try:
        return mapping[dtype]
    except KeyError:
        fail(f"Unsupported schema dtype: {dtype}")

def generate_sample_id(repository_id: str, remote_path: str) -> str:
    file_id = os.path.basename(remote_path).lower()
    uncompressed = file_id
    for comp_ext in COMPRESSION_EXTENSIONS:
        if file_id.endswith(comp_ext):
            uncompressed = file_id[:-len(comp_ext)]
            break

    sample_id = uncompressed

    for sample_ext in SAMPLE_EXTENSIONS:
        if uncompressed.endswith(sample_ext):
            sample_id = uncompressed[:-len(sample_ext)]
            break

    return f"{repository_id}_{sample_id}"

def scan_ftp_directory(ftp, current_path: str, files_list: list[dict]) -> int:
    items = ftp.listdir(current_path)
    folder_size = 0

    for item in items:
        if item in (".", ".."):
            continue

        item_path = ftp.path.join(current_path, item)

        if ftp.path.isfile(item_path):
            size = ftp.path.getsize(item_path)

            files_list.append(
                {
                    "remote_path": item_path,
                    "size_bytes": size,
                }
            )

            folder_size += size

        elif ftp.path.isdir(item_path):
            sub_list: list[dict] = []

            subfolder_size = scan_ftp_directory(
                ftp,
                item_path,
                sub_list,
            )

            files_list.append(
                {
                    "remote_path": item_path,
                    "size_bytes": subfolder_size,
                }
            )

            if not os.path.basename(item_path).lower().endswith(".d"):
                files_list.extend(sub_list)

            folder_size += subfolder_size

    return folder_size

def load_repository(parquet_path: Path) -> dict:
    try:
        df = pl.read_parquet(parquet_path)
    except Exception as exc:
        fail(f"Failed to read parquet: {exc}")

    if df.height != 1:
        fail(
            f"Repository parquet must contain exactly one row, "
            f"found {df.height}"
        )

    return df.row(0, named=True)

def scan_repository(ftp_url: str) -> list[dict]:
    parsed = urlparse(ftp_url)

    user = parsed.username or "anonymous"
    password = parsed.password or ""
    host = parsed.hostname

    if not host:
        fail("FTP URL does not contain a hostname")

    port = parsed.port or 21
    remote_path = parsed.path or "/"

    if remote_path.endswith("/") and remote_path != "/":
        remote_path = remote_path[:-1]

    files_list: list[dict] = []

    if 'massive-ftp.ucsd.edu' in host:
        session_factory = ftputil.session.session_factory( base_class=FTP_TLS, port=port, encoding="utf-8", debug_level=2 )
    else:
        session_factory = ftputil.session.session_factory( port=port, encoding="utf-8", debug_level=2 )

    last_exception = None
    sleep_time = 5

    for attempt in range(MAX_RETRIES):
        try:
            print(f"FTP attempt {host}:{port}, {user}@{password} | {remote_path}")
            with ftputil.FTPHost(host, user, password, session_factory=session_factory) as ftp:
                scan_ftp_directory(ftp, remote_path, files_list)

            return files_list

        except Exception as exc:
            import sys, traceback
            last_exception = exc
            logger.warning(f"FTP attempt {attempt + 1}/{MAX_RETRIES} failed: {exc}")
            traceback.print_exc(file=sys.stdout)
            time.sleep(sleep_time)
            sleep_time *= 2


    fail(f"FTP scan failed after {MAX_RETRIES} attempts: {last_exception}")

def is_valid_sample_filename(filename: str) -> Bool:
    """
    Check if filename is a valid sample file (possibly compressed).

    Returns:
        Bool: is_valid. True if valid sample format
    """
    name = os.path.basename(filename).lower()

    for comp_ext in COMPRESSION_EXTENSIONS:
        if name.endswith(comp_ext):
            name = name[:-len(comp_ext)]
            break

    for sample_ext in SAMPLE_EXTENSIONS:
        if name.endswith(sample_ext):
            return True
    return False

def build_output_dataframe(repository_id: str, files_list: list[dict]) -> pl.DataFrame:

    scan_timestamp = datetime.now(UTC)
    wiff_scan_sizes = {}
    aux_list = []

    for item in files_list:
        if item["remote_path"].lower().endswith(".wiff.scan"):
            wiff_path = item["remote_path"][:-5]  # remove ".scan"
            if wiff_path in wiff_scan_sizes:
                wiff_scan_sizes[wiff_path] += item["size_bytes"]
            else:
                wiff_scan_sizes[wiff_path] = item["size_bytes"]
        else:
            aux_list.append(item)

    wiff_fused = []

    for item in aux_list:
        if item["remote_path"] in wiff_scan_sizes:
            item["size_bytes"] += wiff_scan_sizes[item["remote_path"]]
        wiff_fused.append(item)


    rows = []

    for item in wiff_fused:
        size = item["size_bytes"]
        if size > LARGE_FILE_THRESHOLD and is_valid_sample_filename(item["remote_path"]):
            rows.append(
                {
                    "id": generate_sample_id(repository_id, item["remote_path"]),
                    "repository_id": repository_id,
                    "remote_path": item["remote_path"],
                    "size_bytes": size,
                    "scan_timestamp": scan_timestamp,
                }
            )
        else:
            rows.append(
                {
                    "id": None,
                    "repository_id": repository_id,
                    "remote_path": item["remote_path"],
                    "size_bytes": size,
                    "scan_timestamp": scan_timestamp,
                }
            )

    schema = { column.name: polars_dtype(column.dtype) for column in FILES_SCHEMA["columns"]  }

    return pl.DataFrame(rows, schema=schema)

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if len(sys.argv) != 2:
        fail(
            f"Usage: {Path(sys.argv[0]).name} "
            f"<repository.parquet>"
        )

    parquet_path = Path(sys.argv[1])

    repository = load_repository(parquet_path)

    repository_id = repository["id"]
    ftp_url = repository["url"]

    files_list = scan_repository(ftp_url)

    output_df = build_output_dataframe(
        repository_id,
        files_list,
    )

    output_path = Path(f"files_{repository_id}.parquet")

    output_df.write_parquet(output_path)

    logger.info(
        "Wrote %s records to %s",
        output_df.height,
        output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
