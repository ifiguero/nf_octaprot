nextflow.enable.dsl=2

include { WORKFLOW_SEARCH } from './workflows/03search.nf'

workflow {
    WORKFLOW_SEARCH()
}
