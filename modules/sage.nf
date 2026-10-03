process SAGE_CONFIG {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

    input:
    path fasta

    output:
    tuple path(fasta)

    script:
    """

    """
}

process SAGE_PSM {
    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

    input:
    tuple path(fasta),
          path(mzml_gz)

    output:
    path "*.tsv"

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
        "value": 20.0,
        "unit": "ppm"
    },
    "fragment_tol": {
        "value": 20.0,
        "unit": "ppm"
    },
    "enzyme": {
        "name": "trypsin",
        "missed_cleavages": 2
    },
    "search": {
        "generate_decoys": true
    }
}
EOF

    echo "[SAGE_PSM] Configuration:"
    cat sage.json

    echo "[SAGE_PSM] Running Sage"

    sage sage.json "${mzml_gz.baseName}" \
        --fasta "${fasta}" \
        --output_directory .

    echo "[SAGE_PSM] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[SAGE_PSM] Finish"
    """
}
