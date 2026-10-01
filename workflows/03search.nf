include { LIST_REPLICATES } from '../modules/parquet.nf'
include { FASTA_MSFRAGGER_INDEX; MSFRAGGER_PSM } from '../modules/msfragger.nf'

workflow WORKFLOW_SEARCH {


    fasta_files = Channel.fromPath(params.input_fasta)

    replicates_ch = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")
    mzml_gz_ch = LIST_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { file("${params.bronze_dir}/${it}.mzML.gz") }


    msfragger_fasta_ch = FASTA_MSFRAGGER_INDEX( fasta_files )
    msfragger_queue = msfragger_fasta_ch.combine( mzml_gz_ch )

    MSFRAGGER_PSM( msfragger_queue )


}
