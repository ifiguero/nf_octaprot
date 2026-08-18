nextflow.enable.dsl=2

include { WORKFLOW_REPOSITORY } from './workflows/01repository'

workflow {
    WORKFLOW_REPOSITORY()
    }
