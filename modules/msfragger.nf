
process MSFRAGGER_PREPARE {
    cpus 8
    memory '64 GB'
    publishDir "${params.silver_dir}/fasta_peptide", mode: 'copy', pattern: "*.parquet"

    container 'dev.ilab.usm.cl/dia/nf_octaprot_msfragger'

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
          path("fragger.params"),
          path("${fasta}.1.prepared")

    script:
    """
    echo "[nf_msfragger_db] Start"

    echo "[nf_msfragger_db] FASTA"
    ls -lh "${fasta}"

    echo "[nf_msfragger_db] Creating parameters"

    cat > fragger.params <<'EOF'
                database_name = ${fasta}
                num_threads = 8

                precursor_mass_lower = -${precursor}
                precursor_mass_upper = ${precursor}
                precursor_mass_units = 1

                precursor_true_tolerance = ${precursor}
                precursor_true_units = 1

                fragment_mass_tolerance = ${fragment}
                fragment_mass_units = 1

                isotope_error = 0/1/2/3

                search_enzyme_name = trypsin
                search_enzyme_cutafter = KR
                search_enzyme_butnotafter = P

                num_enzyme_termini = 2
                allowed_missed_cleavage = ${missed}

                digest_min_length = ${min_len}
                digest_max_length = ${max_len}

                output_format = tsv_pepxml_pin
                output_report_topN = 1
    EOF

    sed -i 's/^[[:blank:]]*//' fragger.params

    echo "[nf_msfragger_db] Parameters:"
    cat fragger.params

    echo "[nf_msfragger_db] Building MSFragger peptide index"
    java -Xmx64g -jar /opt/msfragger/msfragger.jar fragger.params
    echo "[nf_msfragger_db] Index exit code: \$?"

    echo "[nf_msfragger_db] Database files:"
    ls -lah

    mv "${fasta}.1.pepindex" "${fasta}.1.prepared"

    echo "[nf_msfragger_db] Finish"
    """
}


process MSFRAGGER_PSM {
    cpus 8
    memory '128 GB'
    maxForks 4

    container 'dev.ilab.usm.cl/dia/nf_octaprot_msfragger'

    input:
    tuple path(fasta),
          val(precursor),
          val(fragment),
          val(missed),
          val(min_len),
          val(max_len),
          val(grid_label),
          path(fragger_params),
          path(pepindex),
          val(replicate_id),
          path(mzml_gz)

  output:
  tuple val('msfragger'),
        val(replicate_id),
        val(fasta.baseName),
        val(grid_label),
        path("results.tsv"),
        path("runtime.tsv")

    script:
    """
    echo "[nf_msfragger] Start"

    echo "[nf_msfragger] PARAMS:"
    cat "${fragger_params}"

    echo "[nf_msfragger] FASTA:"
    cp "${pepindex}" "${pepindex.baseName}.pepindex"
    ls -lh "${fasta}"
    ls -lh "${pepindex.baseName}*"

    echo "[nf_msfragger] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_msfragger] Decompress mzML"
    gzip -dc "${mzml_gz}" > "${mzml_gz.baseName}"
    echo "[nf_msfragger] Decompression exit code: \$?"

    echo "[nf_msfragger] MSFragger parameters:"
    cat "${fragger_params}"

    echo "[nf_msfragger] MSFragger search"

    /usr/bin/time -v -o "runtime.tsv" java -Xmx64g -jar /opt/msfragger/msfragger.jar "${fragger_params}" "${mzml_gz.baseName}"

    echo "[nf_msfragger] MSFragger exit code: \$?"

    echo "[nf_msfragger] Cleanup"
    rm -f "${mzml_gz.baseName}"

    echo "[nf_msfragger] Rename output:"
    mv "${replicate_id}.tsv" "results.tsv"

    echo "[nf_msfragger] Finish"
    """
}
