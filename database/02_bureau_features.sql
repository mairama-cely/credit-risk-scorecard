-- =====================================================================
-- 02_bureau_features.sql — Bureau de crédit et historique mensuel (Phase 2)
-- D5  : bureau_balance agrégé par SK_ID_BUREAU puis rattaché au client via bureau
--       (jointure interne : les SK_ID_BUREAU orphelins, 5,27 %, disparaissent).
-- D11 : STATUS '1'..'5' = retard, '0' = à jour, 'C' = clôturé, 'X' = inconnu ;
--       'C' et 'X' exclus du dénominateur des parts de mois en retard.
-- D12 : historique complet et 12 derniers mois (MONTHS_BALANCE >= -11, le mois courant
--       valant 0 dans bureau_balance ; suffixe _12M).
-- D10 : dénominateur nul → NULL.
-- Aucune valeur 365243 dans les DAYS_* de bureau (contrôle préalable) ;
-- DAYS_CREDIT_ENDDATE positif = échéance future, non traité comme anomalie.
-- CREDIT_ACTIVE : 'Sold' (6 527 lignes) et 'Bad debt' (21 lignes) regroupés dans
--       BUR_NB_SOLD_OR_BAD_DEBT (crédit sorti du circuit normal) ; 'Bad debt' seul serait
--       quasi constant.
-- Monnaie : montants additionnés sans conversion ; les crédits hors devise principale
--       représentent 0,082 % des lignes de bureau (contrôle Phase 2), écart jugé négligeable.
-- =====================================================================

-- a. bureau_balance : 1 ligne par crédit externe (SK_ID_BUREAU)
CREATE OR REPLACE TABLE feat_bureau_balance_credit AS
SELECT
    SK_ID_BUREAU,
    COUNT(*)                                                                    AS n_months,
    COUNT(*) FILTER (WHERE STATUS IN ('0', '1', '2', '3', '4', '5'))            AS n_known,
    COUNT(*) FILTER (WHERE STATUS IN ('1', '2', '3', '4', '5'))                 AS n_late,
    MAX(TRY_CAST(STATUS AS INTEGER))                                            AS max_status,
    COUNT(*) FILTER (WHERE MONTHS_BALANCE >= -11)                               AS n_months_12m,
    COUNT(*) FILTER (WHERE MONTHS_BALANCE >= -11
                       AND STATUS IN ('0', '1', '2', '3', '4', '5'))            AS n_known_12m,
    COUNT(*) FILTER (WHERE MONTHS_BALANCE >= -11
                       AND STATUS IN ('1', '2', '3', '4', '5'))                 AS n_late_12m,
    MAX(TRY_CAST(STATUS AS INTEGER)) FILTER (WHERE MONTHS_BALANCE >= -11)       AS max_status_12m
FROM bureau_balance
GROUP BY SK_ID_BUREAU;

-- b. Agrégation au grain SK_ID_CURR
CREATE OR REPLACE TABLE feat_bureau AS
WITH bb AS (
    SELECT b.SK_ID_CURR,
           c.n_months,
           c.n_months_12m,
           c.max_status,
           c.max_status_12m,
           c.n_late / NULLIF(c.n_known, 0)         AS share_late,
           c.n_late_12m / NULLIF(c.n_known_12m, 0) AS share_late_12m
    FROM feat_bureau_balance_credit c
    JOIN bureau b USING (SK_ID_BUREAU)
),
bb_client AS (
    SELECT SK_ID_CURR,
           SUM(n_months)        AS BB_NB_MONTHS,
           AVG(share_late)      AS BB_MEAN_SHARE_MONTHS_LATE,
           MAX(share_late)      AS BB_MAX_SHARE_MONTHS_LATE,
           MAX(max_status)      AS BB_MAX_STATUS,
           SUM(n_months_12m)    AS BB_NB_MONTHS_12M,
           AVG(share_late_12m)  AS BB_MEAN_SHARE_MONTHS_LATE_12M,
           MAX(share_late_12m)  AS BB_MAX_SHARE_MONTHS_LATE_12M,
           MAX(max_status_12m)  AS BB_MAX_STATUS_12M
    FROM bb
    GROUP BY SK_ID_CURR
),
bur AS (
    SELECT SK_ID_CURR,
           COUNT(*)                                                                  AS BUR_NB_CREDITS,
           COUNT(*) FILTER (WHERE CREDIT_ACTIVE = 'Active')                          AS BUR_NB_ACTIVE,
           COUNT(*) FILTER (WHERE CREDIT_ACTIVE = 'Closed')                          AS BUR_NB_CLOSED,
           COUNT(*) FILTER (WHERE CREDIT_ACTIVE IN ('Sold', 'Bad debt'))             AS BUR_NB_SOLD_OR_BAD_DEBT,
           -- Encours : crédits actifs uniquement ; 0 si aucun crédit actif,
           -- NULL si des crédits actifs existent mais que tous leurs montants sont inconnus
           CASE WHEN COUNT(*) FILTER (WHERE CREDIT_ACTIVE = 'Active') = 0 THEN 0
                ELSE SUM(AMT_CREDIT_SUM) FILTER (WHERE CREDIT_ACTIVE = 'Active') END      AS BUR_SUM_CREDIT,
           CASE WHEN COUNT(*) FILTER (WHERE CREDIT_ACTIVE = 'Active') = 0 THEN 0
                ELSE SUM(AMT_CREDIT_SUM_DEBT) FILTER (WHERE CREDIT_ACTIVE = 'Active') END AS BUR_SUM_DEBT,
           MAX(CREDIT_DAY_OVERDUE)                                                   AS BUR_MAX_DAY_OVERDUE,
           SUM(AMT_CREDIT_SUM_OVERDUE)                                               AS BUR_SUM_OVERDUE,
           SUM(CNT_CREDIT_PROLONG)                                                   AS BUR_NB_PROLONG,
           -MAX(DAYS_CREDIT) / 365.25                                                AS BUR_YEARS_SINCE_LAST_CREDIT
    FROM bureau
    GROUP BY SK_ID_CURR
)
SELECT
    bur.SK_ID_CURR,
    bur.BUR_NB_CREDITS,
    bur.BUR_NB_ACTIVE,
    bur.BUR_NB_CLOSED,
    bur.BUR_NB_SOLD_OR_BAD_DEBT,
    bur.BUR_SUM_CREDIT,
    bur.BUR_SUM_DEBT,
    bur.BUR_SUM_DEBT / NULLIF(bur.BUR_SUM_CREDIT, 0) AS BUR_DEBT_CREDIT_RATIO,
    bur.BUR_MAX_DAY_OVERDUE,
    bur.BUR_SUM_OVERDUE,
    bur.BUR_NB_PROLONG,
    bur.BUR_YEARS_SINCE_LAST_CREDIT,
    bb_client.BB_NB_MONTHS,
    bb_client.BB_MEAN_SHARE_MONTHS_LATE,
    bb_client.BB_MAX_SHARE_MONTHS_LATE,
    bb_client.BB_MAX_STATUS,
    bb_client.BB_NB_MONTHS_12M,
    bb_client.BB_MEAN_SHARE_MONTHS_LATE_12M,
    bb_client.BB_MAX_SHARE_MONTHS_LATE_12M,
    bb_client.BB_MAX_STATUS_12M
FROM bur
LEFT JOIN bb_client USING (SK_ID_CURR);