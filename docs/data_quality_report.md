# Rapport qualité des données — Phase 1

> Version 0.2.0 — 2026-09-29 (chemins mis à jour en 0.3.1). Source des chiffres : `scripts/load_to_database.py` (table `meta_load_log`) et `database/00_quality_checks.sql`, exécutés via `notebooks/00_Data_Audit.ipynb`.
> Aucun chiffre de ce rapport n'est estimé : tous proviennent de ces exécutions. Les décisions proposées ne sont **pas appliquées** en Phase 1 ; elles seront validées puis mises en œuvre en Phase 2.

## 1. Intégrité des fichiers et volumétrie

Les 9 CSV attendus sont présents dans `data/raw/` (téléchargement manuel). Chaque fichier a été chargé dans DuckDB en mode strict, où une ligne mal formée provoque une erreur. Pour chaque table, le nombre de lignes physiques du CSV (hors en-tête) est **identique** au nombre de lignes chargées. Tous les fichiers se terminent par un saut de ligne. **Aucun fichier n'est tronqué.**

| Table DuckDB | Lignes | Colonnes | CSV (Mo) | Lignes CSV = lignes chargées |
|---|---:|---:|---:|:---:|
| `application_train` | 307 511 | 122 | 158,4 | ✅ |
| `application_test` | 48 744 | 121 | 25,3 | ✅ |
| `bureau` | 1 716 428 | 17 | 162,1 | ✅ |
| `bureau_balance` | 27 299 925 | 3 | 358,2 | ✅ |
| `previous_application` | 1 670 214 | 37 | 386,2 | ✅ |
| `pos_cash_balance` | 10 001 358 | 8 | 374,5 | ✅ |
| `installments_payments` | 13 605 401 | 8 | 689,6 | ✅ |
| `credit_card_balance` | 3 840 312 | 23 | 404,9 | ✅ |
| `homecredit_columns_description` | 219 | 4 | 0,0 | ✅ |
| **Total** | **58 490 112** | | **2 559,2** | |

Le dictionnaire `HomeCredit_columns_description.csv` n'est pas encodé en UTF-8 : il est décodé en **cp1252** (l'octet 0x85 y représente « … »). `sample_submission.csv` est présent mais n'est pas utilisé. Les archives .zip avaient déjà été supprimées de `data/raw/` avant la Phase 1.

## 2. Clés et intégrité référentielle

| Contrôle | Résultat |
|---|---|
| `SK_ID_CURR` dans `application_train` | 307 511 valeurs distinctes pour 307 511 lignes : **unique**, aucun NULL |
| `SK_ID_CURR` dans `application_test` | 48 744 valeurs distinctes pour 48 744 lignes : **unique**, aucun NULL |
| Identifiants communs à train et test | 0 |
| `SK_ID_BUREAU` dans `bureau` / `SK_ID_PREV` dans `previous_application` | uniques, aucun NULL |
| `bureau.SK_ID_CURR` présents dans application (train ∪ test) | 305 811 / 305 811 (100,00 %) |
| `previous_application.SK_ID_CURR` présents dans application | 338 857 / 338 857 (100,00 %) |
| `bureau_balance.SK_ID_BUREAU` présents dans `bureau` | 774 354 / 817 395 (**94,73 %**) |
| `pos_cash_balance.SK_ID_PREV` présents dans `previous_application` | 898 903 / 936 325 (96,00 %) |
| `installments_payments.SK_ID_PREV` présents dans `previous_application` | 958 905 / 997 752 (96,11 %) |
| `credit_card_balance.SK_ID_PREV` présents dans `previous_application` | 92 935 / 104 307 (**89,10 %**) |

Couverture des 307 511 demandes d'`application_train` : `installments_payments` 94,84 %, `previous_application` 94,65 %, `pos_cash_balance` 94,12 %, `bureau` 85,69 %, `credit_card_balance` 28,26 %.

## 3. Cible

| `TARGET` | Effectif | % |
|---|---:|---:|
| 0 — sans incident | 282 686 | 91,93 |
| 1 — difficultés de paiement | 24 825 | 8,07 |

Les données sont déséquilibrées, avec un rapport d'environ 1 défaut pour 11,4 non-défauts. La cible n'est analysée que sur `application_train`.

## 4. Valeurs manquantes (`application_train`, 122 colonnes)

| % de manquants | Nombre de colonnes |
|---|---:|
| 0 % | 55 |
| ]0 ; 10 %[ | 10 |
| [10 ; 50 %[ | 16 |
| ≥ 50 % | 41 |

Les 20 colonnes les plus lacunaires (59,4 % à 69,9 %) décrivent presque toutes le logement, sous forme de triplets `*_AVG` / `*_MODE` / `*_MEDI` qui ont des taux identiques. S'y ajoute `OWN_CAR_AGE` (66,0 %). Pour les scores externes, le taux de manquants est de 56,38 % pour `EXT_SOURCE_1`, 19,83 % pour `EXT_SOURCE_3` et 0,21 % pour `EXT_SOURCE_2`. Voir `output/00_top20_missing.png`.

## 5. Problèmes détectés et décisions proposées

| # | Constat | Décision proposée (à valider en Phase 2) |
|---|---|---|
| 1 | `DAYS_EMPLOYED = 365243` (valeur sentinelle, soit ≈ 1 000 ans) : **55 374 demandes (18,01 %)**, dont 55 352 retraités et 22 chômeurs. **Taux de défaut 5,40 %**, contre 8,66 % pour les 252 137 autres demandes. La même sentinelle touche 9 274 lignes du test (19,03 %). | Remplacer par NULL et créer l'indicateur `FLAG_DAYS_EMPLOYED_ANOM`. Le groupe a un risque propre, plus faible que la moyenne : il ne doit être ni imputé ni supprimé. |
| 2 | Sentinelle 365243 dans les `DAYS_*` de `previous_application` : `DAYS_FIRST_DRAWING` 55,95 %, `DAYS_TERMINATION` 13,53 %, `DAYS_LAST_DUE` 12,65 %, `DAYS_LAST_DUE_1ST_VERSION` 5,62 %, `DAYS_FIRST_DUE` 2,43 %. | Remplacer par NULL **avant** toute agrégation, sinon les moyennes et maxima sont faussés. |
| 3 | Colonnes `DAYS_*` des tables application : aucune valeur positive en dehors de la sentinelle de `DAYS_EMPLOYED`. | Convertir en années positives (âge, ancienneté). |
| 4 | `CODE_GENDER = 'XNA'` : 4 lignes dans le train, 0 dans le test. | Documenter la modalité. La variable est exclue du modèle et sert uniquement à l'audit d'équité. |
| 5 | Clés orphelines : 5,27 % des `SK_ID_BUREAU` de `bureau_balance` n'ont pas de crédit dans `bureau`. Le taux est de 4 % à 11 % pour les `SK_ID_PREV` des tables mensuelles. | Agréger `bureau_balance` via `bureau` (les orphelins n'ont pas de client). Agréger `pos_cash_balance`, `installments_payments` et `credit_card_balance` directement par `SK_ID_CURR`, qu'elles portent aussi. |
| 6 | Tables enfants à plusieurs lignes par client. | Agréger au grain `SK_ID_CURR` avant la jointure gauche, puis vérifier que la table modèle compte exactement 307 511 lignes. |
| 7 | 41 colonnes ont au moins 50 % de manquants ; un client sur sept n'a pas d'historique bureau et 71,74 % n'ont pas d'historique carte. | Pas de suppression a priori. Le manquant devient une classe du binning optimal et la sélection par IV tranche. L'absence d'historique est conservée comme information. |
| 8 | `EXT_SOURCE_1/2/3` : manquants de 0,21 % à 56,38 %, variables réputées très prédictives. | Les conserver, puis faire une ablation en Phase 4 pour mesurer la dépendance du modèle à ces scores. |
| 9 | Cible déséquilibrée (8,07 %). | Split stratifié, métriques AUC / KS, pas de sur-échantillonnage (préserver la calibration de la PD). |

## 6. Limites de l'audit

- L'audit porte sur la structure et la cohérence des données, pas sur leur véracité : les données ne sont pas contrôlables à la source.
- L'absence de date d'octroi empêche tout contrôle de dérive temporelle.
- Les clés orphelines correspondent vraisemblablement à un extrait partiel fourni par Home Credit. Leur cause n'est pas documentée.
