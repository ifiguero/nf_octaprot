COPY (
    SELECT 'Table ' || NULLIF(table_name, '') || E' {\n' ||
           string_agg('  ' || name || ' ' || lower(type), E'\n') ||
           E'\n}'
    FROM (
        SELECT DISTINCT
            regexp_extract(file_name, 'silver/([^/]+)/', 1) AS table_name,
            name,
            type
        FROM parquet_schema('silver/**/*.parquet')
        WHERE name IS NOT NULL AND type IS NOT NULL
    )
    GROUP BY table_name
    HAVING table_name IS NOT NULL AND table_name != ''
) TO 'schema.dbml' (FORMAT CSV, QUOTE '', DELIMITER '', HEADER FALSE);
