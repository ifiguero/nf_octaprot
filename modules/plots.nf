
process REPLICATES_BREAKDOWN {
    publishDir "${params.dump_dir}/99sqldump", mode: 'copy'

    input:
    path parquet_files

    output:
    path "*.png"

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    992_dump_breakdown.py
    """
}

process SPECTRA_PERCENTILE {
    storeDir "${params.dump_dir}/png_percentile"
    maxForks 3
    memory '16 GB'

    input:
    path parquet

    output:
    path "${parquet.baseName}.png"

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    027a_png_intensity_distribution.py ${parquet} percentile
    """
}

process SPECTRA_BINNING {
    storeDir "${params.dump_dir}/png_binning"
    maxForks 3
    memory '16 GB'

    input:
    path parquet

    output:
    path "${parquet.baseName}.png"

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    027a_png_intensity_distribution.py ${parquet} linear
    """
}

process COMPARATIVE_SPECTRA_MS1 {
    storeDir "${params.dump_dir}/comparativa"
    memory '16 GB'

    input:
    path spectra_files

    output:
    path("scan_intensity_profiles_ms1.png")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    027b_png_intensity_lvl.py 1
    """
}

process COMPARATIVE_SPECTRA_MS2 {
    storeDir "${params.dump_dir}/comparativa"
    memory '16 GB'

    input:
    path spectra_files

    output:
    path("scan_intensity_profiles_ms2.png")

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    027b_png_intensity_lvl.py 2
    """
}
