include { LIST_REPLICATES } from '../modules/parquet.nf'
include { MSFRAGGER_CONFIG; MSFRAGGER_PSM } from '../modules/msfragger.nf'
include { DIANN_CONFIG; DIANN_PSM } from '../modules/diann.nf'
include { ALPHADIA_CONFIG; ALPHADIA_PSM } from '../modules/alphadia.nf'
include { SAGE_CONFIG; SAGE_PSM } from '../modules/sage.nf'

workflow WORKFLOW_SEARCH {


    fasta_files = Channel.fromPath(params.input_fasta)

    replicates_ch = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")
    mzml_gz_ch = LIST_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { file("${params.bronze_dir}/${it}.mzML.gz") }


    MSFRAGGER_SEARCH(fasta_files, mzml_gz_ch)
    DIANN_SEARCH(fasta_files, mzml_gz_ch)
    SAGE_SEARCH(fasta_files, mzml_gz_ch)
    ALPHADIA_SEARCH(fasta_files, mzml_gz_ch)

}

workflow MSFRAGGER_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = MSFRAGGER_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      MSFRAGGER_PSM( job_queue )
}


workflow DIANN_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = DIANN_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      DIANN_PSM( job_queue )
}

workflow ALPHADIA_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = ALPHADIA_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      ALPHADIA_PSM( job_queue )
}


workflow SAGE_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = SAGE_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      SAGE_PSM( job_queue )
}
