#!/usr/bin/env -S uv run --with polars --with matplotlib --with numpy python3

from __future__ import annotations

from pathlib import Path
import os
import sys
import random
import matplotlib.pyplot as plt
import polars as pl

FIG_WIDTH = 3.4  # inches (single-column article)
FONT_SIZE = 12

plt.rcParams.update({
    "font.size": FONT_SIZE,
    "axes.titlesize": FONT_SIZE,
    "legend.fontsize": 7,
})


SILVER_ROOT = Path(os.environ["SILVER_DIR"])

TABLE_TO_PARQUET = {
    "files": SILVER_ROOT / "files",
    "replicates": SILVER_ROOT / "replicates",
}


PIE_COLORS = [
    "#4E79A7",
    "#F28E2B",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#B07AA1",
    "#EDC948",
    "#9C755F",
    "#FF9DA7",
    "#BAB0AC",
]


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




def sanitize_filename(text: str) -> str:
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(":", "_")
    )


def human_size(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]

    for unit in units:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} EB"


def build_dataset() -> pl.DataFrame:
    replicates = load_table("replicates")
    files = load_table("files")

    if replicates.is_empty() or files.is_empty():
        return pl.DataFrame()

    file_columns = [
        c
        for c in (
            "id",
            "repository_id",
            "size_bytes",
        )
        if c in files.columns
    ]

    files = files.select(file_columns)

    return replicates.join(
        files,
        on="id",
        how="inner",
    )


def aggregate_small_groups(
    df: pl.DataFrame,
    label_column: str,
    value_column: str,
    threshold: float = 0.02,
) -> pl.DataFrame:
    total = (
        df[value_column]
        .cast(pl.Float64)
        .sum()
    )

    if total <= 0:
        return df

    df = (
        df
        .with_columns(
            (
                pl.col(value_column)
                / total
            ).alias("_fraction")
        )
        .sort(
            value_column,
            descending=True,
        )
    )

    major = df.filter(
        pl.col("_fraction") >= threshold
    )

    minor = df.filter(
        pl.col("_fraction") < threshold
    )

    if minor.is_empty():
        return major.drop("_fraction")

    if minor.height == 1:
        return (
            pl.concat(
                [
                    major.select(
                        [label_column, value_column]
                    ),
                    minor.select(
                        [label_column, value_column]
                    ),
                ],
                how="diagonal_relaxed",
            )
            .sort(
                value_column,
                descending=True,
            )
        )

    aggregated_value = (
        minor[value_column]
        .cast(pl.Float64)
        .sum()
    )

    aggregated_count = minor.height

    aggregated = pl.DataFrame(
        {
            label_column: [
                f"Other ({aggregated_count} groups)"
            ],
            value_column: [aggregated_value],
        }
    )

    return pl.concat(
        [
            major.select(
                [label_column, value_column]
            ),
            aggregated,
        ],
        how="diagonal_relaxed",
    )


def pie_chart(
    df: pl.DataFrame,
    group_column: str,
    value_column: str,
    title: str,
    output_path: Path,
    threshold: float = 0.02
) -> bool:
    grouped = (
        df
        .filter(
            pl.col(group_column).is_not_null()
        )
        .group_by(group_column)
        .agg(
            pl.col(value_column)
            .sum()
            .alias("value")
        )
        .sort(
            "value",
            descending=True,
        )
    )

    if grouped.height <= 1:
        return False

    grouped = aggregate_small_groups(
        grouped,
        group_column,
        "value",
        threshold=threshold
    )

    labels = (
        grouped[group_column]
        .cast(pl.String)
        .to_list()
    )

    values = (
        grouped["value"]
        .cast(pl.Float64)
        .to_list()
    )

    total = float(sum(values))

    legend_labels = [
        f"{label} ({100.0 * value / total:.1f}%)"
        for label, value in zip(
            labels,
            values,
            strict=False,
        )
    ]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_WIDTH))

    wedges, _ = ax.pie(
        values,
        startangle=random.uniform(0, 360),
        colors=PIE_COLORS[: len(values)],
    )

    # titlearr = title.split(":")
    # if len(titlearr) > 1:
    #     fig.suptitle(titlearr[1], y=0.99)
    #     ax.set_title(titlearr[0], pad=0)
    # else:
    #     fig.suptitle(titlearr[0], y=0.99)
    fig.suptitle("\n".join(title.split(":")[::-1]))

    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        borderaxespad=0,
    )

#    fig.tight_layout()
#    fig.tight_layout(rect=[0, 0, 1, 0.75])
    fig.savefig(output_path, dpi=600, bbox_inches="tight")
    plt.close(fig)

    return True


def count_pie_chart(
    df: pl.DataFrame,
    group_column: str,
    title: str,
    output_path: Path,
    threshold: float = 0.005,
) -> bool:
    grouped = (
        df
        .filter(
            pl.col(group_column).is_not_null()
        )
        .group_by(group_column)
        .agg(
            pl.len().alias("value")
        )
    )

    return pie_chart(
        grouped,
        group_column,
        "value",
        title,
        output_path,
        threshold=threshold,
    )


def size_pie_chart(
    df: pl.DataFrame,
    group_column: str,
    title: str,
    output_path: Path,
    threshold: float = 0.01,
) -> bool:
    return pie_chart(
        df,
        group_column,
        "size_bytes",
        title,
        output_path,
        threshold=threshold,
    )


def organism_filter(
    df: pl.DataFrame,
    organism: str,
) -> pl.DataFrame:
    return df.filter(
        pl.col("organism") == organism
    )


def create_repository_charts(
    df: pl.DataFrame,
    output_base: Path,
) -> None:
    count_pie_chart(
        df,
        "repository_id",
        "Replicate count distribution by repository",
        output_base.with_suffix(
            ".repositories_by_replicates.png"
        ),
        threshold=0.005,
    )

    size_pie_chart(
        df,
        "repository_id",
        "Storage size footprint by repository",
        output_base.with_suffix(
            ".repositories_by_size.png"
        ),
        threshold=0.005,
    )

    count_pie_chart(
        df,
        "organism",
        "Replicate count distribution by organism",
        output_base.with_suffix(
            ".organism_by_replicates.png"
        ),
        threshold=0.005,
    )

    size_pie_chart(
        df,
        "organism",
        "Storage size footprint by organism",
        output_base.with_suffix(
            ".organism_by_size.png"
        ),
        threshold=0.005,
    )


def create_olap_cuts(
    df: pl.DataFrame,
    output_base: Path,
) -> None:
    candidate_columns = [
        "source_type",
        "material",
        "condition",
    ]

    columns = [
        c
        for c in candidate_columns
        if c in df.columns
    ]

    organisms = (
        df["organism"]
        .drop_nulls()
        .unique()
        .sort()
        .to_list()
    )

    for organism in organisms:
        organism_df = organism_filter(
            df,
            organism,
        )

        organism_slug = sanitize_filename(
            str(organism)
        )

        for column in columns:
            unique_count = (
                organism_df
                .select(
                    pl.col(column)
                    .drop_nulls()
                    .n_unique()
                )
                .item()
            )

            if unique_count <= 1:
                continue

            count_pie_chart(
                organism_df,
                column,
                (
                    rf"Organism $\mathtt{{{organism.replace('_', r'\_')}}}$:Replicate distribution by $\mathtt{{{column.replace('_', r'\_')}}}$"
                ),
                output_base.with_suffix(
                    f".{organism_slug}.{column}.replicates.png"
                ),
            )


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"usage: {sys.argv[0]} <output-base>",
            file=sys.stderr,
        )
        return 1

    output_base = Path(sys.argv[1])

    df = build_dataset()

    if df.is_empty():
        print(
            "no data available",
            file=sys.stderr,
        )
        return 1

    create_repository_charts(
        df,
        output_base,
    )

    create_olap_cuts(
        df,
        output_base,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
