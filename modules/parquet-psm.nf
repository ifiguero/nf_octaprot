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
    032_save_psm.py \
        --software_id "${software_id}" \
        --replicate_id "${replicate_id}" \
        --results "${results}"
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
    033_save_time.py \
        --software_id "${software_id}" \
        --replicate_id "${replicate_id}" \
        --timing "${runtime}"
    """
}
