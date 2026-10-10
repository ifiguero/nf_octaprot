include { LIST_DDA_REPLICATES; LIST_DIA_REPLICATES } from '../modules/parquet.nf'


include { MSFRAGGER_SEARCH as MSFRAGGER_SEARCH_DDA; MSFRAGGER_SEARCH as MSFRAGGER_SEARCH_DIA } from '../03search-subworkflows.nf'
include { DIANN_SEARCH as DIANN_SEARCH_DDA; DIANN_SEARCH as DIANN_SEARCH_DIA } from '../03search-subworkflows.nf'
include { SAGE_SEARCH as SAGE_SEARCH_DDA; SAGE_SEARCH as SAGE_SEARCH_DIA } from '../03search-subworkflows.nf'
include { ALPHADIA_SEARCH as ALPHADIA_SEARCH_DDA; ALPHADIA_SEARCH as ALPHADIA_SEARCH_DIA } from '../03search-subworkflows.nf'


workflow WORKFLOW_SEARCH {


    fasta_files = Channel.fromPath(params.input_fasta)

    replicates_ch = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")
    mzml_gz_dia = LIST_DIA_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { id -> tuple(id, file("${params.bronze_dir}/${id}.mzML.gz")) }
    mzml_gz_dda = LIST_DDA_REPLICATES(replicates_ch).splitText().map { it.trim() }.filter { it }.map { id -> tuple(id, file("${params.bronze_dir}/${id}.mzML.gz")) }


    MSFRAGGER_SEARCH_DDA(fasta_files, mzml_gz_dia)
    DIANN_SEARCH_DDA(fasta_files, mzml_gz_dia)
    SAGE_SEARCH_DDA(fasta_files, mzml_gz_dia)
//    ALPHADIA_SEARCH_DDA(fasta_files, mzml_gz_dia)


    MSFRAGGER_SEARCH_DIA(fasta_files, mzml_gz_dda)
    DIANN_SEARCH_DIA(fasta_files, mzml_gz_dda)
    SAGE_SEARCH_DIA(fasta_files, mzml_gz_dda)
    ALPHADIA_SEARCH_DIA(fasta_files, mzml_gz_dda)

}
