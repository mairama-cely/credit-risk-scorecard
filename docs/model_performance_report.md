# Rapport de performance des modèles — Phase 4 (4b et 4c)

> Généré par `scripts/build_cutoff_strategy.py` (fonction `write_report`) à partir de `output/tables/evaluation_metrics.json`, `final_comparison.csv`, `calibration_test.csv`, `psi_table.csv`, `fairness_table.csv`, `refusal_reasons.csv`, `cutoff_scenarios.csv`, `cutoff_strategy.json` et `challenger_metrics.json`. Aucun chiffre n'est saisi à la main.

> **Test scellé (D15)** : lu uniquement par `scripts/evaluate_models.py`, chaque lecture journalisée dans `models/test_access_log.csv` (dernière : 2026-10-08T09:48:02Z, 46 127 demandes, empreinte SHA-256 conforme à `split_meta`). Aucun modèle, seuil ni calibrage n'a été ajusté sur le test ; le pipeline étant déterministe, chaque exécution redonne les mêmes résultats.

## 1. Comparaison finale (train / validation / test)

| Modèle | Échantillon | Effectif | AUC | Gini | KS | Brier |
|---|---|---:|---:|---:|---:|---:|
| Grille de score | train | 215 257 | 0,7544 | 0,5087 | 0,3810 | 0,0682 |
| Grille de score | valid | 46 127 | 0,7529 | 0,5059 | 0,3808 | 0,0683 |
| Grille de score | test | 46 127 | 0,7518 | 0,5035 | 0,3762 | 0,0684 |
| LightGBM | train | 215 257 | 0,8808 | 0,7615 | 0,5948 | 0,0568 |
| LightGBM | valid | 46 127 | 0,7851 | 0,5702 | 0,4322 | 0,0659 |
| LightGBM | test | 46 127 | 0,7883 | 0,5766 | 0,4384 | 0,0659 |
| LightGBM sans EXT_SOURCE | train | 215 257 | 0,8490 | 0,6981 | 0,5346 | 0,0609 |
| LightGBM sans EXT_SOURCE | valid | 46 127 | 0,7617 | 0,5234 | 0,3865 | 0,0677 |
| LightGBM sans EXT_SOURCE | test | 46 127 | 0,7598 | 0,5195 | 0,3887 | 0,0679 |

Intervalles de confiance à 95 % sur le test (bootstrap, 1000 rééchantillonnages, graine 42, percentiles) :

| Indicateur | Estimation | IC 95 % |
|---|---:|---:|
| AUC grille | 0,7518 | [0,7437 ; 0,7598] |
| Gini grille | 0,5035 | [0,4874 ; 0,5196] |
| AUC LightGBM | 0,7883 | [0,7809 ; 0,7960] |
| Gini LightGBM | 0,5766 | [0,5618 ; 0,5921] |
| Écart d'AUC LightGBM − grille (apparié) | 0,0365 | [0,0319 ; 0,0408] |

L'écart d'AUC est significatif au seuil de 5 % (l'intervalle exclut 0). Écart de généralisation valid → test : grille -0,0012, LightGBM 0,0032 (AUC).

## 2. Calibration (test)

| Modèle | PD moyenne | Taux observé | Brier | Écart absolu moyen par décile | Écart max | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Grille de score | 8,05 % | 8,07 % | 0,0684 | 0,20 pt | 0,40 pt | calibré |
| LightGBM | 7,96 % | 8,07 % | 0,0659 | 0,25 pt | 0,93 pt | calibré |

Critère : un modèle est jugé mal calibré si l'écart absolu moyen entre PD prédite et taux observé par décile dépasse 1,0 pt ou si l'écart max dépasse 3,0 pt. À titre de contrôle, une régression isotone ajustée sur la validation (jamais sur le test) donne un Brier de test de 0,0685 (Grille de score) ; 0,0660 (LightGBM).

Détail par décile de PD : `output/tables/calibration_test.csv`.

## 3. Stabilité (PSI train → test)

- **Score de la grille** (10 tranches = déciles du train) : PSI 0,0001 → stable (train → validation : 0,0004).
- **Stabilité caractéristique** (classes WoE des 17 variables retenues) : PSI max 0,0006 (`ORGANIZATION_TYPE`) ; 0 variable(s) > 0,10, 0 > 0,25.

Seuils usuels : < 0,10 stable ; 0,10 – 0,25 à surveiller ; > 0,25 instable. Train et test sont issus d'un même tirage aléatoire (pas de dimension temporelle) : le PSI contrôle ici la cohérence du découpage, pas la dérive dans le temps.

## 4. Équité — audit par `CODE_GENDER` (variable exclue du modèle)

Seuil appliqué : scénario recommandé (`prudent`, score ≥ 563). Groupe `XNA` ignoré (0 demande(s) au test, 4 sur l'ensemble des échantillons).

| Groupe | Effectif | Taux de défaut | Score moyen | AUC grille | AUC LightGBM | Acceptation | Acceptation des bons | Défaut des acceptés |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| F | 30 429 | 6,96 % | 570,9 | 0,7500 | 0,7847 | 64,2 % | 66,8 % | 3,12 % |
| M | 15 698 | 10,23 % | 563,4 | 0,7423 | 0,7844 | 52,7 % | 56,2 % | 4,20 % |

Ratio d'acceptation M / F : 0,821 (règle des 4/5 : ≥ 0,80 → respectée) ; parmi les bons clients seulement (égalité des chances) : 0,841. Écart d'AUC de la grille F − M : 0,0078. Le genre n'entre pas dans le modèle, mais des variables corrélées (profession, secteur d'emploi) peuvent le refléter. L'écart d'acceptation suit en partie l'écart de taux de défaut entre groupes, mais il persiste parmi les bons clients : les hommes solvables sont plus souvent refusés. Point de vigilance, à soumettre à une revue de conformité.

## 5. Ablation des scores externes (`EXT_SOURCE_*`)

- LightGBM sans les 5 variables `EXT_SOURCE` : AUC validation 0,7617 (Δ -0,0234), AUC test 0,7598 (Δ vs LightGBM complet -0,0285).
- La grille de score n'est **pas** exempte de ces variables : 3 de ses 17 variables en dérivent (`APP_EXT_SOURCE_MEAN`, `EXT_SOURCE_3`, `EXT_SOURCE_1`). Aucune ablation de la grille n'a été réalisée (il faudrait refaire la sélection et la régression).

## 6. Motifs de refus (grille)

Pour chaque demande, les trois variables où l'écart entre les points obtenus et le maximum de points de la variable est le plus grand. Distribution du premier motif parmi les demandes refusées au test (scénario `prudent`) :

| Variable | 1er motif (refusés) | Part | Dans le top 3 (refusés) |
|---|---:|---:|---:|
| `APP_EXT_SOURCE_MEAN` | 18 233 | 99,5 % | 99,8 % |
| `CC_MAX_UTILIZATION_12M` | 57 | 0,3 % | 12,6 % |
| `APP_CREDIT_GOODS_RATIO` | 22 | 0,1 % | 22,7 % |
| `INS_MAX_DAYS_LATE_12M` | 8 | 0,0 % | 8,7 % |
| `APP_EMPLOYED_YEARS` | 4 | 0,0 % | 44,3 % |
| `REGION_RATING_CLIENT_W_CITY` | 1 | 0,0 % | 20,3 % |
| `INS_SHARE_LATE` | 1 | 0,0 % | 9,3 % |
| `EXT_SOURCE_3` | 0 | 0,0 % | 33,5 % |

Le premier motif est presque toujours `APP_EXT_SOURCE_MEAN` : son maximum de points (65) est le plus élevé de la grille, donc son manque de points domine mécaniquement. Les 2e et 3e motifs sont plus informatifs ; un score externe n'est de plus pas un motif explicable au client tel quel.

## 7. Stratégie de seuils (choisie sur la validation, évaluée sur le test)

Zones : accepter si score ≥ seuil + 10 ; revoir entre seuil − 10 et seuil + 10 ; refuser en dessous. Perte attendue = PD × LGD × EAD (EAD = `AMT_CREDIT`, LGD 45 %).

| Scénario | Seuil | Acceptation (test) | Défaut des acceptés | Bons refusés | Perte attendue acceptée | Perte évitée | Part évitée | Zone de revue | Défaut tranche marginale | Marge d'équilibre |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Prudent **(recommandé)** | 563 | 60,3 % | 3,44 % | 15 559 (36,7 %) | 272,4 M | 632,6 M | 69,9 % | 25,4 % | — | — |
| Équilibré | 550 | 75,3 % | 4,49 % | 9 249 (21,8 %) | 422,8 M | 482,1 M | 53,3 % | 20,2 % | 8,72 % | 4,2 % |
| Croissance | 539 | 85,0 % | 5,43 % | 5 342 (12,6 %) | 554,7 M | 350,2 M | 38,7 % | 15,4 % | 12,73 % | 6,4 % |

Sans seuil (tout accepter) : taux de défaut 8,07 %, perte attendue 904,9 M. Montants en unités monétaires du jeu de données. Tranche marginale : clients acceptés en plus par rapport au scénario plus prudent ; marge d'équilibre = marge nette (en % du montant prêté) qu'un bon crédit doit rapporter pour que l'acceptation de cette tranche compense sa perte attendue (LGD · Σ PD·EAD / Σ (1 − PD)·EAD).

Sensibilité à la LGD (test, scénario recommandé) : LGD 35 % → perte attendue acceptée 211,8 M, évitée 492,0 M ; LGD 45 % → perte attendue acceptée 272,4 M, évitée 632,6 M ; LGD 55 % → perte attendue acceptée 332,9 M, évitée 773,1 M. La part évitée ne dépend pas de la LGD (constante).

**Recommandation : scénario Prudent.** Règle fixée avant lecture du test : maximiser, sur la validation, « part de la perte attendue évitée − part des bons clients refusés » (Prudent 0,3321 ; Équilibré 0,3153 ; Croissance 0,2614). Sur le test : acceptation 60,3 %, défaut des acceptés 3,44 % contre 8,07 % sans seuil, 69,9 % de la perte attendue évitée pour 36,7 % de bons clients refusés. Point de bascule : si la marge nette d'un bon crédit dépasse 4,2 % du montant prêté (tranche Équilibré au test), élargir au scénario Équilibré devient rentable ; cette marge n'est pas connue dans les données.

## 8. Limites

- **Sur-apprentissage de LightGBM** : AUC train 0,8808 contre validation 0,7851 et test 0,7883. La grille est stable (train 0,7544, test 0,7518).
- **Validation réutilisée** : early stopping et choix de variante de LightGBM, calibrage isotone de contrôle et choix des seuils ont tous été faits sur la validation ; seules les mesures sur le test sont sans biais.
- **LGD supposée** (45 %, sensibilité 35 %, 45 %, 55 %) et EAD = montant du crédit à l'octroi (pas d'amortissement) : la perte attendue est un ordre de grandeur.
- **Règle de recommandation sans données de marge** : elle pèse à égalité perte évitée et bons clients perdus.
- **Biais de sélection** : Home Credit n'observe le défaut que des dossiers acceptés par le passé ; aucune inférence des refusés n'a été faite.
- **Motifs de refus** dominés par le score externe `APP_EXT_SOURCE_MEAN` (amplitude de points la plus grande), peu exploitable comme motif communiqué au client.
- **Zone de revue** de ± 10 points : 25,4 % des demandes au test pour le scénario recommandé, charge de traitement manuel à valider.
- **PSI** calculé sur un découpage aléatoire : il ne remplace pas un suivi de dérive dans le temps en production.
