process DIANN_CONFIG {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_diann'

    input:
    path fasta

    output:
    tuple path(fasta), path("*.speclib")

    script:
    """
    echo "[nf_diann_config] Start"

    echo "[nf_diann_config] FASTA:"
    ls -lh "${fasta}"

    /usr/bin/time -v -o runtime.tsv diann --fasta ${fasta} --fasta-search --predictor --gen-spec-lib --threads 8 --out-lib ${fasta.baseName}.speclib --min-pep-len 5  --max-pep-len 50 --missed-cleavages 2 --unimod4

    echo "[nf_diann_config] Spectral Library:"
    ls -lh *.speclib

    echo "[nf_diann_config] Finish"
    """
}

process DIANN_PSM {

    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_diann'

    input:
    tuple path(fasta),
          path(speclib),
          val(id),
          path(mzml_gz)

    output:
    tuple val(id),
          path("${id}.results.parquet"),
          path("${id}.runtime.tsv")

    script:
    """
    echo "[nf_diann] Start"

    echo "[nf_diann] Spectral Library:"
    ls -lh "${speclib}"

    echo "[nf_diann] FASTA:"
    ls -lh "${fasta}"

    echo "[nf_diann] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_diann] Decompress mzML"
    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"

    echo "[nf_diann] Running DIA-NN"

    /usr/bin/time -v -o "${id}.runtime.tsv" diann --threads 8 --f "${mzml_gz.baseName}" --lib "${speclib}" --fasta "${fasta}" --out "${id}.results.parquet"

    echo "[nf_diann] Exit code: \$?"

    echo "[nf_diann] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[nf_diann] Finish"
    """
}
