workflow REPOSITORY_SCRAP {

    repositories_csv = Channel.fromPath(params.input_stage01)

    repositories_parquet = REPOSITORY_TO_PARQUET(repositories_csv).flatten()

    files_parquet = REPOSITORY_FILES_EXTRACT(repositories_parquet)

    REPOSITORY_SUMMARY(files_parquet)
}

process REPOSITORY_TO_PARQUET {
    publishDir "${params.silver_dir}/repositories", mode: 'copy'

    tag "$csv.baseName"

    input:
    path csv

    output:
    path "*.parquet"

    script:
    """
    011_repository_to_parquet.py ${csv}
    """
}

process REPOSITORY_FILES_EXTRACT {
    publishDir "${params.silver_dir}/files", mode: 'copy'
    maxForks 1

    input:
    path parquet

    output:
    path "*.parquet"

    script:
    """
    012_repository_scrap.py ${parquet}
    """
}

process REPOSITORY_SUMMARY {
    publishDir "${params.dump_dir}/01repo", mode: 'copy'

    input:
    path parquet

    output:
    path "*.csv"

    script:
    """
    013_repository_summary_csv.py ${parquet}
    """
}
