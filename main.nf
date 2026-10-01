#!/usr/bin/env nextflow

nextflow.enable.dsl=2

include { WORKFLOW_REPOSITORY } from './workflows/01repository.nf'
include { WORKFLOW_REPLICATES } from './workflows/02replicate.nf'
include { WORKFLOW_SEARCH } from './workflows/03search.nf'


def helpMessage() {
    log.info """
    ===================================================================
    OCTAPROT_NF - MULTI-STAGE WORKFLOW HELP
    ===================================================================
    Usage:
      nextflow run main.nf --stage <STAGE_NAME>

    Required Parameters:
      --stage [string]   Specify the pipeline stage to run.
           Available stages:
             - stage1 : Scrap Repositories present in '/input/stage1/*csv'
             - stage2 : Download samples present in '/input/stage2/*csv'
             - stage3 : Run peptide search for '/input/stage3/*fasta'

    Flags:
      --help             Display this help message and exit.

    Examples:
      nextflow run main.nf --stage stage1
      nextflow run main.nf --stage stage2
      nextflow run main.nf --stage stage3
    ===================================================================
    """.stripIndent()
}

workflow {
    // 1. Trigger help on --help flag or if params.stage was unset/invalid
    if (params.help || !params.stage) {
        helpMessage()
        exit 0
    }

    def selectedStage = params.stage ? params.stage.toString().toLowerCase() : ''

    // 2. Route to requested stage
    if (selectedStage == 'stage1') {
            WORKFLOW_REPOSITORY()
            }
    else if (selectedStage == 'stage2') {
            WORKFLOW_REPLICATES()
            }
    else if (selectedStage == 'stage3') {
            WORKFLOW_SEARCH()
            }
    else {
            log.error "Invalid stage specified: '${params.stage}'\n"
            helpMessage()
            exit 1
            }
}
