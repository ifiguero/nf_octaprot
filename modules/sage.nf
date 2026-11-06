process SAGE_PREPARE {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

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
          val(grid_label)

    script: // placeholder
    """
    test -f "${fasta}"
    """
}

process SAGE_PSM {
    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

    input:
    tuple path(fasta),
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label),
          val(replicate_id),
          path(mzml_gz)

    output:
    tuple val('sage'),
          val(replicate_id),
          val(fasta.baseName),
          val(grid_label),
          path("results.tsv"),
          path("runtime.tsv")

    script:
    """
    echo "[SAGE_PSM] Start"

    echo "[SAGE_PSM] FASTA:"
    ls -lh "${fasta}"

    echo "[SAGE_PSM] mzML:"
    ls -lh "${mzml_gz}"

    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"

    cat > sage.json <<EOF
    {
      "database": {
        "fasta": "${fasta}"
      },
      "precursor_tol": {
        "ppm": [-${precursor}, ${precursor}]
      },
      "fragment_tol": {
        "ppm": [-${fragment}, ${fragment}]
      },
      "enzyme": {
        "missed_cleavages": ${missed},
        "min_len": ${min_len},
        "max_len": ${max_len}
      },
      "search": {
        "generate_decoys": true
      }
    }
EOF

    echo "[SAGE_PSM] Configuration:"
    cat sage.json

    echo "[SAGE_PSM] Running Sage"

    /usr/bin/time -v -o "runtime.tsv" sage sage.json "${mzml_gz.baseName}" \
        --fasta "${fasta}" \
        --output_directory .

    echo "[SAGE_PSM] Cleanup"
    rm -f "${mzml_gz.baseName}"

    echo "[SAGE_PSM] Rename Output:"
    mv results.sage.tsv "results.tsv"

    echo "[SAGE_PSM] Finish"
    """
}
