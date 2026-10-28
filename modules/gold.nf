
process GOLD_REPLICATES {
    publishDir "${params.gold_dir}", mode: 'copy', overwrite: true
    memory '32 GB'

    input:
    val all_done

    output:
    path "replicates_gold.parquet"

    script:
    """
    export BRONZE_DIR="${params.bronze_dir}"
    export SILVER_DIR="${params.silver_dir}"
    097_replicate_silver2gold.py
    """
}


process GOLD_TEX_SUMMARY {
    publishDir "${params.dump_dir}/097_GoldReport", mode: 'copy', overwrite: true

    input:
    path input_parquet

    output:
    path "replicates_report.tex"

    script:
    """
    export GOLD_DIR="${params.gold_dir}"
    098_report_latex.py
    """
}
