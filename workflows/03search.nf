include { LIST_DDA_REPLICATES; LIST_DIA_REPLICATES } from '../modules/parquet.nf'
include { SAVE_RUNTIME; SAVE_PSM } from '../modules/parquet-psm.nf'
include { MSFRAGGER_PREPARE; MSFRAGGER_PSM } from '../modules/msfragger.nf'
include { DIANN_PREPARE; DIANN_PSM } from '../modules/diann.nf'
include { ALPHADIA_PREPARE; ALPHADIA_PSM } from '../modules/alphadia.nf'
include { SAGE_PREPARE; SAGE_PSM } from '../modules/sage.nf'


workflow WORKFLOW_SEARCH {

    if (!(params.search_mode in ['wide', 'deep'])) {
        error """
        Invalid search_mode: '${params.search_mode}'.
        Valid values are: 'wide', 'deep'.
        """
    }

   //* 1. FASTA INPUT
    fasta_files = Channel.fromPath(params.input_fasta)


   //* 2. PARAMETER GRID
    parameter_grid = params.precursor_tol.collectMany { precursor ->
        params.fragment_tol.collectMany { fragment ->
            params.missed_cleavages.collectMany { missed ->
                params.min_peptide_len.collectMany { min_len ->
                    params.max_peptide_len.collect { max_len ->

                        def label = "p${precursor}_f${fragment}_c${missed}_n${min_len}_x${max_len}"

                        tuple(
                            precursor,
                            fragment,
                            missed,
                            min_len,
                            max_len,
                            label
                        )
                    }
                }
            }
        }
    }

    //if doing a deep search, then take the first only

    active_grid = params.search_mode == 'deep'
        ? parameter_grid.take(1)
        : parameter_grid

    config_ch = fasta_files.combine(active_grid)


    //* 3. Replicate channel
    replicate_parquets = Channel.fromPath("${params.silver_dir}/replicates/*.parquet")

    dia_ids = LIST_DIA_REPLICATES(replicate_parquets)
    dda_ids = LIST_DDA_REPLICATES(replicate_parquets)

     //* 4. Mode selection

    if (params.search_mode == 'wide') {
        // Wide parameter exploration: Single sample, MSFragger only.
        mzml_dia = dia_ids
            .map { ids_file ->

                def replicate_id = ids_file.text
                    .readLines()
                    .collect { it.trim() }
                    .find { it }

                if (!replicate_id)
                    return null

                tuple(replicate_id, file("${params.bronze_dir}/${replicate_id}.mzML.gz"))
            }
            .filter { it != null }

        mzml_dda = dda_ids
            .map { ids_file ->

                def replicate_id = ids_file.text
                    .readLines()
                    .collect { it.trim() }
                    .find { it }

                if (!replicate_id)
                    return null

                tuple(replicate_id, file("${params.bronze_dir}/${replicate_id}.mzML.gz"))
            }
            .filter { it != null }

        MSFRAGGER_SEARCH(config_ch, mzml_dia, mzml_dda)

    } else {
        // Deep execution: all enabled engines.
        mzml_dia = dia_ids
            .splitText()
            .map { it.trim() }
            .filter { it }
            .map { replicate_id ->
                tuple(replicate_id, file("${params.bronze_dir}/${replicate_id}.mzML.gz"))
            }

        mzml_dda = dda_ids
            .splitText()
            .map { it.trim() }
            .filter { it }
            .map { replicate_id ->
                tuple(replicate_id, file("${params.bronze_dir}/${replicate_id}.mzML.gz"))
            }

        MSFRAGGER_SEARCH(config_ch, mzml_dia, mzml_dda)
        DIANN_SEARCH(config_ch, mzml_dia, mzml_dda)
        SAGE_SEARCH(config_ch, mzml_dia, mzml_dda)
        ALPHADIA_SEARCH(config_ch, mzml_dia)
    }
}

workflow MSFRAGGER_SEARCH {

    take:
        config_ch
        mzml_1_ch
        mzml_2_ch

    main:
        prepared_ch = MSFRAGGER_PREPARE(config_ch)

        mzml_ch = mzml_1_ch.concat(mzml_2_ch)

        job_queue = prepared_ch.combine(mzml_ch)

        psm_results = MSFRAGGER_PSM(job_queue)

        SAVE_PSM(psm_results)

        SAVE_RUNTIME(psm_results)
}

workflow DIANN_SEARCH {

    take:
        config_ch
        mzml_1_ch
        mzml_2_ch

    main:
        prepared_ch = DIANN_PREPARE(config_ch)

        mzml_ch = mzml_1_ch.concat(mzml_2_ch)

        job_queue = prepared_ch.combine(mzml_ch)

        psm_results = DIANN_PSM(job_queue)

        SAVE_PSM(psm_results)

        SAVE_RUNTIME(psm_results)
}

workflow SAGE_SEARCH {

    take:
        config_ch
        mzml_1_ch
        mzml_2_ch

    main:

        prepared_ch = SAGE_PREPARE(config_ch)

        mzml_ch = mzml_1_ch.concat(mzml_2_ch)

        job_queue = prepared_ch.combine(mzml_ch)

        psm_results = SAGE_PSM(job_queue)

        SAVE_PSM(psm_results)

        SAVE_RUNTIME(psm_results)
}

workflow ALPHADIA_SEARCH {

    take:
        config_ch
        mzml_ch

    main:
        prepared_ch = ALPHADIA_PREPARE(config_ch)

        job_queue = prepared_ch.combine(mzml_ch)

        psm_results = ALPHADIA_PSM(job_queue)

        SAVE_PSM(psm_results)

        SAVE_RUNTIME(psm_results)
}
