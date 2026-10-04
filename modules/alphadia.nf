process ALPHADIA_CONFIG {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_alphadia'

    input:
    path fasta

    output:
    tuple path("alphadia.yaml"),
          path(fasta)

    script:
    """
    echo "[nf_alphadia_config] Start"

    echo "[nf_alphadia_config] FASTA:"
    ls -lh ${fasta}

    cat > alphadia.yaml <<EOF
search:
  target_ms1_tolerance: 20
  target_ms2_tolerance: 20

library_prediction:
  enabled: true
  missed_cleavages: 2

fdr:
  fdr: 0.01

general:
  thread_count: 8

search_output:
  file_format: "tsv"
  precursor_level_lfq: true
  peptide_level_lfq: true
EOF

    echo "[nf_alphadia_config] Configuration:"
    cat alphadia.yaml

    echo "[nf_alphadia_config] Finish"
    """
}


process ALPHADIA_PSM {

    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_alphadia'

    input:
    tuple path(alphadia_conf),
          path(fasta),
          path(mzml_gz)

    output:
    path "*.tsv"

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

    /usr/bin/time -v -o runtime.tsv alphadia \
        --config "${alphadia_conf}" \
        --fasta "${fasta}" \
        --file "${mzml_gz.baseName}" \
        --output report

    echo "[nf_alphadia] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[nf_alphadia] Finish"
    """
}
