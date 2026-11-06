process DIANN_PREPARE {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_diann'

    input:
    tuple path(fasta),
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label)

    output:
    tuple path(fasta),
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label),
          path("*.speclib")

    script:
    """
    echo "[nf_diann_config] Start"

    echo "[nf_diann_config] FASTA:"
    ls -lh "${fasta}"

    diann --fasta ${fasta} --fasta-search --predictor --gen-spec-lib --threads 8 --out-lib ${fasta.baseName}.speclib --min-pep-len ${min_len}  --max-pep-len ${max_len} --missed-cleavages ${missed} --unimod4

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
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label),
          path(speclib),
          val(replicate_id),
          path(mzml_gz)

    output:
    tuple val('diann'),
          val(replicate_id),
          val(fasta.baseName),
          val(grid_label),
          path("results.parquet"),
          path("runtime.tsv")


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

    /usr/bin/time -v -o "runtime.tsv" diann --threads 8 --f "${mzml_gz.baseName}" --lib "${speclib}" --fasta "${fasta}"  --mass-acc ${precursor}  --mass-acc-ms2 ${fragment} --out "results.parquet"

    echo "[nf_diann] Exit code: \$?"

    echo "[nf_diann] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[nf_diann] Finish"
    """
}
