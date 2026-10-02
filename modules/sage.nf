process SAGE_CONFIG {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

    input:
    path fasta

    output:
    tuple path("sage.config.toml"),
          path(fasta)

    script:
    """
    echo "[nf_sage_config] Start"

    echo "[nf_sage_config] FASTA:"
    ls -lh "${fasta}"

    cat > sage.config.toml <<EOF
[database]
fasta = "${fasta}"

[precursor_tol]
value = 20.0
unit = "ppm"

[fragment_tol]
value = 20.0
unit = "ppm"

[enzyme]
name = "trypsin"
missed_cleavages = 2

[search]
generate_decoys = true
EOF

    echo "[nf_sage_config] Configuration:"
    cat sage.config.toml

    echo "[nf_sage_config] Finish"
    """
}


process SAGE_PSM {

    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_sage'

    input:
    tuple path(sage_config),
          path(fasta),
          path(mzml_gz)

    output:
    path "*.tsv"

    script:
    """
    echo "[nf_sage] Start"

    echo "[nf_sage] Configuration:"
    cat "${sage_config}"

    echo "[nf_sage] FASTA:"
    ls -lh "${fasta}"

    echo "[nf_sage] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_sage] Decompress mzML"
    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"

    echo "[nf_sage] Running Sage"

    sage \
        "${sage_config}"

    echo "[nf_sage] Sage exit code: \\$?"

    echo "[nf_sage] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[nf_sage] Finish"
    """
}
