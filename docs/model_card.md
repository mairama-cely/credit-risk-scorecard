# Fiche modèle — grille de score d'octroi (credit-risk-scorecard)

> Générée par `scripts/build_reports.py` (fonction `write_card`) le 2026-10-08 à partir de `output/tables/` et des métadonnées des modèles. Aucun chiffre saisi à la main.

## 1. Détails du modèle

- **Modèle de production proposé** : grille de score (scorecard) version 0.4.0, régression logistique non pondérée sur classes WoE (optbinning + statsmodels), 17 variables.
- **Mise à l'échelle** : 600 points pour des odds 50:1 (bons:mauvais), PDO = 20 ; points entiers par classe ; score élevé = risque faible ; plage théorique 439 – 660 points.
- **Challenger** : LightGBM 4.7.0 (variante unweighted, 912 arbres, 200 variables) ; non proposé en production.
- **Règle de décision** : scénario Prudent, seuil 563 ; accepter si score ≥ 573, revue manuelle de 553 à 572, refuser en dessous.
- **Sorties** : score entier, PD du logit, décision (accepter / revoir / refuser), trois motifs de refus (variables au plus grand manque de points).

## 2. Usage prévu

- **Prévu** : aide à la décision d'octroi de crédits à la consommation (prêts cash et renouvelables) pour des particuliers ; classement des demandes par risque, fixation d'un seuil, motivation des refus.
- **Utilisateurs** : analystes crédit, comité de crédit, équipe risque/modèles.
- **Hors champ** : décision entièrement automatisée sans revue humaine de la zone grise ; crédit aux entreprises ou microfinance de groupe ; tarification au risque ; utilisation directe sur un portefeuille camerounais **sans recalibrage** ; toute décision fondée sur le genre.

## 3. Données

- **Source** : Home Credit Default Risk (Kaggle), table `application_train` et historiques (bureau, demandes antérieures, échéances, POS, carte de crédit) agrégés par demande (307 511 demandes).
- **Cible** : `TARGET` = 1 si difficultés de paiement ; taux de défaut 8,07 %.
- **Découpage stratifié** (graine 42) : train 215 257, validation 46 127, test 46 127 ; test scellé, lu uniquement par `scripts/evaluate_models.py` (aucune sélection ni réglage dessus), chaque lecture journalisée dans `models/test_access_log.csv` ; dernière lecture le 2026-10-08T09:48:02Z (empreinte SHA-256 conforme).
- **Biais de sélection** : seuls les dossiers accordés par le passé ont une cible observée ; pas d'inférence des refusés.

## 4. Variables de la grille

Sélection : 200 candidates → 82 avec IV ≥ 0,02 → 41 après corrélation → 20 après plafond → 17 après p-valeur et signe. Variable exclue par construction : `CODE_GENDER` (utilisée seulement pour l'audit d'équité).

| Variable | Description | Source | IV | Coefficient | Points (min – max) |
|---|---|---|---:|---:|---:|
| `APP_EXT_SOURCE_MEAN` | Moyenne des scores externes EXT_SOURCE_1/2/3 renseignés | demande | 0,6287 | -0,6866 | 5 – 65 |
| `EXT_SOURCE_3` | Score externe n° 3 (opaque) | demande | 0,3335 | -0,2165 | 26 – 39 |
| `EXT_SOURCE_1` | Score externe n° 1 (opaque) | demande | 0,1501 | -0,1575 | 30 – 38 |
| `APP_EMPLOYED_YEARS` | Ancienneté dans l'emploi actuel (années) | demande | 0,1163 | -0,3552 | 29 – 40 |
| `BUR_YEARS_SINCE_LAST_CREDIT` | Années depuis le dernier crédit déclaré au bureau | bureau de crédit | 0,0888 | -0,2870 | 28 – 36 |
| `INS_MAX_DAYS_LATE_12M` | Retard maximal de paiement d'échéance sur 12 mois (jours) | échéances | 0,0802 | -0,4036 | 23 – 35 |
| `CC_MAX_UTILIZATION_12M` | Utilisation maximale de la carte de crédit sur 12 mois (solde / plafond) | carte de crédit | 0,0790 | -0,3897 | 24 – 37 |
| `OCCUPATION_TYPE` | Profession déclarée | demande | 0,0780 | -0,3713 | 28 – 37 |
| `APP_CREDIT_GOODS_RATIO` | Montant du crédit / prix du bien financé | demande | 0,0733 | -0,6243 | 24 – 37 |
| `PREV_MEAN_CREDIT_APPLICATION_RATIO` | Demandes antérieures : montant accordé / montant demandé (moyenne) | demandes antérieures | 0,0726 | -0,4350 | 26 – 38 |
| `ORGANIZATION_TYPE` | Secteur de l'employeur | demande | 0,0722 | -0,3730 | 28 – 37 |
| `PREV_SHARE_REFUSED` | Part des demandes antérieures refusées | demandes antérieures | 0,0711 | -0,3254 | 27 – 36 |
| `INS_SHARE_LATE` | Part des échéances payées en retard | échéances | 0,0640 | -0,4435 | 26 – 37 |
| `PREV_SHARE_APPROVED` | Part des demandes antérieures approuvées | demandes antérieures | 0,0638 | -0,1870 | 30 – 34 |
| `BUR_DEBT_CREDIT_RATIO` | Bureau : encours / montant des crédits actifs | bureau de crédit | 0,0594 | -0,4113 | 27 – 39 |
| `CC_MEAN_UTILIZATION` | Utilisation moyenne de la carte de crédit (solde / plafond) | carte de crédit | 0,0574 | -0,1720 | 30 – 35 |
| `REGION_RATING_CLIENT_W_CITY` | Notation de la région de résidence (ville incluse), 1 à 3 | demande | 0,0520 | -0,4425 | 28 – 40 |

## 5. Performance

| Modèle | Échantillon | Effectif | AUC | Gini | KS | Brier |
|---|---|---:|---:|---:|---:|---:|
| Grille de score | train | 215 257 | 0,7544 | 0,5087 | 0,3810 | 0,0682 |
| Grille de score | valid | 46 127 | 0,7529 | 0,5059 | 0,3808 | 0,0683 |
| Grille de score | test | 46 127 | 0,7518 | 0,5035 | 0,3762 | 0,0684 |
| LightGBM (challenger) | train | 215 257 | 0,8808 | 0,7615 | 0,5948 | 0,0568 |
| LightGBM (challenger) | valid | 46 127 | 0,7851 | 0,5702 | 0,4322 | 0,0659 |
| LightGBM (challenger) | test | 46 127 | 0,7883 | 0,5766 | 0,4384 | 0,0659 |
| LightGBM sans EXT_SOURCE | train | 215 257 | 0,8490 | 0,6981 | 0,5346 | 0,0609 |
| LightGBM sans EXT_SOURCE | valid | 46 127 | 0,7617 | 0,5234 | 0,3865 | 0,0677 |
| LightGBM sans EXT_SOURCE | test | 46 127 | 0,7598 | 0,5195 | 0,3887 | 0,0679 |

IC 95 % sur le test (bootstrap apparié, 1000 rééchantillonnages) : AUC grille [0,7437 ; 0,7598], AUC LightGBM [0,7809 ; 0,7960], écart LightGBM − grille 0,0365 [0,0319 ; 0,0408].

**Calibration (test)** : PD moyenne 8,05 % pour 8,07 % observés ; écart moyen par décile 0,20 pt, max 0,40 pt (critère : ≤ 1 pt et ≤ 3 pt) → calibrée.

**Effet du seuil recommandé (test, LGD 45 %)** : acceptation 60,3 %, défaut des acceptés 3,44 % (contre 8,07 % sans seuil), perte attendue évitée 69,9 %, bons clients refusés 36,7 %, zone de revue 25,4 %.

**Explicabilité du challenger** (SHAP, 5000 demandes) : `APP_EXT_SOURCE_MEAN` (11,4 %), `PREV_MEAN_CNT_PAYMENT` (3,2 %), `APP_CREDIT_TERM_MONTHS` (2,9 %), `ORGANIZATION_TYPE` (2,9 %), `APP_CREDIT_GOODS_RATIO` (2,8 %).

## 6. Équité (test, scénario recommandé)

| Genre | Effectif | Taux de défaut | AUC grille | Acceptation | Acceptation des bons | Défaut des acceptés |
|---|---:|---:|---:|---:|---:|---:|
| F | 30 429 | 6,96 % | 0,7500 | 64,2 % | 66,8 % | 3,12 % |
| M | 15 698 | 10,23 % | 0,7423 | 52,7 % | 56,2 % | 4,20 % |

Ratio d'acceptation H/F 0,821 (règle des 4/5 : ≥ 0,80) ; parmi les bons clients 0,841. Le genre n'entre pas dans le modèle, mais des variables corrélées (profession, secteur d'emploi) peuvent le refléter : revue de conformité requise.

## 7. Limites

- Dépendance aux scores externes opaques : 3 variables sur 17 (`APP_EXT_SOURCE_MEAN`, `EXT_SOURCE_3`, `EXT_SOURCE_1`) ; premier motif de 99,5 % des refus ; ablation LightGBM : -0,0285 d'AUC au test.
- LGD supposée (45 %, sensibilité 35 %, 45 %, 55 %) et EAD = montant à l'octroi : la perte attendue est un ordre de grandeur.
- Règle de choix du seuil sans données de marge ; zone de revue de ± 10 points à dimensionner.
- Données Home Credit (autre pays, autre période, autres produits) : PD et seuils non transposables tels quels à un portefeuille camerounais ; recalibrage obligatoire.
- Découpage aléatoire sans dimension temporelle : le PSI mesuré contrôle le découpage, pas la dérive.
- LightGBM sur-appris (AUC train 0,8808 contre test 0,7883).

## 8. Suivi en production

- **PSI mensuel** du score et des 17 variables (référence : score 0,0001, variable max 0,0006 `ORGANIZATION_TYPE`) ; < 0,10 stable, 0,10 – 0,25 à surveiller, > 0,25 instable (action). Au test : 0 variable(s) au-delà de 0,10.
- **Défaut des acceptés** par génération (référence 3,44 %) et **calibration** par décile (alerte : écart moyen > 1 pt ou max > 3 pt).
- **Discrimination** sur les générations arrivées à maturité : alerte si Gini < 0,487 (borne basse de l'IC du test).
- **Équité** : ratio d'acceptation H/F (alerte < 0,80). **Charge** : part de la zone de revue (référence 25,4 %).
- **Revue annuelle** : recalibrage, comparaison au challenger, mise à jour des seuils.

## 9. Versions

Environnement de génération de cette fiche :

| Bibliothèque | Version |
|---|---|
| python | 3.13.15 |
| pandas | 3.0.6 |
| numpy | 2.5.3 |
| pyarrow | 25.0.1 |
| duckdb | 1.5.5 |
| optbinning | 1.0.0 |
| scikit-learn | 1.9.1 |
| statsmodels | 0.15.0 |
| lightgbm | 4.7.0 |
| shap | 0.52.0 |
| matplotlib | 3.11.2 |

Versions enregistrées à l'entraînement : optbinning 1.0.0 ; statsmodels 0.15.0 ; sklearn 1.9.1 ; pandas 3.0.6 ; lightgbm 4.7.0.
