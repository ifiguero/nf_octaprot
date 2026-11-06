process ALPHADIA_PREPARE {

    cpus 8
    memory '128 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_alphadia'

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
          path("alphadia.yaml"),
          path("report/speclib.hdf")

    script:
    """
    echo "[nf_alphadia_config] Start"

    echo "[nf_alphadia_config] FASTA:"
    ls -lh ${fasta}

    cat > alphadia.yaml <<EOF
search:
  target_ms1_tolerance: ${precursor}
  target_ms2_tolerance: ${fragment}
  min_peptide_length: ${min_len}
  max_peptide_length: ${max_len}

library_prediction:
  enabled: true
  enzyme: trypsin
  missed_cleavages: ${missed}

fdr:
  fdr: 0.01

general:
  thread_count: 8
EOF

    echo "[nf_alphadia_config] Configuration:"
    cat alphadia.yaml

    echo "[nf_alphadia_config] generating Spectral Library:"
    /usr/bin/time -v -o runtime.tsv alphadia \
        --config alphadia.yaml \
        --fasta "${fasta}" \
        --output report

    echo "[nf_alphadia_config] Finish"
    """
}


process ALPHADIA_PSM {

    cpus 8
    memory '128 GB'
    maxForks 3

    container 'dev.ilab.usm.cl/dia/nf_octaprot_alphadia'

    input:
    tuple path(fasta),
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label),
          path(alphadia_conf),
          path(speclib),
          val(replicate_id),
          path(mzml_gz)

    output:
    tuple val('alphadia'),
          val(replicate_id),
          val(fasta.baseName),
          val(grid_label),
          path("results.tsv"),
          path("runtime.tsv")

    script:
    """
    echo "[nf_alphadia] Start"

    echo "[nf_alphadia] Configuration:"
    cat "${alphadia_conf}"

    echo "[nf_alphadia] FASTA:"
    ls -lh "${fasta}"

    echo "[nf_alphadia] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_alphadia] Decompress mzML"

    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"

    echo "[nf_alphadia] Running AlphaDIA"

    /usr/bin/time -v -o "runtime.tsv" alphadia \
        --config "${alphadia_conf}" \
        --library "${speclib}" \
        --file "${mzml_gz.baseName}" \
        --output report

    echo "[nf_alphadia] Cleanup"
    rm -f "${mzml_gz.baseName}"

    echo "[nf_alphadia] Rename Output:"
    mv report/precursors.tsv "results.tsv"

    echo "[nf_alphadia] Finish"
    """
}
