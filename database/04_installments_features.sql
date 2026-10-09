-- =====================================================================
-- 04_installments_features.sql — Échéances des prêts antérieurs (Phase 2)
-- D5  : agrégé directement par SK_ID_CURR (sans passer par previous_application).
-- Grain source : 1 ligne = 1 PAIEMENT ; une échéance peut être réglée en plusieurs fois
--   (640 905 échéances sur plusieurs lignes, montant dû et date d'échéance constants
--   au sein de chaque échéance : contrôle Phase 2).
-- Regroupement préalable au grain ÉCHÉANCE (SK_ID_PREV, NUM_INSTALMENT_VERSION,
--   NUM_INSTALMENT_NUMBER) : montant dû = MAX(AMT_INSTALMENT), payé = SUM(AMT_PAYMENT),
--   échéance = MIN(DAYS_INSTALMENT), dernier paiement = MAX(DAYS_ENTRY_PAYMENT).
-- Retard (jours) = dernier paiement - échéance, borné à 0 ; NULL si aucun paiement.
-- Sous-paiement : payé < dû - 0,01 (tolérance d'arrondi des sommes décimales).
-- D12 : fenêtre des 12 derniers mois = échéance >= -365 (suffixe _12M).
-- D10 : dénominateur nul → NULL.
-- =====================================================================

CREATE OR REPLACE TABLE feat_installments AS
WITH inst AS (
    SELECT SK_ID_CURR,
           SK_ID_PREV,
           NUM_INSTALMENT_VERSION,
           NUM_INSTALMENT_NUMBER,
           MIN(DAYS_INSTALMENT)    AS days_instalment,
           MAX(AMT_INSTALMENT)     AS amt_due,
           SUM(AMT_PAYMENT)        AS amt_paid,
           MAX(DAYS_ENTRY_PAYMENT) AS days_last_payment
    FROM installments_payments
    GROUP BY SK_ID_CURR, SK_ID_PREV, NUM_INSTALMENT_VERSION, NUM_INSTALMENT_NUMBER
),
x AS (
    SELECT SK_ID_CURR,
           days_instalment >= -365 AS w12,
           CASE
               WHEN days_last_payment IS NULL OR days_instalment IS NULL THEN NULL
               WHEN days_last_payment - days_instalment > 0 THEN days_last_payment - days_instalment
               ELSE 0
           END AS days_late,
           amt_paid / NULLIF(amt_due, 0) AS payment_ratio,
           CASE
               WHEN amt_paid IS NULL OR amt_due IS NULL THEN NULL
               WHEN amt_paid < amt_due - 0.01 THEN 1
               ELSE 0
           END AS underpaid
    FROM inst
)
SELECT
    SK_ID_CURR,
    -- Historique complet
    COUNT(*)                                                           AS INS_NB_INSTALMENTS,
    AVG(days_late)                                                     AS INS_MEAN_DAYS_LATE,
    MAX(days_late)                                                     AS INS_MAX_DAYS_LATE,
    AVG(CASE WHEN days_late > 0 THEN 1 WHEN days_late = 0 THEN 0 END)  AS INS_SHARE_LATE,
    AVG(payment_ratio)                                                 AS INS_MEAN_PAYMENT_RATIO,
    AVG(underpaid)                                                     AS INS_SHARE_UNDERPAID,
    -- 12 derniers mois
    COUNT(*) FILTER (WHERE w12)                                        AS INS_NB_INSTALMENTS_12M,
    AVG(days_late) FILTER (WHERE w12)                                  AS INS_MEAN_DAYS_LATE_12M,
    MAX(days_late) FILTER (WHERE w12)                                  AS INS_MAX_DAYS_LATE_12M,
    AVG(CASE WHEN days_late > 0 THEN 1 WHEN days_late = 0 THEN 0 END) FILTER (WHERE w12)
                                                                       AS INS_SHARE_LATE_12M,
    AVG(payment_ratio) FILTER (WHERE w12)                              AS INS_MEAN_PAYMENT_RATIO_12M,
    AVG(underpaid) FILTER (WHERE w12)                                  AS INS_SHARE_UNDERPAID_12M
FROM x
GROUP BY SK_ID_CURR;