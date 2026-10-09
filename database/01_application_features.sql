-- =====================================================================
-- 01_application_features.sql — Demande de crédit (Phase 2)
-- Base : db/credit_risk.duckdb. Exécuté par scripts/build_features.py.
-- application_all = application_train ∪ application_test, 1 ligne par SK_ID_CURR.
--   IS_TRAIN = 1 pour le train, 0 pour le test ; TARGET NULL pour le test.
-- Colonnes brutes conservées sous leur nom d'origine ; variables créées préfixées APP_.
-- D1  : DAYS_EMPLOYED = 365243 → NULL + APP_FLAG_DAYS_EMPLOYED_ANOM.
-- D3  : DAYS_* convertis en années positives (/ 365.25).
-- D4  : CODE_GENDER conservé tel quel (audit d'équité, exclu du modèle).
-- D8  : EXT_SOURCE_1/2/3 bruts inchangés.
-- D10 : dénominateur nul ou NULL → NULL (NULLIF), jamais 0 ni infini.
-- =====================================================================

CREATE OR REPLACE TABLE application_all AS
WITH base AS (
    SELECT 1 AS IS_TRAIN, * FROM application_train
    UNION ALL BY NAME
    SELECT 0 AS IS_TRAIN, * FROM application_test
),
flagged AS (
    SELECT *,
           CASE WHEN DAYS_EMPLOYED = 365243 THEN 1 ELSE 0 END AS APP_FLAG_DAYS_EMPLOYED_ANOM
    FROM base
),
clean AS (
    SELECT * REPLACE (NULLIF(DAYS_EMPLOYED, 365243) AS DAYS_EMPLOYED)
    FROM flagged
)
SELECT
    *,
    -- D3 : années positives
    -DAYS_BIRTH / 365.25                                   AS APP_AGE_YEARS,
    -DAYS_EMPLOYED / 365.25                                AS APP_EMPLOYED_YEARS,
    -DAYS_REGISTRATION / 365.25                            AS APP_REGISTRATION_YEARS,
    -DAYS_ID_PUBLISH / 365.25                              AS APP_ID_PUBLISH_YEARS,
    -DAYS_LAST_PHONE_CHANGE / 365.25                       AS APP_PHONE_CHANGE_YEARS,
    -- Ratios (D10)
    AMT_CREDIT / NULLIF(AMT_INCOME_TOTAL, 0)               AS APP_CREDIT_INCOME_RATIO,
    AMT_ANNUITY / NULLIF(AMT_INCOME_TOTAL, 0)              AS APP_ANNUITY_INCOME_RATIO,
    AMT_CREDIT / NULLIF(AMT_GOODS_PRICE, 0)                AS APP_CREDIT_GOODS_RATIO,
    AMT_CREDIT / NULLIF(AMT_ANNUITY, 0)                    AS APP_CREDIT_TERM_MONTHS,
    AMT_INCOME_TOTAL / NULLIF(CNT_FAM_MEMBERS, 0)          AS APP_INCOME_PER_PERSON,
    DAYS_EMPLOYED / NULLIF(DAYS_BIRTH, 0)                  AS APP_EMPLOYED_AGE_RATIO,
    -- Scores externes (D8 : bruts inchangés ; moyenne des scores renseignés)
    (COALESCE(EXT_SOURCE_1, 0) + COALESCE(EXT_SOURCE_2, 0) + COALESCE(EXT_SOURCE_3, 0))
        / NULLIF((EXT_SOURCE_1 IS NOT NULL)::INTEGER
               + (EXT_SOURCE_2 IS NOT NULL)::INTEGER
               + (EXT_SOURCE_3 IS NOT NULL)::INTEGER, 0)  AS APP_EXT_SOURCE_MEAN,
    (EXT_SOURCE_1 IS NULL)::INTEGER
      + (EXT_SOURCE_2 IS NULL)::INTEGER
      + (EXT_SOURCE_3 IS NULL)::INTEGER                    AS APP_EXT_SOURCE_NB_MISSING
FROM clean;
