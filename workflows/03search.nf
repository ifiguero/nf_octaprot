include { LIST_REPLICATES } from './02replicate.nf'

workflow WORKFLOW_SEARCH {


    fasta_files = Channel.fromPath(params.input_fasta)

    replicates_ch = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")
    mzml_gz_ch = LIST_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { file("${params.silver_dir}/${it}.mzML.gz") }


    msfragger_fasta_ch = FASTA_MSFRAGGER_INDEX( fasta_files )
    msfragger_queue = msfragger_fasta_ch.combine( mzml_gz_ch )

    MSFRAGGER_PSM( msfragger_queue )


}


process FASTA_MSFRAGGER_INDEX {
    cpus 8
    memory '64 GB'
    publishDir "${params.silver_dir}/fasta_peptide", mode: 'copy', pattern: "*.parquet"

    container 'dev.ilab.usm.cl/dia/nf_octaprot_msfragger'

    input:
    path fasta

    output:
    tuple path("fragger.params"),
          path(fasta),
          path("${fasta}.1.pepindex")




    script:
    """
    echo "[nf_msfragger_db] Start"

    echo "[nf_msfragger_db] FASTA"
    ls -lh "${fasta}"

    echo "[nf_msfragger_db] Creating parameters"

    cat > fragger.params <<'EOF'
                database_name = ${fasta}
                num_threads = 8

                precursor_mass_lower = -20
                precursor_mass_upper = 20
                precursor_mass_units = 1

                precursor_true_tolerance = 20
                precursor_true_units = 1

                fragment_mass_tolerance = 20
                fragment_mass_units = 1

                isotope_error = 0/1/2/3

                search_enzyme_name = trypsin
                search_enzyme_cutafter = KR
                search_enzyme_butnotafter = P

                num_enzyme_termini = 2
                allowed_missed_cleavage = 2

                output_format = tsv_pepxml_pin
                output_report_topN = 1
    EOF

    sed -i 's/^[[:blank:]]*//' fragger.params

    echo "[nf_msfragger_db] Parameters:"
    cat fragger.params

    echo "[nf_msfragger_db] Building MSFragger peptide index"
    java -Xmx32g -jar /opt/msfragger/msfragger.jar fragger.params
    echo "[nf_msfragger_db] Index exit code: \\$?"

    echo "[nf_msfragger_db] Database files:"
    ls -lah

    echo "[nf_msfragger_db] Finish"
    """
}


process MSFRAGGER_PSM {
    cpus 8
    memory '64 GB'

    container 'dev.ilab.usm.cl/dia/nf_octaprot_msfragger'

    input:
    tuple path(fragger_params), path(fasta), path(pepindex), path(mzml_gz)

    output:
    path "*.tsv"
    path "*.pepXML"
    path "*.pin"

    script:
    """
    echo "[nf_msfragger] Start"

    echo "[nf_msfragger] PARAMS:"
    cat "${fragger_params}"

    echo "[nf_msfragger] FASTA:"
    ls -lh "${fasta}"
    ls -lh "${pepindex}"

    echo "[nf_msfragger] mzML:"
    ls -lh "${mzml_gz}"

    echo "[nf_msfragger] Decompress mzML"
    gzip -dc "${mzml_gz}" > "${mzml_gz.getBaseName}"
    echo "[nf_msfragger] Decompression exit code: \\$?"

    echo "[nf_msfragger] MSFragger parameters:"
    cat "${fragger_params}"

    echo "[nf_msfragger] MSFragger search"

    java -Xmx64g -jar /opt/msfragger/msfragger.jar "${fragger_params}" "${mzml_gz.getBaseName}"

    echo "[nf_msfragger] MSFragger exit code: \\$?"

    echo "[nf_msfragger] Search output:"
    ls -lah

    echo "[nf_msfragger] Cleanup"
    rm -f "${mzml_gz.getBaseName}"

    echo "[nf_msfragger] Finish"
    """
}
