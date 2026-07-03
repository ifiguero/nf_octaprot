workflow BATCH_SPLIT {

    batch_csv = Channel.fromPath(params.input_stage02)

    batch_parquet = REPLICATES_TO_PARQUET(batch_csv)

    BATCH_SPLIT_STRATIFIED(batch_parquet)
}

process REPLICATES_TO_PARQUET {
    publishDir "${params.silver_dir}/replicates", mode: 'copy', overwrite: true

    tag "$csv.baseName"

    input:
    path csv

    output:
    path "*.parquet"

    script:
    """
    021_load_replicates.py ${csv}
    """
}

process BATCH_SPLIT_STRATIFIED {
    publishDir "${params.dump_dir}/02batch", mode: 'copy', overwrite: true

    tag "$parquet.baseName"

    input:
    path parquet

    output:
    path "*.csv"

    script:
    """
    export SILVER_DIR="${params.silver_access}"
    022_batch_split.py ${parquet}
    """
}
