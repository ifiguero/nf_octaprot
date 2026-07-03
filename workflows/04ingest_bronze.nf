workflow INGEST_BRONZE {

    bronze_files = Channel.fromPath("${params.bronze_dir}/*")

    INGEST_BRONZE_METADATA(bronze_files)
}

process INGEST_BRONZE_METADATA {

    tag "$bronze.baseName"

    input:
    path bronze

    output:
    path "*.parquet"

    script:
    """
    041_ingest_bronze.py  ${bronze}
    """
}
