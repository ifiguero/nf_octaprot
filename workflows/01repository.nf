
include { REPOSITORY_TO_PARQUET; REPOSITORY_FILES_EXTRACT; REPOSITORY_SUMMARY } from '../modules/scrapping.nf'

workflow WORKFLOW_REPOSITORY {

    repositories_csv = Channel.fromPath(params.input_stage01)
    repositories_parquet = REPOSITORY_TO_PARQUET(repositories_csv).flatten()
    files_parquet = REPOSITORY_FILES_EXTRACT(repositories_parquet)
    REPOSITORY_SUMMARY(files_parquet)
}
