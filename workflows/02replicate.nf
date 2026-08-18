workflow WORKFLOW_REPLICATES {

    input_csv = Channel.fromPath(params.input_stage02)

    repository_parquet = LOAD_PARQUET(input_csv)

    replicate_ids = LIST_REPLICATES(repository_parquet).splitText().map { it.trim() }.filter { it }

    bronze_replicate = DOWNLOAD_TRANSCODE_PUBLISH(replicate_ids)
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
    publishDir "${params.bronze_dir}", mode: 'move', overwrite: true
    maxForks 1
//    errorStrategy 'retry'
//    maxRetries 3

    container 'ilabusm/nf_octaprot_transcode'

    input:
    val replicate_id

//    when:
//    !file("${params.bronze_dir}/${replicate_id}.mzML.gz", checkIfExists: true)

    output:
    path "${replicate_id}.mzML.gz"

//    script:
//    """
//    export SILVER_DIR="${params.silver_dir}"
//    023a_download_raw.py ${replicate_id}
//    read -r sample_path < stage/sample_filename.txt
//    echo "Raw file download at \${sample_path}"
//    wine msconvert --32 --filter 'peakPicking cwt snr=1 peakSpace=0.1 msLevel=1-' "\${sample_path}" -o stage/mzml/
//    echo "Converted file at stage/mzml/${replicate_id}.mzML"
//    gzip -9 -c stage/mzml/${replicate_id}.mzML > ${replicate_id}.mzML.gz
//    rm -rf stage
//    """

    script:
    """
    echo "[nf_transcode] Start"
    export SILVER_DIR="${params.silver_dir}"
    echo "[nf_transcode] SILVER_DIR: \${SILVER_DIR}"

    test -d \${SILVER_DIR}
    echo "[nf_transcode] test -d returned: \$?"

    023a_download_raw.py ${replicate_id}
    echo "[nf_transcode] Python returned: \$?"

    read -r sample_path < stage/sample_filename.txt
    echo "[nf_transcode] Raw file download at \${sample_path}"

    echo "[nf_transcode] Sample block log"
    ls -lah "\${sample_path}"
    file "\${sample_path}"
    echo "[nf_transcode] Sample block log end"

    echo "[nf_transcode] transcode log"
    wine msconvert \
        --32 \
        --filter 'peakPicking cwt snr=1 peakSpace=0.1 msLevel=1-' \
        "\${sample_path}" \
        -o stage/mzml/ \
        -v

    echo "[nf_transcode] transcode log end"

    echo "[nf_transcode] msconvert exit code: \$?"

    echo "[nf_transcode] Gzip"
    gzip -9 -c stage/mzml/${replicate_id}.mzML > ${replicate_id}.mzML.gz
    echo "[nf_transcode] gzip exit code: \$?"

    echo "[nf_transcode] Cleanup"
    rm -rf stage
    echo "[nf_transcode] Cleanup exit code: \$?"
    echo "[nf_transcode] Finish"
    """


}
