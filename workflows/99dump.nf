workflow DUMP {

    requests = Channel.fromPath(params.input_dump)

    dumps = PARQUET_TO_SQL_DUMP(requests)
    DUMP_BREAKDOWN(dumps)
}

process PARQUET_TO_SQL_DUMP {
    publishDir "${params.dump_dir}/99sqldump", mode: 'copy'
    tag "$request.baseName"

    input:
    path request

    output:
    path "*.sql"

    script:
    """
    export SILVER_DIR="${params.silver_access}"
    991_parquet_to_sql_dump.py ${request}
    """
}


process DUMP_BREAKDOWN {
    publishDir "${params.dump_dir}/99sqldump", mode: 'copy'
    tag "$request.baseName"

    input:
    path request

    output:
    path "*.png"

    script:
    """
    export SILVER_DIR="${params.silver_access}"
    992_dump_breakdown.py ${request}
    """
}
