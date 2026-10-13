
include { LOAD_REPLICATES; LIST_REPLICATES; LOAD_SAMPLE_METADATA; LOAD_MS1_METADATA; LOAD_MS2_METADATA } from '../modules/parquet.nf'
include { LOAD_SPECTRA_INTENSITY_BINNING; LOAD_SPECTRA_PERCENTILE_BINNING } from '../modules/parquet.nf'
include { DOWNLOAD_TRANSCODE_PUBLISH } from '../modules/transcode.nf'

include { GOLD_TEX_SUMMARY; GOLD_REPLICATES } from '../modules/gold.nf'

include { REPLICATES_BREAKDOWN} from '../modules/plots.nf'
include { COMPARATIVE_SPECTRA_MS1; COMPARATIVE_SPECTRA_MS2; SPECTRA_BINNING; SPECTRA_PERCENTILE} from '../modules/plots.nf'

workflow WORKFLOW_REPLICATES {

    input_csv = Channel.fromPath(params.input_stage02)

    repository_parquet = LOAD_REPLICATES(input_csv)


    replicate_ids = LIST_REPLICATES(repository_parquet).splitText().map { it.trim() }.filter { it }

    bronze_replicate = DOWNLOAD_TRANSCODE_PUBLISH(replicate_ids)

    sample_metadata = LOAD_SAMPLE_METADATA(bronze_replicate)
    ms1_metadata = LOAD_MS1_METADATA(bronze_replicate)
    ms2_metadata = LOAD_MS2_METADATA(bronze_replicate)

    gold_parquet = GOLD_REPLICATES( sample_metadata.mix(ms1_metadata, ms2_metadata).collect() )

    GOLD_TEX_SUMMARY( gold_parquet )

/*
    spectra_binning = LOAD_SPECTRA_INTENSITY_BINNING(bronze_replicate)
    spectra_percentile = LOAD_SPECTRA_PERCENTILE_BINNING(bronze_replicate)
    SPECTRA_BINNING(spectra_binning)
    SPECTRA_PERCENTILE(spectra_percentile)
    REPLICATES_BREAKDOWN(repository_parquet.collect())
    COMPARATIVE_SPECTRA_MS1(spectra_binning.collect())
    COMPARATIVE_SPECTRA_MS2(spectra_binning.collect())
*/
}
