
process LOAD_REPLICATES {
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

process LIST_DIA_REPLICATES {

    input:
    path parquet

    output:
    stdout

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    031_get_replicates.py dia ${parquet}
    """
}

process LIST_DDA_REPLICATES {

    input:
    path parquet

    output:
    stdout

    script:
    """
    export SILVER_DIR="${params.silver_dir}"
    031_get_replicates.py dda ${parquet}
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


process LOAD_SAMPLE_METADATA {
    storeDir "${params.silver_dir}/sample_metadata"
    maxForks 1
    memory '4 GB'

    input:
    path mzml

    output:
    path "${mzml.getBaseName(2)}.parquet"

    script:
    """
    024_get_sample_metadata.py ${mzml}
    """
}

process LOAD_MS1_METADATA {
    storeDir "${params.silver_dir}/ms1_metadata"
    maxForks 1
    memory '8 GB'

    input:
    path mzml

    output:
    path "${mzml.getBaseName(2)}.parquet"

    script:
    """
    025_get_ms_metadata.py ${mzml} 1
    """
}

process LOAD_MS2_METADATA {
    storeDir "${params.silver_dir}/ms2_metadata"
    maxForks 3
    memory '8 GB'

    input:
    path mzml

    output:
    path "${mzml.getBaseName(2)}.parquet"

    script:
    """
    025_get_ms_metadata.py ${mzml} 2
    """
}

process LOAD_SPECTRA_INTENSITY_BINNING {
    storeDir "${params.silver_dir}/spec_intensity"
    maxForks 3
    memory '16 GB'

    input:
    path mzml

    output:
    path "${mzml.getBaseName(2)}.parquet"

    script:
    """
    026_get_intensity_distribution.py ${mzml} linear
    """
}

process LOAD_SPECTRA_PERCENTILE_BINNING {
    storeDir "${params.silver_dir}/spec_percentile"
    maxForks 3
    memory '16 GB'

    input:
    path mzml

    output:
    path "${mzml.getBaseName(2)}.parquet"

    script:
    """
    026_get_intensity_distribution.py ${mzml} percentile
    """
}
