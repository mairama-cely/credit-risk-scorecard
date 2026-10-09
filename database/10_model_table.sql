-- =====================================================================
-- 10_model_table.sql — Table de modélisation, 1 ligne = 1 SK_ID_CURR (Phase 2)
-- D6 : jointures GAUCHE des agrégats (déjà au grain SK_ID_CURR) sur application_all.
-- D7 : HAS_<SOURCE>_HISTORY (1/0) par source ; les comptages (NB_*) valent 0 en
--      l'absence d'historique ; les statistiques (moyennes, max, parts, ratios,
--      montants) restent NULL.
-- D9 : TARGET recopiée telle quelle pour le train, absente du test ; aucune
--      agrégation ne l'utilise.
-- =====================================================================

CREATE OR REPLACE VIEW v_model_table AS
SELECT
    a.*,
    -- Indicateurs de présence d'historique (D7)
    (bur.SK_ID_CURR IS NOT NULL)::INTEGER                  AS HAS_BUR_HISTORY,
    (COALESCE(bur.BB_NB_MONTHS, 0) > 0)::INTEGER           AS HAS_BB_HISTORY,
    (prev.SK_ID_CURR IS NOT NULL)::INTEGER                 AS HAS_PREV_HISTORY,
    (ins.SK_ID_CURR IS NOT NULL)::INTEGER                  AS HAS_INS_HISTORY,
    (pos.SK_ID_CURR IS NOT NULL)::INTEGER                  AS HAS_POS_HISTORY,
    (cc.SK_ID_CURR IS NOT NULL)::INTEGER                   AS HAS_CC_HISTORY,
    -- Bureau (BUR_)
    COALESCE(bur.BUR_NB_CREDITS, 0)                        AS BUR_NB_CREDITS,
    COALESCE(bur.BUR_NB_ACTIVE, 0)                         AS BUR_NB_ACTIVE,
    COALESCE(bur.BUR_NB_CLOSED, 0)                         AS BUR_NB_CLOSED,
    COALESCE(bur.BUR_NB_SOLD_OR_BAD_DEBT, 0)               AS BUR_NB_SOLD_OR_BAD_DEBT,
    bur.BUR_SUM_CREDIT,
    bur.BUR_SUM_DEBT,
    bur.BUR_DEBT_CREDIT_RATIO,
    bur.BUR_MAX_DAY_OVERDUE,
    bur.BUR_SUM_OVERDUE,
    COALESCE(bur.BUR_NB_PROLONG, 0)                        AS BUR_NB_PROLONG,
    bur.BUR_YEARS_SINCE_LAST_CREDIT,
    -- Historique mensuel du bureau (BB_)
    COALESCE(bur.BB_NB_MONTHS, 0)                          AS BB_NB_MONTHS,
    bur.BB_MEAN_SHARE_MONTHS_LATE,
    bur.BB_MAX_SHARE_MONTHS_LATE,
    bur.BB_MAX_STATUS,
    COALESCE(bur.BB_NB_MONTHS_12M, 0)                      AS BB_NB_MONTHS_12M,
    bur.BB_MEAN_SHARE_MONTHS_LATE_12M,
    bur.BB_MAX_SHARE_MONTHS_LATE_12M,
    bur.BB_MAX_STATUS_12M,
    -- Demandes antérieures (PREV_)
    COALESCE(prev.PREV_NB_APPLICATIONS, 0)                 AS PREV_NB_APPLICATIONS,
    prev.PREV_SHARE_APPROVED,
    prev.PREV_SHARE_REFUSED,
    prev.PREV_MEAN_AMT_APPLICATION,
    prev.PREV_MEAN_AMT_CREDIT,
    prev.PREV_MEAN_CREDIT_APPLICATION_RATIO,
    prev.PREV_MEAN_CNT_PAYMENT,
    prev.PREV_YEARS_SINCE_LAST_APPLICATION,
    COALESCE(prev.PREV_NB_APPLICATIONS_12M, 0)             AS PREV_NB_APPLICATIONS_12M,
    prev.PREV_SHARE_APPROVED_12M,
    prev.PREV_SHARE_REFUSED_12M,
    prev.PREV_MEAN_AMT_APPLICATION_12M,
    prev.PREV_MEAN_AMT_CREDIT_12M,
    prev.PREV_MEAN_CREDIT_APPLICATION_RATIO_12M,
    prev.PREV_MEAN_CNT_PAYMENT_12M,
    -- Échéances (INS_)
    COALESCE(ins.INS_NB_INSTALMENTS, 0)                    AS INS_NB_INSTALMENTS,
    ins.INS_MEAN_DAYS_LATE,
    ins.INS_MAX_DAYS_LATE,
    ins.INS_SHARE_LATE,
    ins.INS_MEAN_PAYMENT_RATIO,
    ins.INS_SHARE_UNDERPAID,
    COALESCE(ins.INS_NB_INSTALMENTS_12M, 0)                AS INS_NB_INSTALMENTS_12M,
    ins.INS_MEAN_DAYS_LATE_12M,
    ins.INS_MAX_DAYS_LATE_12M,
    ins.INS_SHARE_LATE_12M,
    ins.INS_MEAN_PAYMENT_RATIO_12M,
    ins.INS_SHARE_UNDERPAID_12M,
    -- POS / cash (POS_)
    COALESCE(pos.POS_NB_MONTHS, 0)                         AS POS_NB_MONTHS,
    pos.POS_MAX_DPD,
    pos.POS_MEAN_DPD_DEF,
    pos.POS_SHARE_MONTHS_DPD,
    COALESCE(pos.POS_NB_MONTHS_12M, 0)                     AS POS_NB_MONTHS_12M,
    pos.POS_MAX_DPD_12M,
    pos.POS_MEAN_DPD_DEF_12M,
    pos.POS_SHARE_MONTHS_DPD_12M,
    -- Cartes de crédit (CC_)
    COALESCE(cc.CC_NB_MONTHS, 0)                           AS CC_NB_MONTHS,
    cc.CC_MEAN_UTILIZATION,
    cc.CC_MAX_UTILIZATION,
    cc.CC_MAX_DPD,
    cc.CC_SHARE_MONTHS_DPD,
    cc.CC_MEAN_DRAWINGS,
    COALESCE(cc.CC_NB_MONTHS_12M, 0)                       AS CC_NB_MONTHS_12M,
    cc.CC_MEAN_UTILIZATION_12M,
    cc.CC_MAX_UTILIZATION_12M,
    cc.CC_MAX_DPD_12M,
    cc.CC_SHARE_MONTHS_DPD_12M,
    cc.CC_MEAN_DRAWINGS_12M
FROM application_all a
LEFT JOIN feat_bureau               bur  ON bur.SK_ID_CURR  = a.SK_ID_CURR
LEFT JOIN feat_previous_application prev ON prev.SK_ID_CURR = a.SK_ID_CURR
LEFT JOIN feat_installments         ins  ON ins.SK_ID_CURR  = a.SK_ID_CURR
LEFT JOIN feat_pos_cash             pos  ON pos.SK_ID_CURR  = a.SK_ID_CURR
LEFT JOIN feat_credit_card          cc   ON cc.SK_ID_CURR   = a.SK_ID_CURR;

-- Train : avec TARGET
CREATE OR REPLACE TABLE model_table_train AS
SELECT * EXCLUDE (IS_TRAIN)
FROM v_model_table
WHERE IS_TRAIN = 1
ORDER BY SK_ID_CURR;

-- Test : sans TARGET
CREATE OR REPLACE TABLE model_table_test AS
SELECT * EXCLUDE (IS_TRAIN, TARGET)
FROM v_model_table
WHERE IS_TRAIN = 0
ORDER BY SK_ID_CURR;