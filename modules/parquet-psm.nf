process SAGE_SAVE_PSM {
    publishDir "${params.silver_dir}/psm/sage", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    032_save_psm.py --sage ${id} ${results}
    """
}


process DIANN_SAVE_PSM {
    publishDir "${params.silver_dir}/psm/diann", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    032_save_psm.py --diann ${id} ${results}
    """
}


process MSFRAGGER_SAVE_PSM {
    publishDir "${params.silver_dir}/psm/msfragger", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    032_save_psm.py --msfragger ${id} ${results}
    """
}


process ALPHADIA_SAVE_PSM {
    publishDir "${params.silver_dir}/psm/alphadia", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    032_save_psm.py --alphadia ${id} ${results}
    """
}



process SAGE_SAVE_RUNTIME {
    publishDir "${params.silver_dir}/psm_runtime/sage", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    033_save_time.py ${id} ${runtime}
    """
}


process DIANN_SAVE_RUNTIME {
    publishDir "${params.silver_dir}/psm_runtime/diann", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    033_save_time.py ${id} ${runtime}
    """
}


process MSFRAGGER_SAVE_RUNTIME {
    publishDir "${params.silver_dir}/psm_runtime/msfragger", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    033_save_time.py ${id} ${runtime}
    """
}


process ALPHADIA_SAVE_RUNTIME {
    publishDir "${params.silver_dir}/psm_runtime/alphadia", mode: 'copy', overwrite: true

    input:
    tuple val(id),
          path(results),
          path(runtime)

    output:
    path ("${id}.parquet")

    script:
    """
    033_save_time.py ${id} ${runtime}
    """
}
