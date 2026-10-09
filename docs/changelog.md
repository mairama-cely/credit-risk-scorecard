# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versionnage : `0.<phase>.<correctif>`.

## [0.6.2] — 2026-10-08 — Préparation de la publication

### Modifié
- Racine réduite à `README.md`, `requirements.txt` et `.gitignore`, sur le modèle du dépôt `bank-complaint-routing-nlp` : `changelog.md` → `docs/changelog.md`, `metadata.md` → `docs/data_dictionary.md` (chemin de sortie de `scripts/build_metadata.py` et renvois de `README.md`, `docs/cahier_des_charges.md`, `docs/feature_catalog.md`, `scripts/build_feature_catalog.py` et `notebooks/00_Data_Audit.ipynb` mis à jour).
- `README.md` restructuré : source des données, « En bref », structure du dépôt, reproduction phase par phase, tableau des notebooks, résultats (bloc `RESULTS` inchangé), limites connues ; bloc de statut et « Prochaines étapes » retirés (le tableau de bord Power BI non construit figure dans les limites). Aucun chiffre modifié.
- `requirements.txt` : seules les dépendances utilisées (importées par les scripts et notebooks, plus `pyarrow`, `ipykernel` et `nbconvert` nécessaires à l'exécution), versions exactes `==` reprises de l'environnement (`requirements-lock.txt`) ; `kaggle`, `streamlit`, `seaborn` retirés.
- `.gitignore` : contenu de `data/` et `models/` exclu, manifestes sha256, `.gitkeep` et `models/test_access_log.csv` versionnés ; motifs ancrés à la racine.
- Notebooks 00 à 07 : la cellule de setup n'affiche plus que le nom du dossier racine (aucun chemin local dans les sorties).
- Accès au test : la mention « ouvert une seule fois » est remplacée partout (README, docs, notebooks 05 à 07, générateurs `evaluate_models.py`, `build_cutoff_strategy.py`, `build_reports.py`). `models/test_access_log.csv` compte deux lectures (relances de `evaluate_models.py`) : le test n'est lu que par ce script, sans sélection ni réglage dessus, et le pipeline étant déterministe, chaque exécution redonne les mêmes résultats. Aucun chiffre modifié.

### Ajouté
- `scripts/build_manifest.py` : `data/raw/MANIFEST.json` (taille et sha256 des CSV) et `models/MANIFEST_models.json` (taille et sha256 des modèles).

### Supprimé
- `requirements-lock.txt`, dossiers vides `tests/` et `deployment/`.

## [0.6.1] — 2026-10-08

### Modifié
- Tableau de bord Power BI (`.pbix`) reporté en tâche ultérieure : il ne fait plus partie de la livraison actuelle. Les exports CSV (`scripts/export_to_powerbi.py`, `powerbi_data/`) et `docs/powerbi_guide.md` sont conservés comme préparation.
- `README.md` (statut, ordre d'exécution, section « Prochaines étapes »), `docs/cahier_des_charges.md` (version 0.6.1, D28) et `docs/powerbi_guide.md` (note de statut) mis à jour en conséquence.

## [0.6.0] — 2026-10-07 — Phase 5 : restitution

### Ajouté
- `scripts/export_to_powerbi.py` : exports CSV du tableau de bord dans `powerbi_data/` (non versionnés, régénérés par le script).
- `docs/powerbi_guide.md` : guide de construction du tableau de bord Power BI à partir de `powerbi_data/`.
- `scripts/build_reports.py` : génère `docs/note_comite_credit.md` (note d'une page au comité de crédit) et `docs/model_card.md` à partir des résultats des phases 3 et 4.
- `notebooks/07_Final_Synthesis.ipynb` : synthèse des phases 1 à 5 ; figures `output/07_*.png`.

### Modifié
- `README.md` : statut « terminé (v0.6.0) », bloc de 5 lignes de résultats entre `<!-- RESULTS:START -->` et `<!-- RESULTS:END -->` (chiffres de `output/tables/`), renvois vers la note au comité et le guide Power BI, arborescence, procédure de reproduction complète (scripts puis notebooks 00 → 07), limites complétées (LGD supposée, biais de sélection, motifs de refus).
- `docs/cahier_des_charges.md` : version 0.6.0 ; toutes les phases terminées ; journal 0.3.1 à 0.6.0 ; méthode de travail (sous-agents Claude, relecture du diff et commit par Cely) ; arborescence ; checklists cochées ; décisions de résultat consignées.
- `scripts/build_metadata.py` : version 0.6.0 ; nouvelle section « Tableaux de résultats versionnés » (`output/tables/*.csv`, dimensions lues dans les fichiers) ; `metadata.md` à régénérer.
- `requirements.txt` : ajout de `nbconvert` et `nbclient` (exécution des notebooks en ligne de commande).
- `.gitignore` : commentaires sur `powerbi_data/` (régénéré), `output/` (versionné) et `deployment/*.pbix` (versionnable sous 50 Mo).

## [0.5.0] — 2026-10-07 — Phase 4 : challenger, évaluation sur le test, stratégie de seuil

### Ajouté
- `scripts/train_challenger.py` (4a) : LightGBM sur les 200 candidates (valeurs brutes, NaN laissés au modèle), early stopping sur la validation ; deux variantes comparées sur la validation (sans pondération / `scale_pos_weight` = 11,39) ; ablation des 5 variables `EXT_SOURCE` ; SHAP (`TreeExplainer`) sur 5 000 lignes de validation. Sorties : `models/lgbm_model.txt`, `lgbm_model_no_ext.txt`, `lgbm_categories.json`, `lgbm_valid_scores.parquet` ; `output/tables/challenger_metrics.json`, `lgbm_feature_importance.csv`, `shap_importance.csv`.
- `scripts/evaluate_models.py` (4b) : **seul script qui lit le test**, par `load_split(..., allow_test=True)`, journalisée (`models/test_access_log.csv`, `evaluation_metrics.json`) avec contrôle de l'empreinte SHA-256 ; mode `--dry-run` (la validation remplace le test). Comparaison train / validation / test, bootstrap apparié (1 000 rééchantillonnages, graine 42), calibration par décile avec contrôle isotone ajusté sur la validation, PSI du score et des 17 variables, audit d'équité par `CODE_GENDER`, motifs de refus (3 variables les plus coûteuses en points). Sorties : `final_comparison.csv`, `calibration_test.csv`, `psi_table.csv`, `fairness_table.csv`, `refusal_reasons.csv`, `models/all_scores.parquet`, `models/test_scores.parquet`.
- `scripts/build_cutoff_strategy.py` (4c) : 3 scénarios (acceptation cible 60 / 75 / 85 % sur la validation), zones accepter / revoir / refuser (± 10 points), perte attendue PD × LGD × EAD (LGD 45 %, sensibilité 35 / 55 %, EAD = `AMT_CREDIT`), tranche marginale et marge d'équilibre ; règle de recommandation fixée avant lecture du test. Sorties : `cutoff_scenarios.csv`, `score_deciles.csv`, `cutoff_strategy.json`, `docs/model_performance_report.md`.
- `notebooks/05_Challenger_SHAP.ipynb` et `notebooks/06_Cutoff_Strategy.ipynb` ; figures `output/05_shap_*.png` (bar, beeswarm, dépendance, 3 cas individuels) et `output/06_*.png` (ROC test, calibration, PSI, déciles de score, scénarios, sensibilité à la LGD, équité, motifs de refus).

### Constats (issus de l'exécution)
- Variante retenue : sans pondération (AUC validation 0,7851 contre 0,7847 ; Brier 0,0659 contre 0,1619), 912 itérations.
- Test (46 127 demandes, lecture journalisée dans `models/test_access_log.csv`, empreinte conforme) : grille AUC 0,7518 [0,7437 ; 0,7598], Gini 0,5035, KS 0,3762, Brier 0,0684 ; LightGBM AUC 0,7883 [0,7809 ; 0,7960], Gini 0,5766, KS 0,4384, Brier 0,0659. Écart d'AUC apparié LightGBM − grille 0,0365 [0,0319 ; 0,0408], significatif.
- Sur-apprentissage de LightGBM : AUC train 0,8808 contre test 0,7883 ; grille stable (train 0,7544, test 0,7518).
- Ablation `EXT_SOURCE` (LightGBM) : AUC test 0,7598, soit -0,0285. 3 des 17 variables de la grille dérivent de ces scores ; pas d'ablation de la grille.
- Calibration (test) : grille PD moyenne 8,05 % pour 8,07 % observé, écart moyen par décile 0,20 pt (max 0,40 pt) ; LightGBM 0,25 pt (max 0,93 pt) ; les deux modèles jugés calibrés. PSI du score train → test 0,0001 ; PSI max des variables 0,0006 (`ORGANIZATION_TYPE`).
- Seuil Prudent (563 points) : acceptation 60,3 %, défaut des acceptés 3,44 % contre 8,07 %, 69,9 % de la perte attendue évitée, 36,7 % des bons clients refusés, zone de revue 25,4 %.
- Équité (seuil 563) : acceptation F 64,2 %, M 52,7 %, ratio M / F 0,821 ; parmi les bons clients 0,841.
- Motifs de refus : `APP_EXT_SOURCE_MEAN` premier motif de 99,5 % des refus (amplitude de points la plus grande, 65).

### Décisions
- Grille de score retenue comme modèle de décision ; LightGBM conservé comme référence de performance (challenger).
- Seuil recommandé : scénario **Prudent, 563 points** (critère validation « part de perte évitée − part de bons refusés » : 0,3321 contre 0,3153 et 0,2614).
- **Aucune recalibration isotone** : Brier de test isotone 0,0685 (grille) et 0,0660 (LightGBM), sans gain sur les PD brutes.
- Écart d'acceptation entre genres consigné comme point de vigilance, à soumettre à une revue de conformité.

## [0.4.0] — 2026-10-07 — Phase 3c-3e : binning WoE, sélection, grille de score

### Ajouté
- `scripts/train_scorecard.py` : binning optimal (`BinningProcess` d'optbinning 1.0.0) ajusté sur le train (D17) ; filtres IV, corrélation des WoE, VIF et plafond de 20 variables (D18, D19) ; logit non pondéré statsmodels avec retrait itératif des p-valeurs > 0,05 et des signes incohérents (D20) ; mise à l'échelle 600 points @ 50:1, PDO 20 (D21) ; option `--report`. Sorties : `output/tables/iv_table.csv` (motif d'exclusion de chaque candidate), `scorecard_table.csv` (grille de points), `scorecard_metrics.json`, `docs/scorecard_report.md` ; `models/binning_process.pkl`, `scorecard_logit.pkl`, `scorecard_selected_vars.json`, `scorecard_valid_scores.parquet` (non versionnés, D22).
- `notebooks/03_WoE_Binning.ipynb` : figures `output/03_iv_distribution.png`, `03_iv_top30.png`, `03_woe_top6.png`.
- `notebooks/04_Scorecard.ipynb` : figures `output/04_selection_funnel.png`, `04_points_range.png`, `04_score_distribution.png`, `04_score_bands.png`, `04_roc_ks.png`.

### Constats (issus de l'exécution, train et validation ; test non lu)
- Entonnoir : 200 candidates → 82 (IV ≥ 0,02) → 41 (corrélation des WoE ≤ 0,7) → 41 (VIF ≤ 5) → 20 (plafond) → **17** (p ≤ 0,05 et signe cohérent). Exclusions : `iv_low` 118, `corr` 41, `cap20` 21, `pvalue` 2, `sign` 1.
- 17 coefficients négatifs (convention WoE = ln(%bons / %mauvais)), VIF max 2,05 ; 0 WoE non monotone sur 200.
- IV > 0,5 : `APP_EXT_SOURCE_MEAN` (0,6287), retenue après revue. Sens a priori du catalogue confirmé pour 14 variables numériques sur 15 ; discordant : `PREV_MEAN_CREDIT_APPLICATION_RATIO`.
- Score théorique de 439 à 660 points ; factor 28,8539, offset 487,1229 ; +20 points doublent les odds (rapport mesuré 2,000).
- AUC train 0,7544, validation 0,7529 (écart 0,0014 < 0,02) ; Gini 0,5087 / 0,5059 ; KS 0,3810 / 0,3808.

## [0.3.1] — 2026-09-30 — Restructuration (alignement sur le projet réfugiés) et Phase 3a-3b

### Modifié (restructuration)
- Arborescence alignée sur le projet réfugiés du portfolio : `db/` + `sql/` → `database/` (base et fichiers SQL) ; `reports/` → `docs/` (rapports) et `output/` (figures préfixées par le numéro du notebook, `tables/`) ; `dashboards/exports/` → `powerbi_data/` ; ajout de `data/interim/`, `data/final/`, `models/`, `tests/`, `deployment/`.
- Fichiers racine en minuscules : `CHANGELOG.md` → `changelog.md`, `METADATA.md` → `metadata.md` ; `CAHIER_DES_CHARGES.md` → `docs/cahier_des_charges.md`.
- Scripts renommés (forme verbe_objet) : `load_to_duckdb.py` → `load_to_database.py`, `quality_checks.py` → `run_quality_checks.py`, `feature_catalog.py` → `build_feature_catalog.py`. `config.py` centralise les nouveaux chemins.
- Figures renommées : `00_target_distribution.png`, `00_top20_missing.png`, `01_missing_created_features.png`, `01_history_coverage.png`.
- Notebooks : un par étape d'analyse (`02_EDA`, puis `03_WoE_Binning`, `04_Scorecard`, `05_Challenger_SHAP`, `06_Cutoff_Strategy`, `07_Final_Synthesis`).
- `run_quality_checks.py` : sortie forcée en UTF-8 (plantage sur « ∩ » quand la sortie était redirigée).
- Validation après restructuration : mêmes 17 contrôles bloquants, mêmes 86 variables, mêmes empreintes du découpage ; les trois notebooks s'exécutent de bout en bout.
- Les entrées 0.1.0 à 0.3.0 ci-dessous citent les anciens chemins, valables à leur date.

### Ajouté (Phase 3)
- `scripts/make_splits.py` (3a) : découpage 70/15/15 stratifié sur `TARGET` (D14), 215 257 / 46 127 / 46 127 demandes, taux de défaut 8,07 % dans chaque échantillon ; tables `split_assignment` et `split_meta` ; test scellé (D15), empreinte SHA-256 `549e21fc4e086f93ecb1c954dcd7fffa97e7409f8c2469f554f85b021049e660` ; `load_split()` refuse le test sans autorisation explicite.
- `notebooks/02_EDA.ipynb` (3b) : analyse sur le train seul ; 200 variables candidates ; 83 variables sur 106 avec un écart de taux de défaut ≥ 1 point entre valeur manquante et renseignée ; `APP_EXT_SOURCE_MEAN` de 22,99 % (1er décile) à 1,98 % (dernier) ; drapeau `DAYS_EMPLOYED` = retraités à 99,96 %. Relation en creux relevée sur `APP_CREDIT_GOODS_RATIO` (monotonie à mesurer en 3c).
- `scripts/build_metadata.py` : tables du découpage ajoutées à `metadata.md`.

## [0.3.0] — 2026-09-29 — Phase 2 : feature engineering SQL

### Ajouté
- `sql/01_application_features.sql` : table `application_all` (train ∪ test, `IS_TRAIN`, `TARGET` NULL pour le test) ; `DAYS_EMPLOYED = 365243` → NULL et `APP_FLAG_DAYS_EMPLOYED_ANOM` (D1) ; âges et anciennetés en années (D3) ; ratios protégés par `NULLIF` (D10) ; moyenne et nombre de manquants des `EXT_SOURCE` (D8).
- `sql/02_bureau_features.sql` : `bureau_balance` agrégé par crédit puis par client via `bureau` (D5, D11), variables `BUR_` et `BB_`, fenêtre `_12M`.
- `sql/03_previous_application_features.sql` : `previous_application_clean` (sentinelle → NULL dans 5 colonnes `DAYS_*`, avant agrégation, D2), variables `PREV_`.
- `sql/04_installments_features.sql`, `sql/05_pos_cash_features.sql`, `sql/06_credit_card_features.sql` : variables `INS_`, `POS_`, `CC_`, agrégées directement par `SK_ID_CURR` (D5), historique complet et `_12M` (D12).
- `sql/10_model_table.sql` : vue `v_model_table` et tables `model_table_train` / `model_table_test` (jointures gauches). Indicateurs `HAS_*_HISTORY`, comptages à 0 et statistiques NULL en l'absence d'historique (D7).
- `scripts/build_features.py` : contrôle préalable des sentinelles, exécution ordonnée des SQL, contrôles bloquants, export Parquet, nombre de variables par préfixe.
  - **Transaction** : la construction (fichiers SQL) et les contrôles bloquants s'exécutent dans une seule transaction. En cas d'erreur SQL ou de contrôle en échec, elle est annulée : la base reste dans son état antérieur et aucun Parquet n'est exporté. Un échec simulé a été testé : base inchangée (même empreinte de `model_table_train`, 21 objets avant et après).
  - **Contrôle `TARGET` ∈ {0, 1}** ajouté aux contrôles bloquants (train). Tous les contrôles sont exécutés et affichés, puis le script s'arrête si au moins un échoue.
  - **Exécution mono-thread (`SET threads = 1`) pour la reproductibilité exacte** : la construction et les contrôles tournent sur un seul thread, puis le réglage d'origine est rétabli, y compris en cas d'échec. La durée totale de la construction est journalisée.
  - Cas limites : pas de requête vide si une table n'a aucune colonne décimale ; apostrophe échappée dans le chemin Parquet. Journal : durée par fichier SQL, puis volumes par table.
- `scripts/feature_catalog.py` → `reports/feature_catalog.md` : source, formule, sens attendu et statut des 208 colonnes, avec manquants, min et max lus dans la base. Le script échoue si le catalogue et la table divergent.
- `notebooks/01_Feature_Engineering.ipynb` : contrôles de la Phase 2, sans `TARGET` ; figures `reports/figures/fe_missing_created_features.png` et `fe_history_coverage.png`.

### Constats (issus de l'exécution)
- Sentinelle 365243 : présente dans 7 colonnes `DAYS_*` sur 22 (`DAYS_EMPLOYED` : 55 374 lignes du train, 9 274 du test ; `previous_application` : de 40 645 à 934 444 lignes selon la colonne), aucune dans `bureau` ni `installments_payments`.
- `installments_payments` : 640 905 échéances sont réglées en plusieurs paiements ; le montant dû et la date d'échéance sont constants au sein de chacune (0 incohérence).
- `bureau` : `CREDIT_ACTIVE` = `Closed` 1 079 273, `Active` 630 607, `Sold` 6 527, `Bad debt` 21 ; crédits hors devise principale : 0,082 % des lignes.
- `model_table_train` : 307 511 lignes × 208 colonnes ; `model_table_test` : 48 744 × 207. Les 17 contrôles bloquants sont satisfaits.
- **Correction d'une conclusion erronée sur l'idempotence des Parquet.** La première version de cette entrée tenait les Parquet pour « identiques en contenu » d'une exécution à l'autre. En réalité, ils n'avaient été comparés qu'à la table DuckDB de la même exécution. Comparés entre deux exécutions en parallèle (4 threads), ils différaient sur 17 colonnes calculées par `SUM` / `AVG` de valeurs décimales : 85 200 lignes du train et 14 930 du test, avec un écart relatif maximal de 4·10⁻¹⁵ (dernier bit). La cause est l'ordre des additions, qui varie en parallèle. Depuis le passage en mono-thread, deux exécutions successives donnent des Parquet identiques en comparaison stricte, colonne par colonne et sans tolérance : **0 valeur différente** (vérifié à nouveau après la relecture du SQL). La construction (SQL + contrôles) dure environ 65 s. Les comptes et le catalogue (arrondi à 4 décimales) n'étaient pas affectés.
- 86 variables créées : volume inférieur au cadre indicatif de 100 à 200, accepté après revue (D13 amendé le 29/09), sans ajout forcé.
- Couverture du train : `HAS_INS_HISTORY` 94,84 %, `HAS_PREV_HISTORY` 94,65 %, `HAS_POS_HISTORY` 94,12 %, `HAS_BUR_HISTORY` 85,69 %, `HAS_BB_HISTORY` 29,99 %, `HAS_CC_HISTORY` 28,26 %.

### Modifié
- `scripts/build_metadata.py` : version 0.3.0, tables produites en Phase 2 (volumes lus dans la base), renvoi vers `reports/feature_catalog.md` ; `METADATA.md` régénéré. Plus de date dans le fichier produit ; ligne Licence sans condition non vérifiée ; chiffres des variables clés lus dans la base.
- `README.md` : statut, constats de la Phase 2, procédure de reproduction.
- Relecture du SQL : échéances regroupées au grain échéance avant agrégation (640 905 échéances payées en plusieurs fois), `INS_NB_PAYMENTS` renommé `INS_NB_INSTALMENTS` ; fenêtre `_12M` de `bureau_balance` ramenée à 12 mois exacts (`>= -11`, le mois courant valant 0) ; encours bureau NULL si les montants des crédits actifs sont tous inconnus ; ajout de `BUR_NB_SOLD_OR_BAD_DEBT` (`Sold` et `Bad debt` regroupés, `Bad debt` seul étant quasi constant) ; suppression de la date dans `feature_catalog.md` ; alerte D13 de `build_features.py` et du notebook 01 remplacée par un contrôle du nombre validé (86).

### Corrigé
- `scripts/build_metadata.py` écrasé par une ancienne version (onglet d'éditeur réenregistré) : restauré, puis `METADATA.md` régénéré à l'identique.

## [0.2.0] — 2026-09-29 — Phase 1 : ingestion et audit qualité

### Ajouté
- `scripts/verify_raw_data.py` : vérifie la présence des 9 CSV attendus (noms exacts, casse comprise) et journalise leur taille, sans aucun appel réseau ; liste les fichiers annexes non utilisés (`sample_submission.csv`).
- `scripts/load_to_duckdb.py` : charge les 9 tables dans `db/credit_risk.duckdb` (`CREATE OR REPLACE`, `read_csv` en mode strict avec typage sur le fichier entier). Le dictionnaire est décodé en cp1252 après échec de l'UTF-8. Le script compare les lignes du CSV aux lignes chargées et écrit le résultat dans la table `meta_load_log`.
- `sql/00_quality_checks.sql` : 15 requêtes nommées (volumétrie, unicité des clés, intégrité référentielle, couverture, cible, manquants, sentinelles `365243`, `CODE_GENDER`, `DAYS_*` positifs, `EXT_SOURCE_*`).
- `scripts/quality_checks.py` : exécute ces requêtes en lecture seule (console ou notebook).
- `scripts/build_metadata.py` : génère `METADATA.md` depuis la base.
- `notebooks/00_Data_Audit.ipynb` : audit exécuté de bout en bout ; figures `reports/figures/target_distribution.png` et `top20_missing.png`.
- `reports/data_quality_report.md` : volumétrie, constats et décisions proposées pour la Phase 2.
- `requirements-lock.txt` : `pip freeze` de `.venv` (Python 3.13.15).
- Dépôt Git initialisé ; `.gitkeep` dans les dossiers vides.

### Constats (issus de l'exécution)
- 58 490 112 lignes chargées ; lignes CSV = lignes chargées pour les 9 fichiers (aucun fichier tronqué).
- `application_train` : 307 511 lignes, taux de défaut 8,07 % ; `SK_ID_CURR` unique dans le train (307 511) et le test (48 744), sans recouvrement.
- `DAYS_EMPLOYED = 365243` : 55 374 lignes (18,01 %), taux de défaut 5,40 % contre 8,66 %.
- `CODE_GENDER = 'XNA'` : 4 lignes. `bureau_balance` : 94,73 % des `SK_ID_BUREAU` retrouvés dans `bureau`.

### Modifié
- `scripts/config.py` : 9 CSV attendus ; tables nommées d'après leur fichier (minuscules, sans préfixe `raw_`) ; `application_test` et le dictionnaire sont chargés.
- `README.md` : statut, constats chiffrés, procédure de reproduction (téléchargement manuel).
- `METADATA.md` : volumes mesurés, schéma relationnel (Mermaid) avec taux de clés orphelines lus dans la base, dictionnaire des 219 colonnes.

### Supprimé
- Itération 0.2.0-rc (jamais exécutée sur les données réelles) : `scripts/fetch_data.py` (téléchargement par l'API Kaggle, remplacé par la vérification locale), `sql/01_load_raw.sql`, `sql/01_integrity_checks.sql`, `notebooks/00_Data_Fetching.ipynb`.

## [0.1.0] — 2026-09-26 — Phase 0 : cadrage

### Ajouté
- `CAHIER_DES_CHARGES.md` : contexte, problématique, objectifs O1–O6, périmètre, choix méthodologiques, stack, phases 0–8, planning jusqu'au 20/10/2026, risques.
- `README.md` : présentation, arborescence, installation, accès Kaggle, méthodologie résumée, limites.
- `METADATA.md` : source, 8 tables, clés de jointure, variables clés de `application_train`.
- `requirements.txt` : dépendances avec versions minimales.
- `.gitignore` : exclusion des données brutes, traitées, de la base DuckDB et des identifiants Kaggle.
- `.gitkeep` dans les dossiers vides à conserver sous Git.

### Décisions
- Dataset retenu : Home Credit Default Risk.
- Stockage : DuckDB + Parquet.
- `CODE_GENDER` exclu du modèle.