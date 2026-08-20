workflow WORKFLOW_REPLICATES {

    input_csv = Channel.fromPath(params.input_stage02)

    repository_parquet = LOAD_PARQUET(input_csv)

    replicate_ids = LIST_REPLICATES(repository_parquet).splitText().map { it.trim() }.filter { it }

    bronze_replicate = DOWNLOAD_TRANSCODE_PUBLISH(replicate_ids)

    LOAD_SAMPLE_METADATA(bronze_replicate)
    LOAD_MS1_METADATA(bronze_replicate)
    LOAD_MS2_METADATA(bronze_replicate)
}

process LOAD_PARQUET {
    publishDir "${params.silver_dir}/replicates", mode: 'copy', overwrite: true

    input:
    path csv

    output:
    path "*.parquet"

    script:
    """
    021_load_replicates.py ${csv}
    """
}

process LIST_REPLICATES {

    input:
    path parquet

    output:
    stdout

    script:
    """
    022_get_replicates.py ${parquet}
    """
}

process DOWNLOAD_TRANSCODE_PUBLISH {
    storeDir "${params.bronze_dir}"
    maxForks 3
    cpus 8
    memory '16 GB'

    container 'ilabusm/nf_octaprot_transcode'

    input:
    val replicate_id

    output:
    path "${replicate_id}.mzML.gz"

    script:
    """
    echo "[nf_transcode] Start"
    export SILVER_DIR="${params.silver_dir}"
    echo "[nf_transcode] SILVER_DIR: \${SILVER_DIR}"

    test -d \${SILVER_DIR}
    echo "[nf_transcode] test -d returned: \$?"

    echo "[nf_transcode] Python Sample Downloader log"
    023a_download_raw.py ${replicate_id}
    echo "[nf_transcode] Python Sample Downloader log"

    echo "[nf_transcode] Python returned: \$?"

    read -r sample_path < stage/sample_filename.txt

    echo "[nf_transcode] Sample file information log"
    du -hs \${sample_path}*
    file \${sample_path}
    echo "[nf_transcode] Sample file information log end"

    echo "[nf_transcode] transcode log"
    wine msconvert \
        --32 \
        --filter 'peakPicking cwt snr=1 peakSpace=0.1 msLevel=1-' \
        "\${sample_path}" \
        -o stage/mzml/ \
        -v

    echo "[nf_transcode] transcode log end"

    echo "[nf_transcode] transcode exit code: \$?"

    echo "[nf_transcode] Gzip"
    gzip -9 -c stage/mzml/${replicate_id}.mzML > ${replicate_id}.mzML.gz
    echo "[nf_transcode] Gzip exit code: \$?"

    echo "[nf_transcode] Cleanup"
    rm -rf stage
    echo "[nf_transcode] Cleanup exit code: \$?"
    echo "[nf_transcode] Finish"
    """
}


process LOAD_SAMPLE_METADATA {
    storeDir "${params.silver_dir}/sample_metadata"

    input:
    path mzml

    output:
    path "${mzml.baseName}.parquet"

    script:
    """
    024_get_sample_metadata.py ${mzml} ${mzml.baseName}
    """
}



process LOAD_MS1_METADATA {
    storeDir "${params.silver_dir}/ms1_metadata"

    input:
    path mzml

    output:
    path "${mzml.baseName}.parquet"

    script:
    """
    025_get_ms_metadata.py ${mzml} 1
    """
}

process LOAD_MS2_METADATA {
    storeDir "${params.silver_dir}/ms2_metadata"

    input:
    path mzml

    output:
    path "${mzml.baseName}.parquet"

    script:
    """
    025_get_ms_metadata.py ${mzml} 2
    """
}
