#!/usr/bin/env -S uv run --with polars --with pyarrow python3

import os
from pathlib import Path
import polars as pl

# ==========================================
# CONFIGURATION & GLOBAL VARIABLES
# ==========================================
GOLD_DIR = Path(os.getenv("GOLD_DIR", "gold"))

# Define the tables to construct systematically.
# Each entry specifies a title, the columns to group by,
# columns to sum, and columns to average.
TABLE_CONFIGS = [
    {
        "title": "Replicate Summary Aggregated by Repository ID",
        "group_by": ["repository_id"],
        "sum_cols": ["raw_size_bytes", "compressed_size_bytes", "normalized_size_bytes"],
        "avg_cols": ["summary:spectrum_count", "summary:total_run_time_seconds", "ms1:spectrum_count"]
    },
    {
        "title": "Replicate Summary Aggregated by Organism",
        "group_by": ["organism", "material"],
        "sum_cols": ["raw_size_bytes", "compressed_size_bytes", "ms1:spectrum_count", "ms2:spectrum_count"],
        "avg_cols": ["summary:spectrum_count", "summary:total_run_time_seconds"]
    },
    {
        "title": "Replicate Summary Aggregated by Condition",
        "group_by": ["material", "condition"],
        "sum_cols": ["raw_size_bytes", "compressed_size_bytes"],
        "avg_cols": ["summary:total_run_time_seconds", "ms1:peak_count_avg"]
    },
    {
        "title": "Replicate Summary Aggregated by Acquisition Type",
        "group_by": ["acquisition:type"],
        "sum_cols": ["raw_size_bytes", "compressed_size_bytes"],
        "avg_cols": ["summary:spectrum_count", "summary:total_run_time_seconds", "ms1:spectrum_count", "ms2:spectrum_count"]
    },
    {
        "title": "Replicate Summary Aggregated by Organism and Condition",
        "group_by": ["material", "acquisition:type"],
        "sum_cols": ["compressed_size_bytes"],
        "avg_cols": ["summary:spectrum_count", "summary:total_run_time_seconds", "ms1:spectrum_count", "ms1_std_peak_intensity:median", "ms2_std_peak_intensity:median"]
    }
]

def escape_latex(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return (text
            .replace("_", "\\_")
            .replace("%", "\\%")
            .replace("&", "\\&")
            .replace("#", "\\#"))

def generate_latex_table(df: pl.DataFrame, title: str, group_cols: list, sum_cols: list, avg_cols: list) -> str:
    # Build expressions for aggregation
    agg_exprs = []
    for col in sum_cols:
        if col in df.columns:
            agg_exprs.append(pl.col(col).sum().alias(f"{col}_sum"))
    for col in avg_cols:
        if col in df.columns:
            agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))
            agg_exprs.append(pl.col(col).std().alias(f"{col}_std"))

    # Perform aggregation
    grouped_df = df.group_by(group_cols).agg(agg_exprs).sort(group_cols)

    # Flatten headers correctly
    flat_headers = list(group_cols)
    for c in sum_cols:
        flat_headers.append(f"{c} Sum")
    for c in avg_cols:
        flat_headers.append(f"{c} Mean")
        flat_headers.append(f"{c} Std")

    col_format = "l" * len(group_cols) + "r" * (len(flat_headers) - len(group_cols))

    latex_lines = []
    latex_lines.append("\\begin{table}[htbp]")
    latex_lines.append("\\centering")
    latex_lines.append(f"\\caption{{{escape_latex(title)}}}")
    latex_lines.append(f"\\begin{{tabular}}{{{col_format}}}")
    latex_lines.append("\\toprule")

    header_str = " & ".join([escape_latex(h) for h in flat_headers]) + " \\\\"
    latex_lines.append(header_str)
    latex_lines.append("\\midrule")

    for row in grouped_df.iter_rows(named=True):
        row_values = []
        for g in group_cols:
            val = row.get(g)
            if isinstance(val, bytes):
                try:
                    val = val.decode("utf-8")
                except Exception:
                    val = val.hex()
            row_values.append(escape_latex(str(val)))

        for c in sum_cols:
            val = row.get(f"{c}_sum")
            row_values.append(f"{val:,.2f}" if isinstance(val, (int, float)) and val is not None else "-")

        for c in avg_cols:
            mean_val = row.get(f"{c}_mean")
            std_val = row.get(f"{c}_std")
            row_values.append(f"{mean_val:,.2f}" if isinstance(mean_val, (int, float)) and mean_val is not None else "-")
            row_values.append(f"{std_val:,.2f}" if isinstance(std_val, (int, float)) and std_val is not None else "-")

        latex_lines.append(" & ".join(row_values) + " \\\\")

    latex_lines.append("\\bottomrule")
    latex_lines.append("\\end{tabular}")
    latex_lines.append("\\end{table}")
    latex_lines.append("\n")

    return "\n".join(latex_lines)

def main():
    df = pl.scan_parquet(GOLD_DIR / "*.parquet").collect()

    byte_cols = [col for col in df.columns if col.endswith("_bytes")]
    if byte_cols:
        df = df.with_columns([(pl.col(col) / (1024 ** 3)).alias(col) for col in byte_cols])
    document_body = []
    document_body.append("% --- AUTO-GENERATED GOLD MODEL REPORT ---")

    for config in TABLE_CONFIGS:
        table_latex = generate_latex_table(
            df=df,
            title=config["title"],
            group_cols=config["group_by"],
            sum_cols=config["sum_cols"],
            avg_cols=config["avg_cols"]
        )
        document_body.append(table_latex)

    Path("replicates_report.tex").write_text("\n".join(document_body), encoding="utf-8")


if __name__ == "__main__":
    main()
