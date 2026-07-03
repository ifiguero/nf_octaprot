nextflow.enable.dsl=2

include { REPOSITORY_SCRAP } from './workflows/01repository_scrap'
include { BATCH_SPLIT      } from './workflows/02batch_split'
include { NORMALIZE        } from './workflows/03normalize'
include { INGEST_BRONZE    } from './workflows/04ingest_bronze'
include { DUMP            } from './workflows/99dump'

workflow {
    REPOSITORY_SCRAP()
    BATCH_SPLIT()
//    NORMALIZE()
//    INGEST_BRONZE()
    DUMP()
}
