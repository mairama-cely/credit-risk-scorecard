# Cahier des charges — Credit Risk Scorecard

> Projet bancaire n°1 du portfolio de candidature Afriland First Bank (« Experts Data, Big Data, IA et Data Science »).
> Échéance candidature : **20 octobre 2026** · Fin prévisionnelle du projet 1 : **4 octobre 2026** · Fin effective : **7 octobre 2026**.
> Version du document : **0.6.2 — 2026-10-08** · Référence unique du projet (fusion du cadrage v0.1.0 du dépôt et du cahier v2.1).

---

## 0. Suivi du document

### 0.1 État d'avancement
| Phase | Statut | Détail |
|---|---|---|
| 0 — Cadrage et environnement | ✅ | Squelette du dépôt, README, `.gitignore`, `requirements.txt`, `.venv` (Python 3.13.15), dépendances installées |
| 1 — Ingestion et audit qualité | ✅ | Terminée le 29/09 : 9 CSV intègres (58 490 112 lignes), 307 511 demandes, défaut 8,07 %, `SK_ID_CURR` unique, sentinelle `DAYS_EMPLOYED` chiffrée (18,01 %). Image Kaggle retirée du dépôt au profit d'un schéma Mermaid généré dans `docs/data_dictionary.md` |
| 2 — Feature engineering SQL | ✅ | Terminée le 29/09 (commit `fd84183`) : `model_table_train` 307 511 × 208, `model_table_test` 48 744 × 207 ; 86 variables créées (D13 amendé) ; 17 contrôles bloquants ; transaction ; reproductibilité exacte (mono-thread) ; relecture du SQL (paiements fractionnés, fenêtres exactes) |
| 3 — Split, EDA, WoE/IV, scorecard | ✅ | Terminée le 07/10 : split 215 257 / 46 127 / 46 127, test scellé ; 200 candidates → **17 variables** ; AUC train 0,7544, validation 0,7529 (écart 0,0014) ; grille de 439 à 660 points (`docs/scorecard_report.md`) |
| 4 — Validation, challenger, cut-off | ✅ | Terminée le 07/10 : test lu uniquement par `evaluate_models.py`, chaque lecture journalisée ; AUC test grille 0,7518 [0,7437 ; 0,7598], LightGBM 0,7883 [0,7809 ; 0,7960] ; grille calibrée, aucune recalibration ; seuil recommandé **563 points** (Prudent) (`docs/model_performance_report.md`) |
| 5 — Restitution | ✅ | Terminée le 07/10 : exports `powerbi_data/` et guide Power BI, note au comité, model card, notebook `07_Final_Synthesis`, README final (v0.6.0). Tableau de bord Power BI (`.pbix`) : **Reporté — à faire après** (D28) |
| Bonus — Application Streamlit | ⬜ | Après envoi de la candidature |

### 0.2 Journal des versions
| Version | Date | Changement |
|---|---|---|
| 0.1.0 | 26/09 | Cadrage initial en 9 phases (dépôt) |
| 0.2.0 | 26/09 | Fusion avec le cahier v2.1 : 5 phases, split 70/15/15, VIF et stabilité des WoE conservés, Streamlit en bonus, Python 3.13 et pandas 3 pris en compte. Données téléchargées manuellement : `fetch_data.py` remplacé par `verify_raw_data.py` (vérification, pas de téléchargement) ; schéma officiel des tables ajouté |
| 0.2.1 | 29/09 | Phase 1 validée. Schéma Kaggle retiré (droits de republication incertains) et remplacé par un diagramme Mermaid généré par `build_metadata.py`. Archives .zip supprimées avant la phase. Scripts ajoutés : `config.py`, `quality_checks.py`, `build_metadata.py`. Décisions de la Phase 2 proposées, à valider (§12) |
| 0.2.2 | 29/09 | Décisions D1 à D13 validées ; prompt de la Phase 2 ajouté (annexe B). Nouvelle règle : Claude Code n'exécute plus de commande git d'écriture, le commit est fait après relecture (`git diff`) |
| 0.2.3 | 29/09 | D13 amendé : 86 variables créées acceptées. Relecture du SQL de la Phase 2 : échéances regroupées au grain échéance (paiements fractionnés), fenêtre `_12M` de `bureau_balance` à 12 mois exacts, encours NULL si montants inconnus, ajout de `BUR_NB_SOLD_OR_BAD_DEBT`, construction mono-thread (reproductibilité exacte) |
| 0.3.0 | 30/09 | Phase 2 validée (commit `fd84183`). Changement de méthode à partir de la Phase 3 : fichiers complets fournis dans le chat, copiés par Cely (§0.5). Plan détaillé de la Phase 3 et décisions D14 à D22 proposées (§12). Arborescence mise à jour (`models/`, scripts de la Phase 3) |
| 0.3.1 | 30/09 | Restructuration sur le modèle du projet réfugiés : `db/` + `sql/` → `database/` ; `reports/` → `docs/` (rapports) et `output/` (figures `NN_nom.png`, `tables/`) ; `dashboards/exports/` → `powerbi_data/` ; fichiers racine en minuscules ; scripts renommés (`load_to_database.py`, `run_quality_checks.py`, `build_feature_catalog.py`) ; un notebook par étape (00 → 07). Décisions D14 à D22 validées ; sous-ensembles 3a (split) et 3b (EDA) terminés |
| 0.4.0 | 07/10 | Sous-ensembles 3c à 3e terminés : `train_scorecard.py`, notebooks 03 et 04 ; 17 variables retenues (D23). Changement de méthode : Claude écrit les fichiers directement dans le dépôt par sous-agents (§0.5) |
| 0.5.0 | 07/10 | Phase 4 terminée : `train_challenger.py`, `evaluate_models.py` (seul script qui lit le test, lectures journalisées), `build_cutoff_strategy.py`, notebooks 05 et 06 ; décisions D24 à D26 (modèle de décision, seuil 563, pas de recalibration isotone) ; vigilance équité consignée (D27) |
| 0.6.0 | 07/10 | Phase 5 terminée : `export_to_powerbi.py`, `build_reports.py`, guide Power BI, note au comité, model card, notebook 07 ; README final ; arborescence (§11) et checklists mises à jour |
| 0.6.1 | 08/10 | Power BI reporté en tâche ultérieure (D28) |
| 0.6.2 | 08/10 | Préparation de la publication (D29) : racine réduite, changelog et dictionnaire dans `docs/`, manifestes sha256, notebooks sans chemin local ; formulation de l'accès au test corrigée (lectures multiples, journalisées) |

### 0.3 Règle de documentation continue
Les fichiers Markdown sont mis à jour **pendant** le projet, jamais seulement à la fin.
- **Ce cahier** : mis à jour à chaque décision validée et à chaque fin de phase (statut, journal, contenu concerné).
- **README, changelog, metadata, rapports de `docs/`** : chaque prompt Claude Code impose leur mise à jour en fin de phase, avec les chiffres issus de l'exécution uniquement.
- Une phase n'est validée que si ces fichiers reflètent son état réel.
- Les fichiers de documentation du dépôt (README, changelog, ce cahier) sont mis à jour dans le même lot que le code (§0.5) ; `data_dictionary.md`, `feature_catalog.md`, `scorecard_report.md` et `model_performance_report.md` restent générés par leurs scripts.

### 0.4 Statut du calendrier
Les dates sont un **découpage prévisionnel**, pas une contrainte bloquante. La qualité et la validation de chaque phase priment ; un glissement est acceptable, mais il est consigné en §0.1.

### 0.5 Méthode de travail
- **Depuis la version 0.4.0 (sous-ensemble 3c)** : Claude écrit les fichiers directement dans le dépôt, par l'intermédiaire de sous-agents (scripts, notebooks, documentation) ; Cely relit le diff (`git diff`) et fait elle-même le commit. Claude n'exécute aucune commande git d'écriture.
- **Phase 3a-3b (version 0.3.x)** : Claude fournissait le contenu complet de chaque fichier dans le chat (code des cellules pour les notebooks), copié par Cely dans VS Code.
- **Un sous-ensemble à la fois** : chaque fichier (ou petit groupe de fichiers liés) est exécuté et validé avant le suivant.
- **Emplacements** : SQL dans `database/` ; figures `output/NN_nom.png` (NN = numéro du notebook) ; tableaux de résultats dans `output/tables/` (versionnés) ; `models/` et `powerbi_data/` non versionnés, régénérés par les scripts.
- **Avant chaque commit** : `git status` et `git diff --stat` relus ; aucun `.csv`, `.parquet` ni `.duckdb` suivi. Messages de commit entre **guillemets simples** (PowerShell interprète les guillemets doubles).
- **VS Code** : fermer sans enregistrer l'onglet d'un fichier avant de le remplacer, pour éviter qu'un ancien onglet ne l'écrase (incident du 29/09 sur `build_metadata.py`).
- Les phases 1 et 2 ont été exécutées par Claude Code (annexes A0, A et B, conservées pour mémoire).

---

## 1. Contexte

Une banque de détail en Afrique centrale octroie des crédits à une clientèle dont l'historique de crédit est souvent **faible ou inexistant**. L'octroi repose largement sur l'appréciation manuelle de l'analyste crédit, ce qui produit des décisions hétérogènes, lentes et difficiles à auditer.

Le jeu **Home Credit Default Risk** (Kaggle, 2018) reproduit ce problème : Home Credit prête à des populations sous-bancarisées et cherche à prédire leur capacité de remboursement à partir de données socio-démographiques, du bureau de crédit et de son historique interne.

## 2. Problématique

> Peut-on construire une **grille de score interprétable** qui estime la probabilité de défaut (PD) d'un demandeur, classe les dossiers par niveau de risque, justifie chaque refus et permet de fixer un seuil d'acceptation chiffré en taux d'approbation et en taux de défaut attendu ?

## 3. Missions de la fiche de poste couvertes

| Mission | Démonstration |
|---|---|
| Analyse prédictive | Phases 3 et 4 : scorecard et challenger LightGBM |
| Analyse décisionnelle | Phase 4 : stratégie de cut-off fondée sur le coût métier |
| Gouvernance des données | Phase 1 (audit, dictionnaire, intégrité) et §9 (équité, traçabilité) |

## 4. Objectifs

| # | Objectif | Critère de réussite |
|---|---|---|
| O1 | Modèle PD interprétable (régression logistique sur WoE) | Gini ≥ 0,45 sur le test (repère, à confirmer après EDA) |
| O2 | Grille de points lisible par un analyste crédit | Variable → classes → points ; plage de score visée ~300 à ~850 (repère) |
| O3 | Validation conforme aux pratiques de validation de modèles | AUC, Gini, KS, calibration par déciles, Brier, PSI, stabilité des WoE, intervalles bootstrap |
| O4 | Benchmark challenger | LightGBM + SHAP : écart de performance chiffré contre la scorecard |
| O5 | Stratégie d'octroi | Courbe taux d'approbation / taux de défaut, 3 scénarios de cut-off, zones accord / examen / refus |
| O6 | Restitution | Dashboard Power BI, note d'une page au comité de crédit, model card, README |

## 5. Parties prenantes simulées

| Acteur | Attente |
|---|---|
| Comité de crédit | Grille explicable et seuil recommandé |
| Direction des risques | PD calibrées, stabilité vérifiée, limites documentées |
| Direction commerciale | Impact du seuil sur le taux d'approbation |
| Conformité | Traçabilité, motifs de refus, absence de variables discriminantes |

## 6. Périmètre

**Inclus**
- PD au niveau de la demande de crédit (`SK_ID_CURR`).
- Tables : `application_train`, `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `POS_CASH_balance`, `credit_card_balance`.

**Exclus, et déclarés comme limites**
- LGD et EAD (pas de données de recouvrement ni d'exposition).
- `application_test` pour l'évaluation (pas de cible) : chargé, jamais utilisé pour mesurer la performance.
- Validation out-of-time (pas de date d'octroi).
- Reject inference (population des seuls dossiers acceptés).
- Déploiement en production.

---

## 7. Données

### 7.1 Source et accès
- Kaggle, compétition `home-credit-default-risk`.
- **Mode retenu : téléchargement manuel** depuis l'onglet Data de la compétition. L'API Kaggle n'est pas utilisée ; le jeton n'est donc pas requis.
- Volume constaté : 9 CSV pour environ 2,5 Go décompressés. L'intégrité (fichiers non tronqués) est vérifiée par le comptage des lignes en Phase 1.

### 7.2 Tables et clés
Comptes indicatifs, **re-vérifiés en Phase 1** ; seuls les chiffres issus de l'exécution entrent dans les livrables.

| Table DuckDB | Grain (1 ligne =) | Lignes (approx.) | Clés |
|---|---|---|---|
| `application_train` | 1 demande, avec `TARGET` | ~307 500 | `SK_ID_CURR` |
| `application_test` | 1 demande, sans `TARGET` | ~48 700 | `SK_ID_CURR` |
| `bureau` | 1 crédit externe | ~1,7 M | `SK_ID_BUREAU`, `SK_ID_CURR` |
| `bureau_balance` | 1 mois d'un crédit externe | ~27 M | `SK_ID_BUREAU` |
| `previous_application` | 1 demande antérieure | ~1,7 M | `SK_ID_PREV`, `SK_ID_CURR` |
| `pos_cash_balance` | 1 mois d'un prêt POS/cash antérieur | ~10 M | `SK_ID_PREV`, `SK_ID_CURR` |
| `installments_payments` | 1 échéance d'un prêt antérieur | ~13,6 M | `SK_ID_PREV`, `SK_ID_CURR` |
| `credit_card_balance` | 1 mois d'une carte antérieure | ~3,8 M | `SK_ID_PREV`, `SK_ID_CURR` |
| `homecredit_columns_description` | Dictionnaire | — | — |

### 7.3 Schéma des jointures
```
application ──┬── bureau ── bureau_balance
              └── previous_application ──┬── pos_cash_balance
                                         ├── credit_card_balance
                                         └── installments_payments
```
Précision tirée de la documentation de la compétition (schéma relationnel en Mermaid dans `docs/data_dictionary.md`) : `pos_cash_balance`, `installments_payments` et `credit_card_balance` portent aussi `SK_ID_CURR` et peuvent être agrégées directement au niveau client, sans passer par `previous_application`.

### 7.4 Pièges connus
| Piège | Constat (Phase 1) | Traitement (Phase 2 ou 3) |
|---|---|---|
| `DAYS_EMPLOYED = 365243` (sentinelle) | Effectif et taux de défaut propre | NULL + indicateur `FLAG_DAYS_EMPLOYED_ANOM` |
| `DAYS_*` négatifs | Contrôle des valeurs positives anormales | Conversion en années positives |
| `CODE_GENDER = 'XNA'` | Effectif | Documenté ; variable exclue du modèle |
| Déséquilibre (défaut ≈ 8 %) | Distribution exacte | Stratification ; AUC/KS ; pas de sur-échantillonnage ; pondération testée seulement si nécessaire |
| `EXT_SOURCE_1/2/3` très prédictifs | Taux de manquants | Ablation en Phase 4 |
| Duplication par jointure | — | Agrégation au grain `SK_ID_CURR` avant jointure ; contrôle du nombre de lignes |
| Encodage du dictionnaire | Détection | UTF-8, sinon latin-1 / cp1252 |

---

## 8. Choix méthodologiques

| Sujet | Décision | Justification |
|---|---|---|
| Cible | `TARGET` (1 = difficultés de paiement) | Définition Home Credit |
| Découpage | **Train 70 % / Validation 15 % / Test 15 %**, stratifié sur `TARGET`, `random_state=42`, fait **avant tout binning** | La validation sert à l'early stopping et au choix du seuil ; le test reste scellé jusqu'à l'évaluation finale. Pas de date → pas d'out-of-time (limite documentée) |
| Discrétisation | Binning optimal monotone (`optbinning`), ajusté sur le train seul | Standard des scorecards, monotonie = interprétabilité |
| Sélection | IV ≥ 0,02 ; IV > 0,5 inspecté (suspicion de fuite) ; corrélation des WoE < 0,7 (garder l'IV le plus élevé) ; VIF < 5 | Seuils usuels de la littérature scorecard (Siddiqi) |
| Modèle | Régression logistique sur WoE, 12 à 20 variables, coefficients de signe cohérent | Explicable variable par variable |
| Mise à l'échelle | Score 600 pour des odds de 50:1, PDO = 20 | Convention courante, paramétrable |
| Variables sensibles | `CODE_GENDER` exclu du modèle, utilisé seulement en audit d'équité | Non-discrimination |
| Déséquilibre | Pas de sur-échantillonnage | Préserver la calibration de la PD |
| Challenger | LightGBM, early stopping sur validation, `scale_pos_weight` comparé à l'absence de pondération | Référence du secteur sur données tabulaires |
| Perte attendue | PD × LGD × EAD, **LGD supposée** (ex. 45 %, convention) + analyse de sensibilité | Pas de données de recouvrement |

---

## 9. Gouvernance, conformité, équité
- **Exclusions :** `CODE_GENDER` et toute variable jugée discriminante, chaque exclusion étant justifiée dans la model card.
- **Audit d'équité :** taux d'approbation et de défaut par genre, mesurés après exclusion.
- **Motifs de refus :** pour chaque refus, les 3 variables ayant le plus coûté en points, base d'une lettre de motif.
- **Traçabilité :** chaque variable reliée à sa table source et à sa formule (`docs/data_dictionary.md`, `docs/feature_catalog.md`).
- **Contexte régional :** supervision bancaire CEMAC par la COBAC, sans règle spécifique inventée ; on parle des bonnes pratiques de gestion du risque de crédit issues de Bâle.

---

## 10. Stack technique

| Couche | Outil |
|---|---|
| Langage | Python 3.13.15 (installation et imports validés le 26/09) |
| Stockage analytique | DuckDB (`database/credit_risk.duckdb`) + Parquet |
| SQL | Fichiers `database/*.sql` exécutés sur DuckDB |
| Scorecard | `optbinning`, `scikit-learn`, `statsmodels` |
| Challenger | `lightgbm`, `shap` |
| Visualisation | `matplotlib`, `seaborn` |
| Notebooks | `jupyterlab`, `ipykernel`, exécution par `nbconvert` / `nbclient` |
| Dashboard | Power BI (exports CSV `powerbi_data/`) |
| Application (bonus) | Streamlit |
| Dépendances | `requirements.txt` (dépendances directes, versions exactes `==` relevées dans l'environnement validé) |

**Point d'attention :** l'environnement contient **pandas 3.0**, version majeure dont certains comportements par défaut diffèrent de pandas 2 (copie à l'écriture, type chaîne par défaut). Tout code doit être écrit et testé pour pandas 3.

Justification de DuckDB (README) : moteur SQL analytique embarqué, choisi pour traiter plusieurs dizaines de millions de lignes localement sans infrastructure ; les requêtes sont portables vers un SGBD bancaire moyennant quelques ajustements de syntaxe.

---

## 11. Arborescence

```
credit-risk-scorecard/
├── README.md
├── requirements.txt                   versions exactes
├── .gitignore
├── data/                              non versionné
│   ├── raw/                           9 CSV Kaggle
│   ├── interim/                       split_assignment.parquet (P3)
│   ├── processed/                     model_table_train / _test.parquet (P2)
│   └── final/                         sorties scorées
├── database/
│   ├── credit_risk.duckdb             (non versionné)
│   ├── 00_quality_checks.sql          (P1)
│   ├── 01_application_features.sql … 06_credit_card_features.sql   (P2)
│   └── 10_model_table.sql             (P2)
├── scripts/
│   ├── config.py                      chemins et constantes
│   ├── verify_raw_data.py             (P1)
│   ├── load_to_database.py            (P1)
│   ├── run_quality_checks.py          (P1)
│   ├── build_metadata.py              (P1) génère docs/data_dictionary.md
│   ├── build_features.py              (P2)
│   ├── build_feature_catalog.py       (P2) génère docs/feature_catalog.md
│   ├── make_splits.py                 (P3) split 70/15/15, accès contrôlé au test
│   ├── train_scorecard.py             (P3) binning, sélection, régression, grille
│   ├── train_challenger.py            (P4) LightGBM, ablation EXT_SOURCE, SHAP
│   ├── evaluate_models.py             (P4) seul lecteur du test (journalisé), calibration, PSI, équité
│   ├── build_cutoff_strategy.py       (P4) scénarios de seuil, perte attendue
│   ├── export_to_powerbi.py           (P5) génère powerbi_data/
│   ├── build_reports.py               (P5) note au comité, model card
│   └── build_manifest.py              empreintes sha256 (data/raw, models)
├── notebooks/
│   ├── 00_Data_Audit.ipynb            (P1)
│   ├── 01_Feature_Engineering.ipynb   (P2)
│   ├── 02_EDA.ipynb                   (P3)
│   ├── 03_WoE_Binning.ipynb           (P3)
│   ├── 04_Scorecard.ipynb             (P3)
│   ├── 05_Challenger_SHAP.ipynb       (P4)
│   ├── 06_Cutoff_Strategy.ipynb       (P4)
│   └── 07_Final_Synthesis.ipynb       (P5)
├── output/                            versionné
│   ├── NN_nom.png                     figures (NN = numéro du notebook, 00 à 07)
│   └── tables/                        CSV et JSON de résultats (P3-P4)
├── docs/
│   ├── cahier_des_charges.md
│   ├── changelog.md
│   ├── data_dictionary.md             généré par build_metadata.py
│   ├── data_quality_report.md         (P1)
│   ├── feature_catalog.md             (P2)
│   ├── scorecard_report.md            (P3) généré par train_scorecard.py
│   ├── model_performance_report.md    (P4) généré par build_cutoff_strategy.py
│   ├── powerbi_guide.md               (P5)
│   ├── note_comite_credit.md          (P5)
│   └── model_card.md                  (P5)
├── models/                            binning, logit, LightGBM, scores (non versionnés ; MANIFEST_models.json et test_access_log.csv versionnés)
└── powerbi_data/                      exports CSV Power BI (non versionnés)
```

Conventions : notebook = cellule Markdown de titre, puis cellule de setup vérifiant le répertoire de travail ; scripts idempotents ; aucun chiffre non issu d'une exécution ; une entrée CHANGELOG par phase (P0 = 0.1.0, P1 = 0.2.0 … P5 = 0.6.0).

---

## 12. Phases

Phases 1 et 2 : une phase = un prompt Claude Code. Phase 3a-3b : fichiers complets fournis dans le chat. À partir de 3c : fichiers écrits dans le dépôt par sous-agents Claude, diff relu et commit par Cely (§0.5). Un sous-ensemble à la fois. Passage à la phase suivante uniquement quand la checklist est entièrement cochée.

| Phase | Dates prévisionnelles | Contenu | Livrable clé |
|---|---|---|---|
| 0 | 26/09 | Cadrage, dépôt, environnement | ✅ 26/09 |
| 1 | 26–27/09 | Vérification des fichiers, DuckDB, audit qualité | ✅ 29/09 |
| 2 | 28/09 | Feature engineering SQL sur les 7 tables | ✅ 29/09 |
| 3 | 30/09–01/10 | Split, EDA ciblée, WoE/IV, VIF, scorecard | ✅ 07/10 — grille de points |
| 4 | 02–03/10 | Validation complète, challenger, SHAP, cut-off | ✅ 07/10 — rapport de performance |
| 5 | 04/10 | Power BI, note au comité, model card, README | ✅ 07/10 — projet publiable |
| Bonus | après le 20/10 | Application Streamlit de scoring | — |

### Phase 1 — Ingestion et audit qualité
**Prompt :** annexe A0 puis annexe A.
**Prérequis :**
- [x] 9 CSV présents dans `data/raw/` (téléchargement manuel)
- [x] Test d'import des bibliothèques réussi sous Python 3.13 (duckdb, pandas, lightgbm, shap, optbinning, scikit-learn, statsmodels)
- [x] Claude Code lancé depuis la racine du dépôt

**Checklist :**
- [x] Les 9 CSV présents, comptes de lignes cohérents (aucun fichier tronqué) ; archives .zip supprimées avant la phase (écart constaté, sans conséquence)
- [x] `application_train` : 307 511 lignes, défaut 8,07 %
- [x] `SK_ID_CURR` unique dans les deux tables `application`
- [x] Anomalie `DAYS_EMPLOYED = 365243` chiffrée : 55 374 lignes (18,01 %), défaut 5,40 % contre 8,66 %
- [x] Notebook exécuté de bout en bout
- [x] Scripts relancés sans duplication
- [x] Aucun CSV, zip, `.duckdb` ni `kaggle.json` suivi par Git
- [x] README, CHANGELOG (0.2.0), METADATA et `data_quality_report.md` à jour

### Phase 2 — Feature engineering SQL
Agrégation de chaque table d'historique au grain `SK_ID_CURR` (un fichier SQL par table), puis jointure gauche sur `application_train` (et `application_test` par symétrie).
- **Demande :** crédit / revenu, annuité / revenu, crédit / prix du bien, durée implicite ; âge et ancienneté en années ; traitement de `DAYS_EMPLOYED`.
- **Bureau et bureau_balance :** crédits actifs et clos, encours, dette / montant accordé, retard maximal, part des mois en retard.
- **Demandes antérieures :** nombre, taux de refus, écart demandé / accordé.
- **Échéances :** retard moyen et maximal, payé / dû, part des paiements en retard.
- **POS et carte :** utilisation de la carte, DPD maximal, part des mois en impayé.

**Décisions issues de l'audit de la Phase 1** (`docs/data_quality_report.md`, §5), complétées. Statut : **validées le 29/09.** Prompt : **annexe B**.

| # | Décision |
|---|---|
| D1 | `DAYS_EMPLOYED = 365243` → NULL + `FLAG_DAYS_EMPLOYED_ANOM`. Ni imputation ni suppression (défaut propre de 5,40 %). Le drapeau recoupe presque totalement `NAME_INCOME_TYPE = 'Pensioner'` : colinéarité à contrôler au VIF en Phase 3 |
| D2 | Sentinelle 365243 des `DAYS_*` de `previous_application` → NULL **avant** toute agrégation |
| D3 | `DAYS_*` convertis en années positives (âge, ancienneté) |
| D4 | `CODE_GENDER` conservé dans la table modèle pour l'audit d'équité, marqué « exclu du modèle » dans le catalogue |
| D5 | `bureau_balance` agrégé via `bureau` (orphelins perdus, 5,27 %, documenté) ; `pos_cash_balance`, `installments_payments` et `credit_card_balance` agrégés directement par `SK_ID_CURR` |
| D6 | Agrégation au grain `SK_ID_CURR` avant jointure gauche ; contrôle strict : 307 511 lignes (train) et 48 744 (test) |
| D7 | Absence d'historique : les **comptages** valent 0 et un indicateur `HAS_<SOURCE>_HISTORY` est créé ; les **statistiques** (moyenne, max, ratio) restent NULL. Aucune suppression de colonne a priori : le manquant devient une classe du binning |
| D8 | `EXT_SOURCE_1/2/3` conservés tels quels ; ablation en Phase 4 |
| D9 | Aucune agrégation n'utilise `TARGET` (pas d'encodage cible en Phase 2) : toute information liée à la cible est calculée après le split, sur le train seul |
| D10 | Ratios : division par zéro ou dénominateur NULL → NULL, jamais 0 ni infini |
| D11 | `bureau_balance.STATUS` : codes 1 à 5 = retard, 0 = à jour, C = clôturé, X = inconnu ; X exclu du dénominateur des parts de mois en retard |
| D12 | Fenêtres temporelles limitées à deux horizons (historique complet et 12 derniers mois) pour les tables mensuelles, afin de maîtriser le nombre de variables |
| D13 | Volume : de l'ordre de 100 à 200 variables en sortie ; chaque variable documentée dans `feature_catalog.md`. **Amendé le 29/09 :** 86 variables créées acceptées (≈ 206 candidates avec les colonnes brutes), sans ajout artificiel. Des variables ciblées pourront être ajoutées en Phase 4 si l'analyse du challenger le justifie, et documentées |

**Checklist :**
- [x] Nombre de lignes de la table modèle = nombre constaté en Phase 1, exactement (307 511 × 208 ; 48 744 × 207)
- [x] Chaque variable documentée (nom, source, formule, sens attendu) dans `feature_catalog.md` (208 entrées ; le script échoue en cas d'écart)
- [x] Pipeline idempotent, table exportée en Parquet ; reproductibilité exacte vérifiée (comparaison stricte de deux exécutions)
- [x] Documentation à jour (0.3.0) ; commit `fd84183`

**Relecture du 29/09 (corrections intégrées au commit de la Phase 2) :** échéances regroupées au grain échéance (640 905 échéances payées en plusieurs fois) ; fenêtre `_12M` de `bureau_balance` ramenée à 12 mois exacts (`>= -11`, le mois courant valant 0) ; encours bureau NULL si les montants des crédits actifs sont tous inconnus ; `BUR_NB_SOLD_OR_BAD_DEBT` ajouté (`Bad debt` seul : 21 crédits, quasi constant) ; construction en mono-thread.

### Phase 3 — Split, EDA, WoE/IV, scorecard
**Méthode :** 5 sous-ensembles validés l'un après l'autre ; 3a-3b fournis dans le chat, 3c-3e écrits dans le dépôt par sous-agents (§0.5).

| Sous-ensemble | Contenu | Fichiers | Validation avant de passer au suivant |
|---|---|---|---|
| 3a — Split | Découpage 70/15/15 stratifié sur `TARGET`, persisté ; accès au test verrouillé | `scripts/make_splits.py` | Tailles exactes, taux de défaut par échantillon, échantillons disjoints, relance identique |
| 3b — EDA ciblée | Taux de défaut par segment et rôle des manquants, **train seul** | `notebooks/02_EDA.ipynb` | Aucune lecture du test ni de la validation |
| 3c — Binning | Binning optimal monotone des variables candidates, ajusté sur le train | `scripts/train_scorecard.py` (partie binning), `notebooks/03_WoE_Binning.ipynb` | Table des IV ; variables à IV > 0,5 listées pour revue |
| 3d — Sélection | Filtres IV, corrélation des WoE, VIF ; 12 à 20 variables | `scripts/train_scorecard.py` (partie sélection) | `output/tables/iv_table.csv` avec le motif de chaque exclusion |
| 3e — Régression et grille | Régression logistique sur WoE, contrôle des signes, mise à l'échelle, métriques train / validation | `scripts/train_scorecard.py` (fin), `notebooks/04_Scorecard.ipynb`, `docs/scorecard_report.md`, `output/tables/scorecard_table.csv` | Checklist ci-dessous |

**Décisions de la Phase 3.** Statut : **validées le 30/09.**

| # | Décision |
|---|---|
| D14 | Split : deux `train_test_split` successifs de scikit-learn (70 % / 30 %, puis 50 / 50 du reste), stratifiés sur `TARGET`, `random_state = 42`. Affectation persistée dans DuckDB (table `split_assignment`, 1 ligne par `SK_ID_CURR`) et dans `data/processed/split_assignment.parquet` |
| D15 | Test scellé : une seule fonction d'accès aux échantillons, qui refuse le test sauf autorisation explicite (réservée à la Phase 4). Une empreinte de la liste des identifiants du test est consignée dans le rapport, pour prouver qu'elle n'a pas changé |
| D16 | Variables candidates : uniquement celles au statut « candidate » dans `feature_catalog.py`. Sont donc exclus d'office : `SK_ID_CURR`, `TARGET`, `CODE_GENDER` (D4) et les `DAYS_*` bruts (doublons des `APP_*_YEARS`) |
| D17 | Binning : `BinningProcess` d'`optbinning`, ajusté sur le train seul ; tendance monotone déterminée automatiquement pour les variables numériques ; au moins 5 % des individus par classe ; valeurs manquantes dans une classe à part (D7) ; variables catégorielles regroupées selon leur taux de défaut |
| D18 | IV : exclusion si IV < 0,02 ; IV > 0,5 **conservé mais signalé** pour revue manuelle (suspicion de fuite ou variable dominante, par exemple les `EXT_SOURCE`) |
| D19 | Redondance : si deux WoE ont une corrélation > 0,7, on garde la variable d'IV le plus élevé ; puis élimination itérative de la variable au VIF le plus élevé tant qu'un VIF dépasse 5. S'il reste plus de 20 variables, on garde les 20 d'IV le plus élevé |
| D20 | Régression logistique non pondérée (pas de rééquilibrage, pour préserver la calibration de la PD, §8) avec `statsmodels`, pour disposer des p-valeurs ; retrait itératif des variables non significatives (p > 0,05) ; tous les coefficients doivent avoir le même signe, cohérent avec la convention de WoE d'`optbinning` (convention vérifiée en 3c avant d'écrire le contrôle) |
| D21 | Mise à l'échelle : 600 points pour des odds de 50:1, PDO = 20, via la classe `Scorecard` d'`optbinning` si elle expose ces paramètres dans la version installée (1.0.0), sinon calcul explicite `points = offset - factor × ln(odds)` documenté |
| D22 | Artefacts : binning et modèle sérialisés dans `models/` (non versionnés, reproductibles par le script) ; grille `output/tables/scorecard_table.csv` et `output/tables/iv_table.csv` versionnées |

**Checklist :**
- [x] Split conforme : 215 257 / 46 127 / 46 127 lignes, taux de défaut 8,07 % dans chaque échantillon, échantillons disjoints, relance identique (mêmes empreintes)
- [x] Test jamais lu ; binning ajusté sur le train seul
- [x] 17 variables retenues, chacune justifiée dans `iv_table.csv` ; 17 coefficients négatifs (signe cohérent) ; p-valeurs < 0,05
- [x] AUC, Gini, KS sur train et validation ; écart d'AUC 0,0014 < 0,02
- [x] Grille exportée en CSV, IV et VIF tabulés, `scorecard_report.md`
- [x] Documentation à jour (0.4.0)

**Décision de résultat (07/10) :**

| # | Décision |
|---|---|
| D23 | Grille à **17 variables** (entonnoir 200 → 82 → 41 → 41 → 20 → 17) ; `APP_EXT_SOURCE_MEAN` (IV 0,6287 > 0,5) conservée après revue ; discordance de sens a priori sur `PREV_MEAN_CREDIT_APPLICATION_RATIO` documentée, variable conservée (WoE monotone, coefficient négatif) |

### Phase 4 — Validation, challenger, SHAP, cut-off
- LightGBM avec early stopping sur la validation ; ablation `EXT_SOURCE` pour les deux modèles.
- Calibration par déciles et Brier ; recalibration isotonique si nécessaire.
- Stabilité des WoE entre train et validation ; intervalles bootstrap pour AUC et Gini.
- SHAP : importance globale, dépendances des 5 variables principales, 3 cas individuels (accord, refus, cas limite).
- **Test lu par un seul script** (`evaluate_models.py`, aucune sélection ni réglage dessus) pour le tableau comparatif final ; PSI du score train/test (attendu faible car split aléatoire, à écrire).
- Cut-off : déciles (effectif, défaut observé, PD moyenne, approbation cumulée), 3 scénarios, zones accord / examen / refus, perte attendue avec LGD supposée et sensibilité.

| Métrique (test) | Scorecard | LightGBM |
|---|---|---|
| AUC (IC 95 %) | 0,7518 [0,7437 ; 0,7598] | 0,7883 [0,7809 ; 0,7960] |
| Gini (IC 95 %) | 0,5035 [0,4874 ; 0,5196] | 0,5766 [0,5618 ; 0,5921] |
| KS | 0,3762 | 0,4384 |
| Brier | 0,0684 | 0,0659 |
| AUC sans EXT_SOURCE | non mesurée (pas d'ablation de la grille) | 0,7598 |
| Nombre de variables | 17 | 200 |
| Explicabilité | Native (points) | Post-hoc (SHAP) |

**Checklist :**
- [x] Test lu uniquement par `scripts/evaluate_models.py` (aucune sélection ni réglage dessus) ; chaque lecture est journalisée dans `models/test_access_log.csv` (empreinte conforme) ; le pipeline étant déterministe, chaque exécution redonne les mêmes résultats ; tableau rempli
- [x] Recommandation argumentée : modèle de décision et rôle du challenger (D24)
- [x] Seuil recommandé chiffré en approbation et défaut attendu ; hypothèses paramétrables (LGD, demi-largeur de la zone de revue)
- [x] Documentation à jour (0.5.0)

Écart d'AUC apparié LightGBM − grille : 0,0365 [0,0319 ; 0,0408], significatif. Ablation `EXT_SOURCE` réalisée sur LightGBM seulement : 3 des 17 variables de la grille dérivent de ces scores, une ablation de la grille imposerait de refaire sélection et régression.

**Décisions de résultat (07/10) :**

| # | Décision |
|---|---|
| D24 | **Grille de score = modèle de décision** (lisible, stable : AUC train 0,7544, test 0,7518) ; LightGBM conservé comme challenger et référence de performance (+0,0365 d'AUC, mais sur-apprentissage : AUC train 0,8808) |
| D25 | **Seuil recommandé : 563 points (scénario Prudent)**, choisi sur la validation par la règle « part de perte attendue évitée − part de bons clients refusés » (0,3321 contre 0,3153 Équilibré et 0,2614 Croissance). Test : acceptation 60,3 %, défaut des acceptés 3,44 % contre 8,07 %, 69,9 % de la perte attendue évitée (LGD 45 %) ; zone de revue 553–572 |
| D26 | **Pas de recalibration isotone** : grille calibrée au test (écart moyen par décile 0,20 pt, max 0,40 pt) ; le contrôle isotone ajusté sur la validation ne réduit pas le Brier (0,0685 contre 0,0684) |
| D27 | Équité : ratio d'acceptation M / F 0,821 (règle des 4/5 respectée), 0,841 parmi les bons clients ; consigné comme point de vigilance, à soumettre à une revue de conformité |

Repères indicatifs, non garantis : scorecard ≈ 0,74–0,77 d'AUC ; LightGBM avec agrégats ≈ 0,77–0,79. Jamais sur le CV ni dans un rapport avant obtention.

### Phase 5 — Restitution
- **Power BI :** vue portefeuille ; segments à risque ; simulateur de seuil (paramètre What-if) ; explicabilité (SHAP, grille).
- **Note au comité (1 page) :** contexte, modèle retenu, performance, seuil et impact, 3 risques et limites, prochaines étapes.
- **Model card**, **README final** (5 lignes de résultats en tête, reproduction, captures, mesures DAX).
- Livrables : `docs/powerbi_guide.md` (exports `powerbi_data/` par `export_to_powerbi.py`), `docs/note_comite_credit.md` et `docs/model_card.md` (`build_reports.py`), `notebooks/07_Final_Synthesis.ipynb`.

**Décision (08/10) :**

| # | Décision |
|---|---|
| D28 | Tableau de bord Power BI reporté après la livraison v0.6.0 ; exports CSV et guide déjà prêts. |
| D29 | Publication alignée sur le dépôt `bank-complaint-routing-nlp` : racine réduite à README, requirements et .gitignore ; changelog et dictionnaire de données dans `docs/` ; manifestes sha256 des données et des modèles ; historique publié en un seul commit sur `main`. |

**Checklist :**
- [ ] Reporté — à faire après : chiffres du dashboard = chiffres des notebooks 04 à 06 et de `output/tables/` au centième près (exports `powerbi_data/` prêts ; rapport `.pbix` à construire et contrôler)
- [x] Note sur une page ; README compréhensible en 60 secondes (5 lignes de résultats en tête)
- [ ] Dépôt public épinglé sur GitHub (après commit par Cely)
- [x] Documentation à jour (0.6.0)

---

## 13. Risques

| Risque | Mitigation |
|---|---|
| Volume (plusieurs Go, tables de dizaines de millions de lignes) | Agrégations SQL DuckDB, Parquet |
| Pas de dimension temporelle | PSI, stabilité des WoE, bootstrap ; limite écrite |
| Fuite via variables à IV très élevé | Revue manuelle de toute variable IV > 0,5 |
| Données non africaines (origine exacte non documentée par Home Credit) | Transposition au marché CEMAC argumentée, pas mesurée |
| Téléchargement manuel (fichier manquant ou tronqué) | `verify_raw_data.py` + comptage des lignes en Phase 1 |
| pandas 3.0 (version majeure récente) | Code testé sous pandas 3 ; versions figées dans `requirements.txt` |
| Calendrier serré | Dates prévisionnelles ; Streamlit reporté en bonus |

---

## 14. Formulations CV (chiffres réels uniquement)
- Développé une grille de score crédit (Python, optbinning, WoE/IV) sur [N] dossiers et 7 tables relationnelles : AUC [x,xx], Gini [x,xx], KS [x,xx] sur jeu de test indépendant.
- Construit un pipeline SQL (DuckDB) agrégeant [N] M de lignes d'historique en [N] variables de risque.
- Comparé régression logistique et LightGBM ; justifié chaque refus par SHAP et par les points de la grille.
- Proposé un seuil ramenant le taux de défaut de [x] % à [y] % pour un taux d'approbation de [z] %.
- Conçu un dashboard Power BI de pilotage du portefeuille avec simulateur de seuil.

---

## Annexe A0 — Complément au prompt de la Phase 1 (à coller avant l'annexe A)

```
COMPLÉMENT PHASE 1 — PRIORITAIRE SUR LE PROMPT CI-DESSOUS EN CAS DE DIVERGENCE

ÉTAT ACTUEL DU DÉPÔT
Le dossier courant (credit-risk-scorecard/) est la racine.
Existent déjà et NE DOIVENT PAS être écrasés sans nécessité : CAHIER_DES_CHARGES.md,
README.md, .gitignore, requirements.txt (versions minimales). METADATA.md et CHANGELOG.md
sont à compléter. Un environnement .venv (Python 3.13.15) existe, dépendances installées.
Git n'est pas initialisé. Windows 11, terminal PowerShell dans VS Code.
Ne recrée pas de sous-dossier credit-risk-scorecard/.

DONNÉES DÉJÀ PRÉSENTES (téléchargement manuel, API Kaggle NON utilisée)
data/raw/ contient les 9 CSV attendus, plus des fichiers annexes : archives .zip,
sample_submission.csv et home_credit.png (schéma officiel des tables).
- Ne télécharge rien. Ne supprime rien dans data/raw/.
- Déplace home_credit.png vers reports/figures/home_credit_schema.png (seul
  déplacement autorisé) et cite la source (Kaggle / Home Credit) dans METADATA.md.

AJUSTEMENTS PAR RAPPORT AU PROMPT
- Nom de la base : db/credit_risk.duckdb (et non home_credit.duckdb).
- L'étape 3 est REMPLACÉE par scripts/verify_raw_data.py, qui :
  * vérifie la présence des 9 CSV attendus (noms exacts, casse comprise) et s'arrête
    avec un message clair si l'un manque ;
  * journalise nom et taille en Mo de chaque CSV ;
  * liste les fichiers annexes (.zip, sample_submission.csv) comme "non utilisés",
    sans les supprimer ;
  * ne fait aucun appel réseau.
- Étape 4 : ne charge que les 9 CSV attendus (ignore .zip et sample_submission.csv).
- Rapport qualité : ajouter une ligne "intégrité des fichiers" (comptes de lignes
  cohérents, aucune ligne tronquée signalée par DuckDB).
- Étape 1 (structure) : ne crée que ce qui manque.
- Étape 2 (requirements) : ne réécris pas requirements.txt ; génère requirements-lock.txt
  via pip freeze depuis .venv.
- Utilise exclusivement .venv\Scripts\python.exe. Aucune installation globale.
- pandas est en version 3.0 : écris un code compatible pandas 3 (copie à l'écriture,
  type chaîne par défaut) ; pas d'affectation chaînée.

GIT
- git init à la racine.
- Fichier .gitkeep vide dans data/raw, data/processed, db, dashboards/exports,
  reports/figures et tout dossier sans fichier suivi.
- Vérifie que le .gitignore existant exclut bien data/, db/, .venv/, kaggle.json
  tout en conservant les .gitkeep ; complète-le si besoin sans supprimer de règle.
- Avant commit : git status et git ls-files ; si un .csv, .zip, .duckdb ou kaggle.json
  est suivi, arrête-toi et signale-le.
- Commit en fin de phase uniquement : "Phase 1: ingestion and data quality audit (v0.2.0)".

DOCUMENTATION CONTINUE
- README.md : statut "Phase 1 terminée", instructions d'exécution de la Phase 1,
  chiffres issus de l'exécution uniquement.
- CHANGELOG.md : entrée 0.1.0 (Phase 0, cadrage) et 0.2.0 (Phase 1).
- METADATA.md : dictionnaire + schéma des jointures (étape 8).
- NE MODIFIE PAS CAHIER_DES_CHARGES.md (tenu à jour dans une autre session).

COMPTE RENDU FINAL
En plus des éléments demandés : version de Python, taille des 9 CSV en Mo, liste des
fichiers annexes non utilisés, sortie de git ls-files.

--- PROMPT PHASE 1 ---
```

## Annexe A — Prompt Claude Code, Phase 1

```
CONTEXTE
Je construis un projet de portfolio "Credit Risk Scorecard" pour une candidature
Data Scientist dans une banque (Afriland First Bank, Cameroun). Données : compétition
Kaggle "home-credit-default-risk" (règles déjà acceptées sur Kaggle, kaggle.json
configuré). Ce prompt couvre UNIQUEMENT la Phase 1 : mise en place, ingestion,
audit qualité. Aucune modélisation, aucun feature engineering.

RÈGLES
- N'invente aucun chiffre : tout nombre dans les rapports provient d'une exécution réelle.
- Si une étape échoue, arrête-toi et affiche l'erreur exacte, sans contournement silencieux.
- application_test.csv n'a pas de TARGET : charge-le, mais ne l'utilise jamais pour
  l'analyse de la cible.
- Scripts idempotents : relancer ne duplique rien et ne retélécharge pas si déjà présent.

1. STRUCTURE DU DÉPÔT (racine : credit-risk-scorecard/)
credit-risk-scorecard/
├── data/raw/            (CSV décompressés, gitignoré)
├── data/processed/      (gitignoré)
├── db/                  (credit_risk.duckdb, gitignoré)
├── scripts/
├── sql/
├── notebooks/
├── reports/figures/
├── dashboards/
├── README.md
├── METADATA.md
├── CHANGELOG.md
├── requirements.txt
└── .gitignore           (data/, db/, *.duckdb, .ipynb_checkpoints, kaggle.json, .env)

2. requirements
Voir complément A0 : requirements.txt conservé, requirements-lock.txt généré par
pip freeze. N'écris pas de versions de mémoire.

3. scripts/fetch_data.py
- Vérifie la présence de ~/.kaggle/kaggle.json (ou de la variable KAGGLE_CONFIG_DIR),
  sinon message clair et arrêt.
- Télécharge via l'API Kaggle (compétition home-credit-default-risk) dans data/raw/.
- Si erreur 403 : message explicite "Règles de la compétition non acceptées sur Kaggle".
- Décompresse, puis supprime le zip.
- Journalise pour chaque fichier : nom, taille en Mo.
- Fichiers attendus : application_train, application_test, bureau, bureau_balance,
  previous_application, POS_CASH_balance, credit_card_balance, installments_payments,
  HomeCredit_columns_description. Signale tout fichier manquant ou inattendu.

4. scripts/load_to_duckdb.py
- Crée db/credit_risk.duckdb.
- Une table par CSV (nom en minuscules, sans .csv), via read_csv_auto de DuckDB
  (pas de chargement pandas des gros fichiers).
- HomeCredit_columns_description.csv peut ne pas être en UTF-8 : détecte et gère
  l'encodage (essaie latin-1 / cp1252 si UTF-8 échoue).
- CREATE OR REPLACE pour garantir l'idempotence.
- Affiche un tableau récapitulatif : table, nb lignes, nb colonnes.

5. sql/00_quality_checks.sql (exécuté par un script ou le notebook)
a. Nombre de lignes et de colonnes par table.
b. Unicité de SK_ID_CURR dans application_train et application_test.
c. Unicité de SK_ID_BUREAU dans bureau et de SK_ID_PREV dans previous_application.
d. Intégrité référentielle : % de SK_ID_CURR de bureau et previous_application
   présents dans application_train ∪ application_test ; % de SK_ID_BUREAU de
   bureau_balance présents dans bureau.
e. Distribution de TARGET (effectif et %) dans application_train.
f. Top 20 des colonnes d'application_train par % de valeurs manquantes.
g. Anomalies connues à vérifier et chiffrer :
   - DAYS_EMPLOYED = 365243 (valeur sentinelle) : nombre de lignes et taux de
     défaut de ce groupe comparé au reste.
   - CODE_GENDER = 'XNA' : nombre de lignes.
   - Valeurs DAYS_* positives là où elles devraient être négatives.

6. notebooks/00_Data_Audit.ipynb
- Cellule 1 (Markdown) : "# 00_Data_Audit — Home Credit Data Quality Audit"
- Cellule 2 : setup avec vérification du répertoire de travail (doit être la racine
  credit-risk-scorecard/, sinon erreur claire) et connexion DuckDB en lecture seule.
- Sections : volumétrie, clés et intégrité, cible, valeurs manquantes, anomalies,
  schéma relationnel (description texte des 7 tables et de leurs clés de jointure).
- Figures sauvegardées dans reports/figures/ : distribution de TARGET, top 20 des
  manquants.
- Cellule finale : synthèse des constats et implications pour la Phase 2.

7. reports/data_quality_report.md
Rapport d'une à deux pages rédigé à partir des résultats réels : tableau de
volumétrie, déséquilibre de la cible, problèmes détectés, décision proposée pour
chacun (à valider, pas appliquée en Phase 1).

8. METADATA.md
Dictionnaire généré depuis la table homecredit_columns_description : table,
colonne, description. Plus un schéma des jointures en texte :
application → bureau → bureau_balance ; application → previous_application →
POS_CASH_balance / credit_card_balance / installments_payments.

9. README.md et CHANGELOG.md
Voir complément A0 (documentation continue).

FIN DE PHASE
Affiche la liste des fichiers créés et les résultats clés (volumétrie, taux de
défaut, anomalies). Ne commence pas la Phase 2.
```

Modifications de l'annexe A par rapport à la version d'origine, pour cohérence avec le dépôt : nom de la base (`credit_risk.duckdb`), étapes 2 et 9 renvoyées au complément A0. L'étape 3 (téléchargement) est conservée pour mémoire mais **remplacée** par `verify_raw_data.py` selon A0, les données ayant été téléchargées manuellement. Le reste est inchangé.

## Annexe B — Prompt Claude Code, Phase 2 (feature engineering SQL)

```
CONTEXTE
Projet "Credit Risk Scorecard" (dépôt courant, racine
credit-risk-scorecard/). La Phase 1 est terminée : les 9 CSV sont chargés dans
db/credit_risk.duckdb (tables application_train, application_test, bureau,
bureau_balance, previous_application, pos_cash_balance, installments_payments,
credit_card_balance, homecredit_columns_description, meta_load_log).
Ce prompt couvre UNIQUEMENT la Phase 2 : construire la table de modélisation
1 ligne = 1 SK_ID_CURR par agrégations SQL. Aucun split, aucun binning, aucun modèle.

LIS D'ABORD, EN ENTIER : CAHIER_DES_CHARGES.md (§7.4, §8, §12 Phase 2 et le tableau
des décisions D1 à D13) et reports/data_quality_report.md (§5). Les décisions D1 à
D13 sont VALIDÉES et s'appliquent telles quelles.

RÈGLES
- N'invente aucun chiffre : tout nombre écrit provient d'une exécution réelle.
- En cas d'échec, arrête-toi et affiche l'erreur exacte ; pas de contournement silencieux.
- TARGET n'est utilisée dans AUCUNE agrégation ni analyse (D9). Elle est seulement
  recopiée telle quelle dans la table modèle du train.
- Scripts idempotents (CREATE OR REPLACE) ; aucune suppression dans data/raw/.
- Python exclusivement via .venv\Scripts\python.exe ; code compatible pandas 3
  (pas d'affectation chaînée). Les agrégations se font en SQL DuckDB, pas en pandas.
- N'exécute AUCUNE commande git d'écriture (add, commit, amend, reset, checkout).
  git status et git diff sont autorisés.
- Ne modifie pas CAHIER_DES_CHARGES.md.
- Demande une autorisation avant chaque création ou modification de fichier.

CONVENTIONS DE NOMMAGE
- Préfixe par source : APP_ (application), BUR_ (bureau), BB_ (bureau_balance,
  agrégé via bureau), PREV_ (previous_application), INS_ (installments_payments),
  POS_ (pos_cash_balance), CC_ (credit_card_balance).
- Suffixe _12M pour la fenêtre des 12 derniers mois (D12) ; sans suffixe = historique
  complet.
- Colonnes brutes d'application conservées sous leur nom d'origine ; seules les
  variables CRÉÉES portent le préfixe APP_.

1. CONTRÔLE PRÉALABLE DES SENTINELLES
   Avant d'écrire les agrégations, compte la valeur 365243 dans toutes les colonnes
   DAYS_* de toutes les tables et affiche le résultat. Traite comme sentinelle (→ NULL)
   UNIQUEMENT