# Output Structure and DuckDB Queries (Silver Layer)

## Output layout (verified)
From config and processes:
- `output/silver/` - Parquet tables produced by pipeline
  - `repositories/` - from `REPOSITORY_TO_PARQUET` (schema: `id,url,doi`)
  - `files/` - from `REPOSITORY_FILES_EXTRACT` (schema: `replicate_id,repository_id,remote_path,size_bytes,scan_timestamp`)
  - `replicates/` - from `LOAD_REPLICATES` (schema: `replicate_id,organism,source_type,material,condition,sample_group`)
  - `psm/{engine}/` - PSM Parquet from `032_save_psm.py` (columns include `replicate_id,peptide,charge,software,scan_number,retention_time,confidence`)
  - `psm_runtime/{engine}/` - runtimes from `033_save_time.py`
  - `sample_metadata/`, `ms1_metadata/`, `ms2_metadata/`, `spec_intensity/`, `spec_percentile/`, `fasta_peptide/` etc. as produced
- `output/bronze/` - mzML.gz files from transcode
- `output/dump/` - summary CSVs/SQL/PNGs (`01repo/`, `02batch/`, `99sqldump/`, `097_GoldReport/`)
- `output/gold/` - gold Parquet/LaTeX from gold modules

**Silver schemas (from `lib/silver_model.py`)**:
- `REPOSITORY_SCHEMA`: `id(string,not null), url(string,not null), doi(string,not null)`
- `FILES_SCHEMA`: `id/replicate_id(string), repository_id(string,not null), remote_path(string,not null), size_bytes(int64), scan_timestamp(timestamp)` (note: in code files schema uses `replicate_id` as sample id column)
- `REPLICATES_SCHEMA`: `id/replicate_id(string,not null), organism(string,not null), source_type(string,not null), material(string,not null), condition(string,not null), sample_group(string,not null)`

Check actual files after run: `find output/silver -name "*.parquet" | head -20`

## Is dataset partitioned?
Not explicitly partitioned by Hive in the scripts shown (files written as individual parquet files). You can query directories as datasets.

## DuckDB examples
Use DuckDB CLI or Python with `uv`. Examples below use paths relative to repo root.

### Read a single Parquet file
```sql
SELECT * FROM read_parquet('output/silver/repositories/PXD001064.parquet') LIMIT 5;
```

### Read a Parquet dataset (directory of files)
```sql
-- Read all repositories
SELECT * FROM read_parquet('output/silver/repositories/*.parquet');

-- Read all files
SELECT * FROM read_parquet('output/silver/files/*.parquet');

-- Read all replicates
SELECT * FROM read_parquet('output/silver/replicates/*.parquet');
```

### Inspect schema
```sql
DESCRIBE SELECT * FROM read_parquet('output/silver/replicates/*.parquet');
-- or
SELECT * FROM parquet_schema('output/silver/replicates/*.parquet');
```

### Count rows
```sql
SELECT COUNT(*) AS cnt FROM read_parquet('output/silver/files/*.parquet');
SELECT COUNT(*) AS cnt FROM read_parquet('output/silver/replicates/*.parquet');
```

### Select a few records
```sql
SELECT replicate_id, organism, material, condition 
FROM read_parquet('output/silver/replicates/*.parquet') 
LIMIT 10;
```

### Filter records
```sql
SELECT replicate_id, remote_path, size_bytes 
FROM read_parquet('output/silver/files/*.parquet') 
WHERE replicate_id IS NOT NULL 
LIMIT 20;
```

### Aggregate by relevant column
```sql
SELECT organism, COUNT(*) AS n_replicates, SUM(size_bytes)/1e9 AS total_gb
FROM read_parquet('output/silver/files/*.parquet') f
JOIN read_parquet('output/silver/replicates/*.parquet') r
  ON f.replicate_id = r.replicate_id
WHERE f.replicate_id IS NOT NULL
GROUP BY organism
ORDER BY total_gb DESC;
```

## Python with uv
```python
# run: uv run --with duckdb python example.py
import duckdb

con = duckdb.connect()
df = con.execute("SELECT * FROM read_parquet('output/silver/replicates/*.parquet') LIMIT 5").df()
print(df)
```

## Determining run success
- Check Nextflow exit code (0 = success)
- Verify expected outputs exist: `output/silver/repositories/`, `output/silver/files/`, etc.
- Check logs in `.nextflow.log` and pod logs
- For stage1, ensure summary CSVs in `output/dump/01repo/`

**Note**: Schema/columns may vary slightly; use `DESCRIBE` to discover actual schema.
