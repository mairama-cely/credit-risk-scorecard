-- =====================================================================
-- 05_pos_cash_features.sql — Soldes mensuels des prêts POS / cash antérieurs (Phase 2)
-- D5  : agrégé directement par SK_ID_CURR.
-- SK_DPD = jours de retard du mois ; SK_DPD_DEF = retard hors petits montants tolérés.
-- D12 : fenêtre des 12 derniers mois = MONTHS_BALANCE >= -12 (suffixe _12M).
-- =====================================================================

CREATE OR REPLACE TABLE feat_pos_cash AS
SELECT
    SK_ID_CURR,
    -- Historique complet
    COUNT(*)                                                            AS POS_NB_MONTHS,
    MAX(SK_DPD)                                                         AS POS_MAX_DPD,
    AVG(SK_DPD_DEF)                                                     AS POS_MEAN_DPD_DEF,
    AVG(CASE WHEN SK_DPD > 0 THEN 1 WHEN SK_DPD = 0 THEN 0 END)         AS POS_SHARE_MONTHS_DPD,
    -- 12 derniers mois
    COUNT(*) FILTER (WHERE MONTHS_BALANCE >= -12)                       AS POS_NB_MONTHS_12M,
    MAX(SK_DPD) FILTER (WHERE MONTHS_BALANCE >= -12)                    AS POS_MAX_DPD_12M,
    AVG(SK_DPD_DEF) FILTER (WHERE MONTHS_BALANCE >= -12)                AS POS_MEAN_DPD_DEF_12M,
    AVG(CASE WHEN SK_DPD > 0 THEN 1 WHEN SK_DPD = 0 THEN 0 END)
        FILTER (WHERE MONTHS_BALANCE >= -12)                            AS POS_SHARE_MONTHS_DPD_12M
FROM pos_cash_balance
GROUP BY SK_ID_CURR;
