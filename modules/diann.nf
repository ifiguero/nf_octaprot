process DIANN_CONFIG {

    cpus 8
    memory '16 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_diann'

    input:
    path fasta

    output:
    tuple path("diann.conf"),
          path(fasta)

    script:
    """
    echo "[nf_diann_config] Start"

    echo "[nf_diann_config] FASTA:"
    ls -lh "${fasta}"

    cat > diann.conf <<EOF
--threads 8
--fasta ${fasta}
--cut K*,R*
--missed-cleavages 2
--mass-acc 20
--mass-acc-ms1 20
--matrices
--qvalue 0.01
--gen-spec-lib
EOF

    echo "[nf_diann_config] Configuration:"
    cat diann.conf

    echo "[nf_diann_config] Finish"
    """
}

process DIANN_PSM {

    cpus 8
    memory '64 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_diann'

    input:
    tuple path(diann_conf),
          path(fasta),
          path(mzml_gz)

    output:
    path "*.tsv"

    script:
    """
    echo "[nf_diann] Start"

    echo "[nf_diann] Configuration:"
    cat "${diann_conf}"

    echo "[nf_diann] FASTA:"
    ls -lh "${fasta}"

    echo "[nf_diann] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_diann] Decompress mzML"
    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"

    echo "[nf_diann] Running DIA-NN"

    diann \\
        --threads ${task.cpus} \\
        --fasta "${fasta}" \\
        --f "${mzml_gz.baseName}" \\
        --out report.tsv \\
        --qvalue 0.01 \\
        --matrices \\
        --gen-spec-lib

    echo "[nf_diann] Exit code: \$?"

    echo "[nf_diann] Output:"
    ls -lah

    rm -f "${mzml_gz.baseName}"

    echo "[nf_diann] Finish"
    """
}
