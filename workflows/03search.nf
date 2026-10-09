include { LIST_DDA_REPLICATES; LIST_DIA_REPLICATES } from '../modules/parquet.nf'
include { SAGE_SAVE_PSM; DIANN_SAVE_PSM; ALPHADIA_SAVE_PSM; MSFRAGGER_SAVE_PSM } from '../modules/parquet-psm.nf'
include { SAGE_SAVE_RUNTIME; DIANN_SAVE_RUNTIME; ALPHADIA_SAVE_RUNTIME; MSFRAGGER_SAVE_RUNTIME } from '../modules/parquet-psm.nf'
include { MSFRAGGER_CONFIG; MSFRAGGER_PSM } from '../modules/msfragger.nf'
include { DIANN_CONFIG; DIANN_PSM } from '../modules/diann.nf'
include { ALPHADIA_CONFIG; ALPHADIA_PSM } from '../modules/alphadia.nf'
include { SAGE_CONFIG; SAGE_PSM } from '../modules/sage.nf'

workflow WORKFLOW_SEARCH {


    fasta_files = Channel.fromPath(params.input_fasta)

    replicates_ch = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")
    mzml_gz_dia = LIST_DIA_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { id -> tuple(id, file("${params.bronze_dir}/${id}.mzML.gz")) }
    mzml_gz_dda = LIST_DDA_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { id -> tuple(id, file("${params.bronze_dir}/${id}.mzML.gz")) }


    MSFRAGGER_SEARCH(fasta_files, mzml_gz_dia)
    DIANN_SEARCH(fasta_files, mzml_gz_dia)
    SAGE_SEARCH(fasta_files, mzml_gz_dia)
    ALPHADIA_SEARCH(fasta_files, mzml_gz_dia)


    MSFRAGGER_SEARCH(fasta_files, mzml_gz_dda)
    DIANN_SEARCH(fasta_files, mzml_gz_dda)
    SAGE_SEARCH(fasta_files, mzml_gz_dda)
//    ALPHADIA_SEARCH(fasta_files, mzml_gz_dda)

}

workflow MSFRAGGER_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = MSFRAGGER_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      if (params.test) {
          job_queue = job_queue.take(1)
      }
      psm_results = MSFRAGGER_PSM( job_queue )
      MSFRAGGER_SAVE_PSM ( psm_results )
      MSFRAGGER_SAVE_RUNTIME ( psm_results )

}


workflow DIANN_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = DIANN_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      if (params.test) {
          job_queue = job_queue.take(1)
      }
      psm_results = DIANN_PSM( job_queue )
      DIANN_SAVE_PSM ( psm_results )
      DIANN_SAVE_RUNTIME ( psm_results )

}

workflow ALPHADIA_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = ALPHADIA_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      if (params.test) {
          job_queue = job_queue.take(1)
      }
      psm_results = ALPHADIA_PSM( job_queue )
      ALPHADIA_SAVE_PSM ( psm_results )
      ALPHADIA_SAVE_RUNTIME ( psm_results )


}


workflow SAGE_SEARCH {
    take:
      fasta_files
      mzml_gz

    main:
      config_ch = SAGE_CONFIG( fasta_files )
      job_queue = config_ch.combine( mzml_gz )
      if (params.test) {
          job_queue = job_queue.take(1)
      }
      psm_results = SAGE_PSM( job_queue )
      SAGE_SAVE_PSM ( psm_results )
      SAGE_SAVE_RUNTIME ( psm_results )

}
