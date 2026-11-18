process SAVE_PSM {

    publishDir {
        "${params.silver_dir}/psm/${fasta_id}/${grid_label}"
    }, mode: 'copy', overwrite: true

    input:
        tuple val(software_id),
              val(replicate_id),
              val(fasta_id),
              val(grid_label),
              path(results),
              path(runtime)

    output:
        path("${software_id}.${replicate_id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    032_save_psm.py "${software_id}" "${replicate_id}" "${results}"
    """
}



process SAVE_RUNTIME {

    publishDir {
        "${params.silver_dir}/psm_runtime/${fasta_id}/${grid_label}"
    }, mode: 'copy', overwrite: true

    input:
        tuple val(software_id),
              val(replicate_id),
              val(fasta_id),
              val(grid_label),
              path(results),
              path(runtime)

    output:
        path("${software_id}.${replicate_id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    033_save_time.py "${software_id}" "${replicate_id}" "${runtime}"
    """
}
