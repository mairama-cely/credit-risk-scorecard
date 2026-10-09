-- =====================================================================
-- 06_credit_card_features.sql — Soldes mensuels des cartes de crédit antérieures (Phase 2)
-- D5  : agrégé directement par SK_ID_CURR.
-- Utilisation = AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL ; plafond nul → NULL (D10).
-- D12 : fenêtre des 12 derniers mois = MONTHS_BALANCE >= -12 (suffixe _12M).
-- =====================================================================

CREATE OR REPLACE TABLE feat_credit_card AS
WITH c AS (
    SELECT SK_ID_CURR,
           MONTHS_BALANCE >= -12 AS w12,
           AMT_BALANCE / NULLIF(AMT_CREDIT_LIMIT_ACTUAL, 0) AS utilization,
           SK_DPD,
           AMT_DRAWINGS_CURRENT
    FROM credit_card_balance
)
SELECT
    SK_ID_CURR,
    -- Historique complet
    COUNT(*)                                                            AS CC_NB_MONTHS,
    AVG(utilization)                                                    AS CC_MEAN_UTILIZATION,
    MAX(utilization)                                                    AS CC_MAX_UTILIZATION,
    MAX(SK_DPD)                                                         AS CC_MAX_DPD,
    AVG(CASE WHEN SK_DPD > 0 THEN 1 WHEN SK_DPD = 0 THEN 0 END)         AS CC_SHARE_MONTHS_DPD,
    AVG(AMT_DRAWINGS_CURRENT)                                           AS CC_MEAN_DRAWINGS,
    -- 12 derniers mois
    COUNT(*) FILTER (WHERE w12)                                         AS CC_NB_MONTHS_12M,
    AVG(utilization) FILTER (WHERE w12)                                 AS CC_MEAN_UTILIZATION_12M,
    MAX(utilization) FILTER (WHERE w12)                                 AS CC_MAX_UTILIZATION_12M,
    MAX(SK_DPD) FILTER (WHERE w12)                                      AS CC_MAX_DPD_12M,
    AVG(CASE WHEN SK_DPD > 0 THEN 1 WHEN SK_DPD = 0 THEN 0 END) FILTER (WHERE w12)
                                                                        AS CC_SHARE_MONTHS_DPD_12M,
    AVG(AMT_DRAWINGS_CURRENT) FILTER (WHERE w12)                        AS CC_MEAN_DRAWINGS_12M
FROM c
GROUP BY SK_ID_CURR;
