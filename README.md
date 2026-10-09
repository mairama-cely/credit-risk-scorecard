# Grille de score crédit interprétable (credit risk scorecard)

Une banque qui prête à des demandeurs à historique de crédit faible doit classer chaque demande par niveau de risque, avec une règle que l'analyste crédit peut lire, justifier et auditer.
Ce projet construit une grille de score (régression logistique sur Weight of Evidence, mise à l'échelle en points), la valide sur un jeu de test scellé et la compare à un challenger LightGBM.
Le livrable métier est un seuil d'acceptation chiffré : taux d'acceptation, défaut des acceptés et perte attendue évitée.

> **Source des données.** Compétition Kaggle *Home Credit Default Risk* (Home Credit Group, 2018) : 9 CSV (8 tables + dictionnaire des colonnes, 2 559 Mo).
> Utilisation soumise aux règles de la compétition : les données ne sont pas redistribuées dans ce dépôt ; `data/raw/MANIFEST.json` donne la taille et l'empreinte sha256 des fichiers utilisés.
> Les demandes ne portent pas de date d'octroi : aucune validation out-of-time n'est possible.
> Page source : https://www.kaggle.com/competitions/home-credit-default-risk/data

## En bref

| | |
|---|---|
| **Question** | Comment classer des demandeurs à historique de crédit faible par niveau de risque, avec une grille que l'analyste crédit peut lire, justifier et auditer ? |
| **Données** | 307 511 demandes réelles (`application_train`, défaut 8,07 %) et 7 tables d'historique agrégées au client ; découpage 70/15/15 stratifié, test de 46 127 demandes scellé. |
| **Modèle** | Binning optimal → WoE → sélection (IV, corrélation des WoE, VIF, p-valeur et signe) → régression logistique sur 17 variables, mise à l'échelle de 439 à 660 points (600 points pour des odds 50:1, PDO 20). Challenger : LightGBM (200 variables) expliqué par SHAP. |
| **Résultat** | AUC test **0,7518** pour la grille (LightGBM : 0,7883). Au seuil de 563 points : acceptation 60,3 %, défaut des acceptés **3,44 %** contre 8,07 % sans seuil, **69,9 %** de la perte attendue évitée. |
| **Rigueur** | Test lu par un seul script (`evaluate_models.py`), chaque ouverture journalisée avec contrôle d'empreinte (`models/test_access_log.csv`) ; seuils choisis sur la validation, évalués sur le test ; IC 95 % par bootstrap (1 000 rééchantillonnages) ; calibration et PSI contrôlés ; empreintes sha256 des données et des modèles. |
| **Limites principales** | Pas de validation out-of-time ; données non africaines (transposition au marché CEMAC argumentée, pas mesurée) ; LGD supposée (45 %). |

Note d'une page pour le comité de crédit : [`docs/note_comite_credit.md`](docs/note_comite_credit.md).

Cadrage complet : [`docs/cahier_des_charges.md`](docs/cahier_des_charges.md).

## Structure du dépôt

```
data/            non versionné — raw/ (CSV Kaggle + MANIFEST.json), interim/ (affectation train / valid / test), processed/ (tables de modélisation Parquet), final/
database/        00_quality_checks.sql · 01_application_features.sql … 06_credit_card_features.sql · 10_model_table.sql (base credit_risk.duckdb non versionnée)
scripts/         config.py · verify_raw_data.py · load_to_database.py · run_quality_checks.py · build_features.py · build_feature_catalog.py · make_splits.py · build_metadata.py · train_scorecard.py · train_challenger.py · evaluate_models.py · build_cutoff_strategy.py · export_to_powerbi.py · build_reports.py · build_manifest.py
notebooks/       00_Data_Audit · 01_Feature_Engineering · 02_EDA · 03_WoE_Binning · 04_Scorecard · 05_Challenger_SHAP · 06_Cutoff_Strategy · 07_Final_Synthesis
output/          figures des notebooks (NN_nom.png, NN = numéro du notebook) · tables/ (CSV et JSON de résultats)
docs/            cahier_des_charges.md · changelog.md · data_dictionary.md (généré) · data_quality_report.md · feature_catalog.md (généré) · scorecard_report.md (généré) · model_performance_report.md (généré) · note_comite_credit.md et model_card.md (générés) · powerbi_guide.md
models/          non versionné — binning, grille, LightGBM, scores · seuls MANIFEST_models.json et test_access_log.csv sont versionnés
powerbi_data/    non versionné — exports CSV pour Power BI (régénérés par export_to_powerbi.py)
```

## Reproduire la Phase 1

Prérequis : Python 3.13, Windows (PowerShell).

Acquisition des données : télécharger manuellement les données depuis l'onglet *Data* de la compétition Kaggle [`home-credit-default-risk`](https://www.kaggle.com/competitions/home-credit-default-risk/data) (règles à accepter), puis placer les 9 CSV décompressés dans `data/raw/`. Aucun script n'appelle l'API Kaggle.

Depuis la racine du dépôt :

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

.venv\Scripts\python.exe scripts\verify_raw_data.py        # présence des 9 CSV (aucun appel réseau)
.venv\Scripts\python.exe scripts\load_to_database.py       # database\credit_risk.duckdb + intégrité (~5 min)
.venv\Scripts\python.exe scripts\run_quality_checks.py     # database\00_quality_checks.sql
```

## Reproduire la Phase 2

```powershell
.venv\Scripts\python.exe scripts\build_features.py         # database\01 … 06 puis 10, contrôles bloquants (~70 s, mono-thread)
```

`build_features.py` s'arrête avec l'erreur exacte si un contrôle bloquant échoue ; ses écritures se font dans une transaction, annulée en cas d'échec. La construction tourne sur un seul thread : deux exécutions produisent des tables identiques au bit près.

## Reproduire la Phase 3

```powershell
.venv\Scripts\python.exe scripts\make_splits.py            # train / valid / test, test scellé
.venv\Scripts\python.exe scripts\build_feature_catalog.py  # docs\feature_catalog.md (statut « candidate », D16)
.venv\Scripts\python.exe scripts\build_metadata.py         # docs\data_dictionary.md
.venv\Scripts\python.exe scripts\train_scorecard.py        # binning, sélection, logit, grille, docs\scorecard_report.md
```

`make_splits.py` s'arrête lui aussi si un contrôle bloquant échoue (écritures en transaction). `build_metadata.py` lit les tables du découpage et les CSV présents dans `output/tables/` : le relancer en fin de chaîne si ces CSV ont été régénérés.

## Reproduire la Phase 4

```powershell
.venv\Scripts\python.exe scripts\train_challenger.py       # LightGBM, ablation EXT_SOURCE, SHAP
.venv\Scripts\python.exe scripts\evaluate_models.py        # ouverture du test (journalisée)
.venv\Scripts\python.exe scripts\build_cutoff_strategy.py  # scénarios de seuil, docs\model_performance_report.md
.venv\Scripts\python.exe scripts\build_manifest.py         # empreintes sha256 : data\raw\MANIFEST.json, models\MANIFEST_models.json
```

`evaluate_models.py` est le seul script autorisé à lire le test ; chaque exécution est journalisée (`models/test_access_log.csv`) avec contrôle de l'empreinte (`--dry-run` : répétition sur la validation).

## Reproduire la Phase 5

```powershell
.venv\Scripts\python.exe scripts\export_to_powerbi.py      # powerbi_data\*.csv (préparation du tableau de bord, reporté)
.venv\Scripts\python.exe scripts\build_reports.py          # note au comité, model card
```

## Notebooks (00 à 07)

Les notebooks présentent les résultats produits par les scripts ci-dessus : ils ouvrent la base en lecture seule et relisent les artefacts de `models/` et `output/tables/`, n'entraînent aucun modèle et n'ouvrent pas le jeu de test dans la base. Chaque figure est enregistrée dans `output/`.

```powershell
foreach ($nb in Get-ChildItem notebooks\0*.ipynb | Sort-Object Name) {
    .venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace $nb.FullName
}
```

| Notebook | Contenu |
|---|---|
| 00_Data_Audit | Volumétrie et intégrité des fichiers, clés, cible, valeurs manquantes, anomalies, schéma relationnel |
| 01_Feature_Engineering | Contrôle de la table de modélisation : sentinelles, agrégats, contrôles bloquants, familles de variables, couverture des historiques |
| 02_EDA | Analyse exploratoire sur le train seul : taux de défaut par segment, forme des relations, manquants informatifs |
| 03_WoE_Binning | Binning optimal, WoE et IV, monotonie, variables à IV élevé |
| 04_Scorecard | Entonnoir de sélection, régression logistique, grille de score, ROC et KS, défaut par tranche |
| 05_Challenger_SHAP | Challenger LightGBM, ablation `EXT_SOURCE`, importance des variables, SHAP global et individuel |
| 06_Cutoff_Strategy | Évaluation finale sur le test, calibration, PSI, équité, motifs de refus, scénarios de seuil |
| 07_Final_Synthesis | Chiffres clés, figures clés, recommandation |

Tous les scripts sont idempotents et ne suppriment rien dans `data/raw/`.

## Résultats

Chiffres issus de l'exécution (`output/tables/`, test de 46 127 demandes lu uniquement par `scripts/evaluate_models.py`, chaque lecture journalisée ; IC 95 % par bootstrap, 1 000 rééchantillonnages) :

<!-- RESULTS:START -->
- **Grille de score** (17 variables, 439 à 660 points) : AUC test **0,7518** [0,7437 ; 0,7598], Gini **0,5035** [0,4874 ; 0,5196], KS 0,3762 ; AUC train 0,7544, validation 0,7529.
- **Challenger LightGBM** (200 variables) : AUC test **0,7883** [0,7809 ; 0,7960], soit **+0,0365** [0,0319 ; 0,0408] sur la grille (écart significatif), au prix d'un sur-apprentissage (AUC train 0,8808) et d'une explicabilité post-hoc (SHAP) ; la grille reste le modèle de décision.
- **Calibration et stabilité** : PD moyenne de la grille 8,05 % pour 8,07 % de défaut observé, écart moyen par décile 0,20 pt (max 0,40 pt) → aucune recalibration ; PSI du score train → test 0,0001, PSI max des variables 0,0006.
- **Seuil recommandé — scénario Prudent, 563 points** : acceptation 60,3 %, défaut des acceptés **3,44 %** contre 8,07 % sans seuil, **69,9 %** de la perte attendue évitée (LGD 45 %), 36,7 % des bons clients refusés ; zone de revue 553–572 (25,4 % des demandes).
- **Point de vigilance équité** (`CODE_GENDER`, exclu du modèle) : ratio d'acceptation M / F 0,821 (règle des 4/5 respectée), mais 0,841 parmi les seuls bons clients — les hommes solvables sont plus souvent refusés ; à soumettre à une revue de conformité.

Synthèse pour décision : [`docs/note_comite_credit.md`](docs/note_comite_credit.md) · [Guide Power BI (tableau de bord à venir)](docs/powerbi_guide.md)
<!-- RESULTS:END -->

Détail par phase :

- Phase 1 — Ingestion et audit qualité (`notebooks/00_Data_Audit.ipynb`, [`docs/data_quality_report.md`](docs/data_quality_report.md)).
  - 9 CSV (2 559 Mo) chargés dans DuckDB, soit **58,5 M de lignes** sur 8 tables. Aucun fichier tronqué : pour chaque table, les lignes du CSV égalent les lignes chargées.
  - `application_train` : **307 511 demandes**, taux de défaut **8,07 %** ; `SK_ID_CURR` unique dans le train et le test.
  - `DAYS_EMPLOYED = 365243` (valeur sentinelle) : 18,01 % des demandes, taux de défaut 5,40 % contre 8,66 % pour les autres.
  - 41 colonnes sur 122 ont au moins 50 % de valeurs manquantes (surtout des variables de logement).
- Phase 2 — Table de modélisation (`scripts/build_features.py`, `notebooks/01_Feature_Engineering.ipynb`, [`docs/feature_catalog.md`](docs/feature_catalog.md)).
  - Les 7 tables d'historique sont agrégées en SQL au grain `SK_ID_CURR`, puis jointes à gauche sur la demande : `model_table_train` compte **307 511 lignes × 208 colonnes** et `model_table_test` 48 744 lignes × 207 colonnes (sans `TARGET`).
  - **86 variables créées** (`APP_` 14, `BUR_` 11, `BB_` 8, `PREV_` 15, `INS_` 12, `POS_` 8, `CC_` 12, `HAS_` 6), en plus des 120 colonnes brutes de la demande. Volume accepté après revue (D13 amendé le 29/09).
  - Valeur sentinelle 365243 → NULL, uniquement dans les 7 colonnes où elle apparaît. Aucune valeur infinie ni NaN dans la table modèle.
  - Part des demandes du train ayant un historique : échéances 94,84 %, demandes antérieures 94,65 %, POS 94,12 %, bureau 85,69 %, historique mensuel du bureau 29,99 %, cartes 28,26 %.
- Phase 3 — Découpage et grille de score ([`docs/scorecard_report.md`](docs/scorecard_report.md)).
  - **Découpage 70/15/15** stratifié sur `TARGET` (`scripts/make_splits.py`) : 215 257 / 46 127 / 46 127 demandes, taux de défaut de 8,07 % dans chaque échantillon. Test scellé (empreinte SHA-256 `549e21fc…e660`) : il n'est lu que par `scripts/evaluate_models.py` (aucune sélection ni réglage dessus) ; chaque lecture est journalisée dans `models/test_access_log.csv`, empreinte conforme ; le pipeline étant déterministe, chaque exécution redonne les mêmes résultats.
  - **Analyse exploratoire sur le train seul** (`notebooks/02_EDA.ipynb`) : 200 variables candidates ; `APP_EXT_SOURCE_MEAN` passe de 22,99 % de défaut dans le 1er décile à 1,98 % dans le dernier.
  - **Grille** (`scripts/train_scorecard.py`) : entonnoir 200 → 82 (IV ≥ 0,02) → 41 (corrélation des WoE) → 20 (plafond) → **17** (p-valeur et signe) ; 0 WoE non monotone ; tous les coefficients négatifs.
- Phase 4 — Challenger, évaluation, seuil (`train_challenger.py`, `evaluate_models.py`, `build_cutoff_strategy.py` ; [`docs/model_performance_report.md`](docs/model_performance_report.md)).
  - Sans les 5 variables `EXT_SOURCE`, LightGBM perd 0,0285 d'AUC au test ; seuils choisis sur la validation, évalués sur le test.
- Phase 5 — Restitution (`export_to_powerbi.py`, `build_reports.py`) : note au comité de crédit ([`docs/note_comite_credit.md`](docs/note_comite_credit.md)), model card ([`docs/model_card.md`](docs/model_card.md)), notebook `07_Final_Synthesis`. Le tableau de bord Power BI n'est pas réalisé dans cette version : les exports `powerbi_data/` et le guide ([`docs/powerbi_guide.md`](docs/powerbi_guide.md)) sont prêts.

Dictionnaire de données : [`docs/data_dictionary.md`](docs/data_dictionary.md) · Historique des versions et des décisions : [`docs/changelog.md`](docs/changelog.md).

## Limites connues

- Tableau de bord Power BI non construit : les exports CSV (`powerbi_data/`, régénérés par `scripts/export_to_powerbi.py`) et le guide de construction ([`docs/powerbi_guide.md`](docs/powerbi_guide.md)) sont prêts, le rapport `.pbix` reste à construire et à contrôler.
- Pas de date d'octroi : aucune validation out-of-time.
- Données non africaines : Home Credit n'est pas un portefeuille camerounais ; la transposition au marché CEMAC est argumentée, pas mesurée.
- PD uniquement : LGD supposée (45 %, sensibilité 35–55 %), EAD = montant octroyé ; la perte attendue est un ordre de grandeur.
- LightGBM sur-appris (AUC train 0,8808 contre test 0,7883) : il reste challenger et référence de performance, pas modèle de décision.
- Équité : `CODE_GENDER` est exclu du modèle, mais le ratio d'acceptation M / F vaut 0,821, et 0,841 parmi les seuls bons clients ; point à surveiller et à soumettre à une revue de conformité.
- Biais de sélection : défaut observé sur les seuls dossiers acceptés par le passé, sans inférence des refusés.
- Motifs de refus dominés par le score externe `APP_EXT_SOURCE_MEAN` (1er motif de 99,5 % des refus), peu explicable au client tel quel.

## Auteure

Cely — [linkedin.com/in/m-cely](https://linkedin.com/in/m-cely)
