-- =====================================================================
-- 03_previous_application_features.sql — Demandes antérieures chez Home Credit (Phase 2)
-- D2  : sentinelle 365243 → NULL dans les 5 colonnes DAYS_* où elle apparaît
--       (contrôle préalable), AVANT toute agrégation. DAYS_DECISION n'en contient pas.
--       DAYS_LAST_DUE_1ST_VERSION a aussi des valeurs positives légitimes (échéance future).
-- D12 : fenêtre des 12 derniers mois = DAYS_DECISION >= -365 (suffixe _12M).
-- D10 : dénominateur nul → NULL.
-- =====================================================================

CREATE OR REPLACE TABLE previous_application_clean AS
SELECT * REPLACE (
    NULLIF(DAYS_FIRST_DRAWING, 365243)        AS DAYS_FIRST_DRAWING,
    NULLIF(DAYS_FIRST_DUE, 365243)            AS DAYS_FIRST_DUE,
    NULLIF(DAYS_LAST_DUE_1ST_VERSION, 365243) AS DAYS_LAST_DUE_1ST_VERSION,
    NULLIF(DAYS_LAST_DUE, 365243)             AS DAYS_LAST_DUE,
    NULLIF(DAYS_TERMINATION, 365243)          AS DAYS_TERMINATION
)
FROM previous_application;

CREATE OR REPLACE TABLE feat_previous_application AS
WITH p AS (
    SELECT SK_ID_CURR,
           NAME_CONTRACT_STATUS,
           AMT_APPLICATION,
           AMT_CREDIT,
           AMT_CREDIT / NULLIF(AMT_APPLICATION, 0) AS credit_application_ratio,
           CNT_PAYMENT,
           DAYS_DECISION,
           DAYS_DECISION >= -365 AS w12
    FROM previous_application_clean
)
SELECT
    SK_ID_CURR,
    -- Historique complet
    COUNT(*)                                                                   AS PREV_NB_APPLICATIONS,
    COUNT(*) FILTER (WHERE NAME_CONTRACT_STATUS = 'Approved') / COUNT(*)       AS PREV_SHARE_APPROVED,
    COUNT(*) FILTER (WHERE NAME_CONTRACT_STATUS = 'Refused') / COUNT(*)        AS PREV_SHARE_REFUSED,
    AVG(AMT_APPLICATION)                                                       AS PREV_MEAN_AMT_APPLICATION,
    AVG(AMT_CREDIT)                                                            AS PREV_MEAN_AMT_CREDIT,
    AVG(credit_application_ratio)                                              AS PREV_MEAN_CREDIT_APPLICATION_RATIO,
    AVG(CNT_PAYMENT)                                                           AS PREV_MEAN_CNT_PAYMENT,
    -MAX(DAYS_DECISION) / 365.25                                               AS PREV_YEARS_SINCE_LAST_APPLICATION,
    -- 12 derniers mois
    COUNT(*) FILTER (WHERE w12)                                                AS PREV_NB_APPLICATIONS_12M,
    COUNT(*) FILTER (WHERE w12 AND NAME_CONTRACT_STATUS = 'Approved')
        / NULLIF(COUNT(*) FILTER (WHERE w12), 0)                               AS PREV_SHARE_APPROVED_12M,
    COUNT(*) FILTER (WHERE w12 AND NAME_CONTRACT_STATUS = 'Refused')
        / NULLIF(COUNT(*) FILTER (WHERE w12), 0)                               AS PREV_SHARE_REFUSED_12M,
    AVG(AMT_APPLICATION) FILTER (WHERE w12)                                    AS PREV_MEAN_AMT_APPLICATION_12M,
    AVG(AMT_CREDIT) FILTER (WHERE w12)                                         AS PREV_MEAN_AMT_CREDIT_12M,
    AVG(credit_application_ratio) FILTER (WHERE w12)                           AS PREV_MEAN_CREDIT_APPLICATION_RATIO_12M,
    AVG(CNT_PAYMENT) FILTER (WHERE w12)                                        AS PREV_MEAN_CNT_PAYMENT_12M
FROM p
GROUP BY SK_ID_CURR;
