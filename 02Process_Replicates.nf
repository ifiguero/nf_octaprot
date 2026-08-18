nextflow.enable.dsl=2

include { WORKFLOW_REPLICATES } from './workflows/02replicate'

workflow {
    WORKFLOW_REPLICATES()
}
