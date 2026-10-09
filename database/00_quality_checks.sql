-- =====================================================================
-- 00_quality_checks.sql — Audit qualité des données brutes (Phase 1)
-- Base : db/credit_risk.duckdb (tables créées par scripts/load_to_duckdb.py)
-- Chaque requête est nommée par un commentaire « -- name: » et exécutée
-- séparément par scripts/quality_checks.py (lecture seule).
-- application_test n'a pas de TARGET : il n'intervient jamais dans l'analyse
-- de la cible, seulement dans la volumétrie, l'unicité et l'intégrité.
-- =====================================================================

-- name: a_volumetrie
-- a. Lignes et colonnes par table ; intégrité des fichiers (lignes CSV = lignes chargées)
SELECT l.table_name,
       l.n_rows,
       l.n_cols,
       l.size_mb,
       l.csv_data_lines,
       l.lines_match,
       l.encoding
FROM meta_load_log l
ORDER BY l.n_rows DESC;

-- name: b_unicite_sk_id_curr
-- b. Unicité de SK_ID_CURR dans les deux tables application
SELECT 'application_train' AS table_name,
       COUNT(*) AS n_lignes,
       COUNT(DISTINCT SK_ID_CURR) AS n_distincts,
       COUNT(*) - COUNT(DISTINCT SK_ID_CURR) AS n_doublons,
       COUNT(*) - COUNT(SK_ID_CURR) AS n_nulls
FROM application_train
UNION ALL
SELECT 'application_test', COUNT(*), COUNT(DISTINCT SK_ID_CURR),
       COUNT(*) - COUNT(DISTINCT SK_ID_CURR), COUNT(*) - COUNT(SK_ID_CURR)
FROM application_test
UNION ALL
-- Recouvrement train / test (doit être nul)
SELECT 'train ∩ test', COUNT(*), COUNT(DISTINCT SK_ID_CURR), NULL, NULL
FROM application_train
WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_test);

-- name: c_unicite_cles_secondaires
-- c. Unicité de SK_ID_BUREAU dans bureau et de SK_ID_PREV dans previous_application
SELECT 'bureau.SK_ID_BUREAU' AS cle,
       COUNT(*) AS n_lignes,
       COUNT(DISTINCT SK_ID_BUREAU) AS n_distincts,
       COUNT(*) - COUNT(DISTINCT SK_ID_BUREAU) AS n_doublons,
       COUNT(*) - COUNT(SK_ID_BUREAU) AS n_nulls
FROM bureau
UNION ALL
SELECT 'previous_application.SK_ID_PREV', COUNT(*), COUNT(DISTINCT SK_ID_PREV),
       COUNT(*) - COUNT(DISTINCT SK_ID_PREV), COUNT(*) - COUNT(SK_ID_PREV)
FROM previous_application;

-- name: d_integrite_referentielle
-- d. Part des clés distinctes d'une table enfant retrouvées dans la table parent
WITH app AS (
    SELECT SK_ID_CURR FROM application_train
    UNION
    SELECT SK_ID_CURR FROM application_test
),
enfants AS (
    SELECT 'bureau.SK_ID_CURR → application (train ∪ test)' AS relation,
           COUNT(DISTINCT b.SK_ID_CURR) AS n_cles_distinctes,
           COUNT(DISTINCT b.SK_ID_CURR) FILTER (WHERE b.SK_ID_CURR IN (SELECT SK_ID_CURR FROM app)) AS n_retrouvees
    FROM bureau b
    UNION ALL
    SELECT 'previous_application.SK_ID_CURR → application (train ∪ test)',
           COUNT(DISTINCT p.SK_ID_CURR),
           COUNT(DISTINCT p.SK_ID_CURR) FILTER (WHERE p.SK_ID_CURR IN (SELECT SK_ID_CURR FROM app))
    FROM previous_application p
    UNION ALL
    SELECT 'bureau_balance.SK_ID_BUREAU → bureau',
           COUNT(DISTINCT bb.SK_ID_BUREAU),
           COUNT(DISTINCT bb.SK_ID_BUREAU) FILTER (WHERE bb.SK_ID_BUREAU IN (SELECT SK_ID_BUREAU FROM bureau))
    FROM bureau_balance bb
    -- Contrôles complémentaires (tables agrégées en Phase 2)
    UNION ALL
    SELECT 'pos_cash_balance.SK_ID_PREV → previous_application',
           COUNT(DISTINCT x.SK_ID_PREV),
           COUNT(DISTINCT x.SK_ID_PREV) FILTER (WHERE x.SK_ID_PREV IN (SELECT SK_ID_PREV FROM previous_application))
    FROM pos_cash_balance x
    UNION ALL
    SELECT 'installments_payments.SK_ID_PREV → previous_application',
           COUNT(DISTINCT x.SK_ID_PREV),
           COUNT(DISTINCT x.SK_ID_PREV) FILTER (WHERE x.SK_ID_PREV IN (SELECT SK_ID_PREV FROM previous_application))
    FROM installments_payments x
    UNION ALL
    SELECT 'credit_card_balance.SK_ID_PREV → previous_application',
           COUNT(DISTINCT x.SK_ID_PREV),
           COUNT(DISTINCT x.SK_ID_PREV) FILTER (WHERE x.SK_ID_PREV IN (SELECT SK_ID_PREV FROM previous_application))
    FROM credit_card_balance x
)
SELECT relation,
       n_cles_distinctes,
       n_retrouvees,
       ROUND(100.0 * n_retrouvees / n_cles_distinctes, 2) AS pct_retrouvees
FROM enfants;

-- name: d_couverture_application_train
-- d (complément). Part des demandes d'application_train ayant un historique dans chaque table
SELECT source,
       n_clients,
       ROUND(100.0 * n_clients / (SELECT COUNT(*) FROM application_train), 2) AS pct_application_train
FROM (
    SELECT 'bureau' AS source, COUNT(DISTINCT SK_ID_CURR) AS n_clients
    FROM bureau WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_train)
    UNION ALL
    SELECT 'previous_application', COUNT(DISTINCT SK_ID_CURR)
    FROM previous_application WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_train)
    UNION ALL
    SELECT 'pos_cash_balance', COUNT(DISTINCT SK_ID_CURR)
    FROM pos_cash_balance WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_train)
    UNION ALL
    SELECT 'installments_payments', COUNT(DISTINCT SK_ID_CURR)
    FROM installments_payments WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_train)
    UNION ALL
    SELECT 'credit_card_balance', COUNT(DISTINCT SK_ID_CURR)
    FROM credit_card_balance WHERE SK_ID_CURR IN (SELECT SK_ID_CURR FROM application_train)
)
ORDER BY pct_application_train DESC;

-- name: e_distribution_target
-- e. Distribution de la cible (application_train uniquement)
SELECT TARGET,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM application_train
GROUP BY TARGET
ORDER BY TARGET;

-- name: f_top20_manquants
-- f. Top 20 des colonnes d'application_train par % de valeurs manquantes
WITH nulls AS (
    UNPIVOT (SELECT COUNT(*) - COUNT(COLUMNS(*)) FROM application_train)
    ON COLUMNS(*) INTO NAME colonne VALUE n_manquants
)
SELECT colonne,
       n_manquants,
       ROUND(100.0 * n_manquants / (SELECT COUNT(*) FROM application_train), 2) AS pct_manquants
FROM nulls
ORDER BY n_manquants DESC, colonne
LIMIT 20;

-- name: f_synthese_manquants
-- f (complément). Nombre de colonnes d'application_train par tranche de manquants
WITH nulls AS (
    UNPIVOT (SELECT COUNT(*) - COUNT(COLUMNS(*)) FROM application_train)
    ON COLUMNS(*) INTO NAME colonne VALUE n_manquants
)
SELECT CASE
           WHEN n_manquants = 0 THEN '0 %'
           WHEN n_manquants < 0.10 * (SELECT COUNT(*) FROM application_train) THEN ']0 ; 10 %['
           WHEN n_manquants < 0.50 * (SELECT COUNT(*) FROM application_train) THEN '[10 ; 50 %['
           ELSE '≥ 50 %'
       END AS tranche,
       COUNT(*) AS n_colonnes
FROM nulls
GROUP BY tranche
ORDER BY MIN(n_manquants);

-- name: g1_days_employed_sentinelle
-- g. DAYS_EMPLOYED = 365243 (≈ 1 000 ans) : effectif et taux de défaut comparé au reste
SELECT CASE WHEN DAYS_EMPLOYED = 365243 THEN 'DAYS_EMPLOYED = 365243' ELSE 'autres' END AS groupe,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_lignes,
       SUM(TARGET)::BIGINT AS n_defauts,
       ROUND(100.0 * AVG(TARGET), 2) AS taux_defaut_pct
FROM application_train
GROUP BY groupe
ORDER BY groupe DESC;

-- name: g1_days_employed_sentinelle_income_type
-- g (complément). Profil du groupe sentinelle selon NAME_INCOME_TYPE
SELECT NAME_INCOME_TYPE,
       COUNT(*) AS n_sentinelle
FROM application_train
WHERE DAYS_EMPLOYED = 365243
GROUP BY NAME_INCOME_TYPE
ORDER BY n_sentinelle DESC;

-- name: g1_days_employed_sentinelle_test
-- g (complément). Même sentinelle dans application_test (effectif seulement, pas de cible)
SELECT COUNT(*) FILTER (WHERE DAYS_EMPLOYED = 365243) AS n_sentinelle,
       ROUND(100.0 * COUNT(*) FILTER (WHERE DAYS_EMPLOYED = 365243) / COUNT(*), 2) AS pct_lignes
FROM application_test;

-- name: g2_code_gender
-- g. Modalités de CODE_GENDER, dont 'XNA'
SELECT 'application_train' AS table_name, CODE_GENDER, COUNT(*) AS n
FROM application_train GROUP BY CODE_GENDER
UNION ALL
SELECT 'application_test', CODE_GENDER, COUNT(*)
FROM application_test GROUP BY CODE_GENDER
ORDER BY table_name DESC, n DESC;

-- name: g3_days_positifs
-- g. Colonnes DAYS_* des tables application : valeurs positives (attendues ≤ 0)
WITH train AS (
    UNPIVOT (SELECT COUNT(*) FILTER (WHERE COLUMNS('^DAYS_') > 0) FROM application_train)
    ON COLUMNS(*) INTO NAME colonne VALUE n_positifs
),
test AS (
    UNPIVOT (SELECT COUNT(*) FILTER (WHERE COLUMNS('^DAYS_') > 0) FROM application_test)
    ON COLUMNS(*) INTO NAME colonne VALUE n_positifs
),
train_hors_sentinelle AS (
    SELECT 'DAYS_EMPLOYED' AS colonne, COUNT(*) AS n_positifs_hors_365243
    FROM application_train WHERE DAYS_EMPLOYED > 0 AND DAYS_EMPLOYED <> 365243
)
SELECT colonne,
       train.n_positifs AS n_positifs_train,
       test.n_positifs AS n_positifs_test,
       COALESCE(h.n_positifs_hors_365243, train.n_positifs) AS n_positifs_train_hors_365243
FROM train
JOIN test USING (colonne)
LEFT JOIN train_hors_sentinelle h USING (colonne)
ORDER BY colonne;

-- name: g4_sentinelle_previous_application
-- g (complément, pour la Phase 2). La même sentinelle 365243 dans les DAYS_* de previous_application
WITH s AS (
    UNPIVOT (SELECT COUNT(*) FILTER (WHERE COLUMNS('^DAYS_') = 365243) FROM previous_application)
    ON COLUMNS(*) INTO NAME colonne VALUE n_365243
)
SELECT colonne,
       n_365243,
       ROUND(100.0 * n_365243 / (SELECT COUNT(*) FROM previous_application), 2) AS pct_lignes
FROM s
ORDER BY colonne;

-- name: h_ext_source_manquants
-- Complément (cahier §7.4) : manquants des scores externes EXT_SOURCE_1/2/3 (application_train)
WITH m AS (
    UNPIVOT (SELECT COUNT(*) - COUNT(COLUMNS('^EXT_SOURCE_')) FROM application_train)
    ON COLUMNS(*) INTO NAME colonne VALUE n_manquants
)
SELECT colonne,
       n_manquants,
       ROUND(100.0 * n_manquants / (SELECT COUNT(*) FROM application_train), 2) AS pct_manquants
FROM m
ORDER BY colonne;
