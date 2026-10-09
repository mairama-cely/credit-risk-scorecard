# Rapport de la grille de score — Phase 3 (3c à 3e)

> Version 0.4.0. Généré par `scripts/train_scorecard.py` (fonction `write_report`) à partir de `output/tables/scorecard_metrics.json`, `iv_table.csv` et `scorecard_table.csv`. Aucun chiffre n'est saisi à la main. Échantillons : train (ajustement) et validation (contrôle) ; **le test n'a pas été lu** (D15).

## 1. Méthode

- **Candidates (D16)** : 200 variables au statut « candidate » du catalogue.
- **Binning (D17)** : `BinningProcess` d'optbinning 1.0.0, ajusté sur le train (215 257 demandes) ; tendance `auto_asc_desc` pour les numériques, au moins 5 % des individus par classe, manquants dans une classe à part (WoE empirique), catégorielles regroupées selon le taux de défaut.
- **Convention WoE** : WoE = ln(%non-défauts / %défauts) ; un WoE élevé correspond à un risque faible, donc tous les coefficients du logit (cible = défaut) doivent être **négatifs** (D20).
- **Filtres (D18, D19)** : IV < 0,02 exclue ; IV > 0,5 conservée mais signalée ; corrélation des WoE > 0,7 → IV le plus élevé conservé ; VIF > 5 retiré itérativement ; au plus 20 variables.
- **Régression (D20)** : logit non pondéré (statsmodels 0.15.0) ; retrait itératif des p-valeurs > 0,05 puis des signes incohérents.
- **Mise à l'échelle (D21)** : 600 points pour des odds 50:1 (bons:mauvais), PDO = 20 ; factor = 28,8539, offset = 487,1229 ; l'intercept est réparti à parts égales entre les variables ; points arrondis à l'entier ; score élevé = risque faible.

## 2. Entonnoir de sélection

| Étape | Variables restantes |
|---|---:|
| Candidates (D16) | 200 |
| IV ≥ 0,02 (D18) | 82 |
| Corrélation des WoE ≤ 0,7 (D19) | 41 |
| VIF ≤ 5 (D19) | 41 |
| Plafond 20 variables (D19) | 20 |
| p ≤ 0,05 et signe cohérent (D20) | 17 |

Motifs d'exclusion : `iv_low` 118 ; `corr` 41 ; `cap20` 21 ; `pvalue` 2 ; `sign` 1.

## 3. Variables retenues

| Variable | IV | Classes | Monotone | Coefficient | p-valeur | VIF | Points min | Points max |
|---|---:|---:|:---:|---:|---:|---:|---:|---:|
| `APP_EXT_SOURCE_MEAN` | 0,6287 | 15 | oui | -0,6866 | < 1e-300 | 2,05 | 5 | 65 |
| `EXT_SOURCE_3` | 0,3335 | 11 | oui | -0,2165 | 6,69e-31 | 1,82 | 26 | 39 |
| `EXT_SOURCE_1` | 0,1501 | 6 | oui | -0,1575 | 2,32e-10 | 1,28 | 30 | 38 |
| `APP_EMPLOYED_YEARS` | 0,1163 | 9 | oui | -0,3552 | 4,35e-36 | 1,34 | 29 | 40 |
| `BUR_YEARS_SINCE_LAST_CREDIT` | 0,0888 | 8 | oui | -0,2870 | 1,03e-21 | 1,20 | 28 | 36 |
| `INS_MAX_DAYS_LATE_12M` | 0,0802 | 4 | oui | -0,4036 | 3,63e-37 | 1,31 | 23 | 35 |
| `CC_MAX_UTILIZATION_12M` | 0,0790 | 3 | oui | -0,3897 | 1,24e-21 | 1,93 | 24 | 37 |
| `OCCUPATION_TYPE` | 0,0780 | 5 | oui | -0,3713 | 3,81e-30 | 1,25 | 28 | 37 |
| `APP_CREDIT_GOODS_RATIO` | 0,0733 | 6 | oui | -0,6243 | 3,34e-98 | 1,02 | 24 | 37 |
| `PREV_MEAN_CREDIT_APPLICATION_RATIO` | 0,0726 | 12 | oui | -0,4350 | 7,95e-44 | 1,09 | 26 | 38 |
| `ORGANIZATION_TYPE` | 0,0722 | 8 | oui | -0,3730 | 1,88e-23 | 1,44 | 28 | 37 |
| `PREV_SHARE_REFUSED` | 0,0711 | 5 | oui | -0,3254 | 3,75e-16 | 1,76 | 27 | 36 |
| `INS_SHARE_LATE` | 0,0640 | 8 | oui | -0,4435 | 2,78e-33 | 1,29 | 26 | 37 |
| `PREV_SHARE_APPROVED` | 0,0638 | 6 | oui | -0,1870 | 1,54e-05 | 1,79 | 30 | 34 |
| `BUR_DEBT_CREDIT_RATIO` | 0,0594 | 8 | oui | -0,4113 | 2,64e-33 | 1,06 | 27 | 39 |
| `CC_MEAN_UTILIZATION` | 0,0574 | 3 | oui | -0,1720 | 4,42e-04 | 1,89 | 30 | 35 |
| `REGION_RATING_CLIENT_W_CITY` | 0,0520 | 3 | oui | -0,4425 | 3,83e-31 | 1,09 | 28 | 40 |

Intercept : -2,4352 (p < 1e-300). Score théorique : de 439 à 660 points.

## 4. Performance

| Échantillon | Effectif | AUC | Gini | KS |
|---|---:|---:|---:|---:|
| Train | 215 257 | 0,7544 | 0,5087 | 0,3810 |
| Validation | 46 127 | 0,7529 | 0,5059 | 0,3808 |

Écart d'AUC train − validation : **0,0014** (seuil 0,02) → **conforme**. Métriques calculées sur le score entier de la grille.

Cohérence score ↔ PD : à 600 points, PD = 0,01961 (= 1 / 51) ; +20 points doublent les odds (rapport mesuré 2,000). Écart entre la PD implicite du score arrondi et la PD du logit (validation) : moyen 0,00202, maximal 0,03842 (cumul des arrondis de 17 variables). AUC de validation calculée sur la PD du logit : 0,7529.

## 5. Signalements

- **IV > 0,5 (D18, revue manuelle)** : `APP_EXT_SOURCE_MEAN` (IV 0,6287, retenue).
- **WoE non monotone** : 0 variable(s) sur 200.
- **Sens a priori du catalogue vs sens observé (variables retenues numériques)** : 14 concordant(s) sur 15 comparables ; discordant(s) : `PREV_MEAN_CREDIT_APPLICATION_RATIO`.

## 6. Limites

- Régression non pondérée : la PD reflète le taux de défaut du train ; la calibration sera contrôlée en Phase 4.
- La sélection (corrélation, VIF, plafond) est gloutonne et ordonnée par IV : une autre combinaison de variables pourrait donner une performance voisine.
- Arrondi des points à l'entier : écart entre la PD implicite du score et celle du logit (§4).
- Les variables `EXT_SOURCE_*` sont des scores externes opaques ; leur poids sera mesuré par ablation (D8, Phase 4).
- Performance mesurée sur la validation seulement ; le test reste scellé jusqu'à la Phase 4.
