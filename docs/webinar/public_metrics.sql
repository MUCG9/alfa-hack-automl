-- :evidence is the complete JSON text loaded from docs/v2_results.json.
-- SQLite JSON1: direct extraction of recorded measurements, no fabricated rows.
WITH search AS (
    SELECT json_extract(t.value, '$.task') AS task,
           json_extract(v.value, '$.version') AS version,
           42 AS seed,
           json_extract(v.value, '$.selected_search_value') AS value,
           json_extract(v.value, '$.split.validation_rows') AS validation_rows,
           'search: recipe selected on this split' AS stage
    FROM json_each(:evidence, '$.tasks') AS t
    CROSS JOIN json_each(t.value, '$.versions') AS v
), extra AS (
    SELECT json_extract(t.value, '$.task') AS task,
           json_extract(v.value, '$.version') AS version,
           44 AS seed,
           CASE json_extract(t.value, '$.task')
             WHEN 'regression' THEN json_extract(v.value, '$.metrics.rmse')
             ELSE json_extract(v.value, '$.metrics.macro_f1') END AS value,
           json_extract(t.value, '$.split.validation_rows') AS validation_rows,
           'fixed selected recipe, no new search' AS stage
    FROM json_each(:evidence, '$.robustness44') AS t
    CROSS JOIN json_each(t.value, '$.results') AS v
), combined AS (SELECT * FROM search UNION ALL SELECT * FROM extra)
SELECT task, version, seed, value, validation_rows, stage,
       CAST(seed AS TEXT) || ' · ' || version AS "case"
FROM combined
ORDER BY task, seed, version;
