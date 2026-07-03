workflow NORMALIZE {

    datasets_csv = Channel.fromPath(params.input_stage03)
    dataset_parquet = DATASET_MANIFEST_TO_PARQUET(datasets_csv)
    DOWNLOAD_TRANSCODE_PUBLISH(dataset_parquet)
}

process DATASET_MANIFEST_TO_PARQUET {
    tag "$csv.baseName"

    input:
    path csv

    output:
    path "*.parquet"

    script:
    """
    031_batch_work_load.py ${csv}
    """
}

process DOWNLOAD_TRANSCODE_PUBLISH {

    input:
    path parquet

    output:
    path "*.mzML.gz"

    script:
    """
    032_download_transcode_bronze.py  ${parquet}
    """
}
