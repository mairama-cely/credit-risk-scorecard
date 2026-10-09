# Catalogue des variables — table de modélisation

> Version 0.3.1. Généré par `scripts/build_feature_catalog.py` depuis `database/credit_risk.duckdb`. Source, formule, sens attendu et statut sont déclarés dans le script ; taux de manquants, min et max sont lus dans `model_table_train` (307 511 lignes, 208 colonnes). `model_table_test` (48 744 lignes, 207 colonnes) a les mêmes colonnes, sans `TARGET`.

## Conventions

- **Sens attendu** : hypothèse a priori sur le risque quand la variable augmente (↑ le risque augmente, ↓ il diminue). Il sera confronté aux WoE en Phase 3, sur le train seul. « — » pour l'identifiant, la cible et la variable exclue d'équité.
- **Préfixes** : `APP_` demande, `BUR_` bureau, `BB_` bureau_balance (agrégé via bureau), `PREV_` demandes antérieures, `INS_` échéances, `POS_` POS / cash, `CC_` cartes, `HAS_` présence d'historique. Suffixe `_12M` : 12 derniers mois. Colonnes brutes : nom d'origine.
- **Absence d'historique (D7)** : les comptages (`*_NB_*`) valent 0 et `HAS_<SOURCE>_HISTORY` = 0 ; les statistiques restent NULL.
- **Ratios (D10)** : dénominateur nul ou NULL → NULL.
- Min / max : colonnes numériques uniquement. Aucune statistique n'est calculée sur `TARGET` (D9).

## Statuts

| Statut | Colonnes |
|---|---:|
| candidate | 200 |
| exclue du modèle — doublon de APP_*_YEARS (D3) | 5 |
| identifiant | 1 |
| cible | 1 |
| exclue du modèle — audit d'équité | 1 |


## Identifiant et cible (2)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `SK_ID_CURR` | application | Identifiant de la demande | — | identifiant | 0,00 | 100 002 | 456 255 |
| `TARGET` | application_train | 1 = difficultés de paiement, 0 = sinon ; train uniquement (D9) | — | cible | — | — | — |

## Créées — demande (`APP_`, database/01) (14)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `APP_FLAG_DAYS_EMPLOYED_ANOM` | application | 1 si DAYS_EMPLOYED = 365243 dans la source, sinon 0 (D1) | ↓ | candidate | 0,00 | 0 | 1 |
| `APP_AGE_YEARS` | application | -DAYS_BIRTH / 365.25 | ↓ | candidate | 0,00 | 20,5038 | 69,0732 |
| `APP_EMPLOYED_YEARS` | application | -DAYS_EMPLOYED / 365.25 (NULL si sentinelle) | ↓ | candidate | 18,01 | 0 | 49,0404 |
| `APP_REGISTRATION_YEARS` | application | -DAYS_REGISTRATION / 365.25 | ↓ | candidate | 0,00 | 0 | 67,5483 |
| `APP_ID_PUBLISH_YEARS` | application | -DAYS_ID_PUBLISH / 365.25 | ↓ | candidate | 0,00 | 0 | 19,7043 |
| `APP_PHONE_CHANGE_YEARS` | application | -DAYS_LAST_PHONE_CHANGE / 365.25 | ↓ | candidate | 0,00 | 0 | 11,7509 |
| `APP_CREDIT_INCOME_RATIO` | application | AMT_CREDIT / AMT_INCOME_TOTAL | ↑ | candidate | 0,00 | 0,0048 | 84,7368 |
| `APP_ANNUITY_INCOME_RATIO` | application | AMT_ANNUITY / AMT_INCOME_TOTAL | ↑ | candidate | 0,00 | 0,0002 | 1,8760 |
| `APP_CREDIT_GOODS_RATIO` | application | AMT_CREDIT / AMT_GOODS_PRICE | ↑ | candidate | 0,09 | 0,1500 | 6 |
| `APP_CREDIT_TERM_MONTHS` | application | AMT_CREDIT / AMT_ANNUITY (durée implicite) | indéterminé | candidate | 0,00 | 8,0367 | 45,3051 |
| `APP_INCOME_PER_PERSON` | application | AMT_INCOME_TOTAL / CNT_FAM_MEMBERS | ↓ | candidate | 0,00 | 2 812,5000 | 39 000 000 |
| `APP_EMPLOYED_AGE_RATIO` | application | DAYS_EMPLOYED / DAYS_BIRTH (part de la vie en emploi) | ↓ | candidate | 18,01 | 0 | 0,7288 |
| `APP_EXT_SOURCE_MEAN` | application | Moyenne des EXT_SOURCE_1/2/3 renseignés ; NULL si aucun | ↓ | candidate | 0,06 | 0,0000 | 0,8789 |
| `APP_EXT_SOURCE_NB_MISSING` | application | Nombre de EXT_SOURCE_1/2/3 manquants (0 à 3) | ↑ | candidate | 0,00 | 0 | 3 |

## Créées — présence d'historique (`HAS_`, database/10) (6)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `HAS_BUR_HISTORY` | bureau | 1 si au moins un crédit dans bureau | indéterminé | candidate | 0,00 | 0 | 1 |
| `HAS_BB_HISTORY` | bureau_balance via bureau | 1 si au moins un mois de bureau_balance rattaché | indéterminé | candidate | 0,00 | 0 | 1 |
| `HAS_PREV_HISTORY` | previous_application | 1 si au moins une demande antérieure | indéterminé | candidate | 0,00 | 0 | 1 |
| `HAS_INS_HISTORY` | installments_payments | 1 si au moins une échéance | indéterminé | candidate | 0,00 | 0 | 1 |
| `HAS_POS_HISTORY` | pos_cash_balance | 1 si au moins un mois de prêt POS / cash | indéterminé | candidate | 0,00 | 0 | 1 |
| `HAS_CC_HISTORY` | credit_card_balance | 1 si au moins un mois de carte | indéterminé | candidate | 0,00 | 0 | 1 |

## Créées — bureau (`BUR_`, database/02) (11)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `BUR_NB_CREDITS` | bureau | Nombre de crédits déclarés ; 0 sans historique | indéterminé | candidate | 0,00 | 0 | 116 |
| `BUR_NB_ACTIVE` | bureau | Nombre de crédits CREDIT_ACTIVE = 'Active' ; 0 sans historique | ↑ | candidate | 0,00 | 0 | 32 |
| `BUR_NB_CLOSED` | bureau | Nombre de crédits CREDIT_ACTIVE = 'Closed' ; 0 sans historique | ↓ | candidate | 0,00 | 0 | 108 |
| `BUR_NB_SOLD_OR_BAD_DEBT` | bureau | Nombre de crédits CREDIT_ACTIVE IN ('Sold', 'Bad debt') ; 0 sans historique | ↑ | candidate | 0,00 | 0 | 9 |
| `BUR_SUM_CREDIT` | bureau | Somme de AMT_CREDIT_SUM des crédits actifs (0 si aucun actif ; NULL si montants tous inconnus) | indéterminé | candidate | 14,32 | 0 | 334 739 700 |
| `BUR_SUM_DEBT` | bureau | Somme de AMT_CREDIT_SUM_DEBT des crédits actifs (0 si aucun actif ; NULL si montants tous inconnus) | ↑ | candidate | 17,77 | -6 978 830,4900 | 334 498 331,2050 |
| `BUR_DEBT_CREDIT_RATIO` | bureau | BUR_SUM_DEBT / BUR_SUM_CREDIT (crédits actifs) | ↑ | candidate | 33,83 | -309,0900 | 382,5100 |
| `BUR_MAX_DAY_OVERDUE` | bureau | MAX(CREDIT_DAY_OVERDUE) | ↑ | candidate | 14,31 | 0 | 2 792 |
| `BUR_SUM_OVERDUE` | bureau | SUM(AMT_CREDIT_SUM_OVERDUE) | ↑ | candidate | 14,31 | 0 | 3 756 681 |
| `BUR_NB_PROLONG` | bureau | SUM(CNT_CREDIT_PROLONG) ; 0 sans historique | ↑ | candidate | 0,00 | 0 | 9 |
| `BUR_YEARS_SINCE_LAST_CREDIT` | bureau | -MAX(DAYS_CREDIT) / 365.25 | ↓ | candidate | 14,31 | 0 | 8 |

## Créées — historique mensuel du bureau (`BB_`, database/02) (8)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `BB_NB_MONTHS` | bureau_balance via bureau | Nombre de mois observés, tous statuts ; 0 sans historique | ↓ | candidate | 0,00 | 0 | 2 657 |
| `BB_MEAN_SHARE_MONTHS_LATE` | bureau_balance via bureau | Moyenne par crédit de (mois '1'..'5') / (mois '0'..'5') | ↑ | candidate | 70,78 | 0 | 1 |
| `BB_MAX_SHARE_MONTHS_LATE` | bureau_balance via bureau | Max par crédit de (mois '1'..'5') / (mois '0'..'5') | ↑ | candidate | 70,78 | 0 | 1 |
| `BB_MAX_STATUS` | bureau_balance via bureau | Statut de retard maximal (0 à 5), C et X ignorés | ↑ | candidate | 70,78 | 0 | 5 |
| `BB_NB_MONTHS_12M` | bureau_balance via bureau | BB_NB_MONTHS sur MONTHS_BALANCE >= -11 (mois courant = 0) | ↓ | candidate | 0,00 | 0 | 708 |
| `BB_MEAN_SHARE_MONTHS_LATE_12M` | bureau_balance via bureau | BB_MEAN_SHARE_MONTHS_LATE sur MONTHS_BALANCE >= -11 | ↑ | candidate | 76,38 | 0 | 1 |
| `BB_MAX_SHARE_MONTHS_LATE_12M` | bureau_balance via bureau | BB_MAX_SHARE_MONTHS_LATE sur MONTHS_BALANCE >= -11 | ↑ | candidate | 76,38 | 0 | 1 |
| `BB_MAX_STATUS_12M` | bureau_balance via bureau | BB_MAX_STATUS sur MONTHS_BALANCE >= -11 | ↑ | candidate | 76,38 | 0 | 5 |

## Créées — demandes antérieures (`PREV_`, database/03) (15)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `PREV_NB_APPLICATIONS` | previous_application | Nombre de demandes ; 0 sans historique | ↑ | candidate | 0,00 | 0 | 73 |
| `PREV_SHARE_APPROVED` | previous_application | Part NAME_CONTRACT_STATUS = 'Approved' | ↓ | candidate | 5,35 | 0 | 1 |
| `PREV_SHARE_REFUSED` | previous_application | Part NAME_CONTRACT_STATUS = 'Refused' | ↑ | candidate | 5,35 | 0 | 1 |
| `PREV_MEAN_AMT_APPLICATION` | previous_application | AVG(AMT_APPLICATION) | indéterminé | candidate | 5,35 | 0 | 4 050 000 |
| `PREV_MEAN_AMT_CREDIT` | previous_application | AVG(AMT_CREDIT) | indéterminé | candidate | 5,35 | 0 | 4 050 000 |
| `PREV_MEAN_CREDIT_APPLICATION_RATIO` | previous_application | AVG(AMT_CREDIT / AMT_APPLICATION) : accordé / demandé | ↓ | candidate | 5,68 | 0,2000 | 10,1800 |
| `PREV_MEAN_CNT_PAYMENT` | previous_application | AVG(CNT_PAYMENT) : durée moyenne en échéances | indéterminé | candidate | 5,49 | 0 | 72 |
| `PREV_YEARS_SINCE_LAST_APPLICATION` | previous_application | -MAX(DAYS_DECISION) / 365.25 | ↓ | candidate | 5,35 | 0,0027 | 8 |
| `PREV_NB_APPLICATIONS_12M` | previous_application | Nombre de demandes avec DAYS_DECISION >= -365 ; 0 sans historique | ↑ | candidate | 0,00 | 0 | 63 |
| `PREV_SHARE_APPROVED_12M` | previous_application | PREV_SHARE_APPROVED sur DAYS_DECISION >= -365 | ↓ | candidate | 45,05 | 0 | 1 |
| `PREV_SHARE_REFUSED_12M` | previous_application | PREV_SHARE_REFUSED sur DAYS_DECISION >= -365 | ↑ | candidate | 45,05 | 0 | 1 |
| `PREV_MEAN_AMT_APPLICATION_12M` | previous_application | PREV_MEAN_AMT_APPLICATION sur DAYS_DECISION >= -365 | indéterminé | candidate | 45,05 | 0 | 3 850 500 |
| `PREV_MEAN_AMT_CREDIT_12M` | previous_application | PREV_MEAN_AMT_CREDIT sur DAYS_DECISION >= -365 | indéterminé | candidate | 45,05 | 0 | 3 850 500 |
| `PREV_MEAN_CREDIT_APPLICATION_RATIO_12M` | previous_application | PREV_MEAN_CREDIT_APPLICATION_RATIO sur DAYS_DECISION >= -365 | ↓ | candidate | 53,38 | 0,1901 | 8,5000 |
| `PREV_MEAN_CNT_PAYMENT_12M` | previous_application | PREV_MEAN_CNT_PAYMENT sur DAYS_DECISION >= -365 | indéterminé | candidate | 54,10 | 0 | 84 |

## Créées — échéances (`INS_`, database/04) (12)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `INS_NB_INSTALMENTS` | installments_payments | Nombre d'échéances (paiements fractionnés regroupés) ; 0 sans historique | ↓ | candidate | 0,00 | 0 | 332 |
| `INS_MEAN_DAYS_LATE` | installments_payments | Moyenne par échéance de max(dernier paiement - échéance, 0) | ↑ | candidate | 5,16 | 0 | 2 813 |
| `INS_MAX_DAYS_LATE` | installments_payments | Maximum par échéance du retard en jours | ↑ | candidate | 5,16 | 0 | 2 884 |
| `INS_SHARE_LATE` | installments_payments | Part des échéances dont le dernier paiement est en retard | ↑ | candidate | 5,16 | 0 | 1 |
| `INS_MEAN_PAYMENT_RATIO` | installments_payments | Moyenne par échéance de SUM(AMT_PAYMENT) / AMT_INSTALMENT | ↓ | candidate | 5,16 | 0,5122 | 9 189,3167 |
| `INS_SHARE_UNDERPAID` | installments_payments | Part des échéances avec total payé < dû - 0,01 | ↑ | candidate | 5,16 | 0 | 1 |
| `INS_NB_INSTALMENTS_12M` | installments_payments | INS_NB_INSTALMENTS sur échéance >= -365 | ↓ | candidate | 0,00 | 0 | 128 |
| `INS_MEAN_DAYS_LATE_12M` | installments_payments | INS_MEAN_DAYS_LATE sur échéance >= -365 | ↑ | candidate | 29,28 | 0 | 308 |
| `INS_MAX_DAYS_LATE_12M` | installments_payments | INS_MAX_DAYS_LATE sur échéance >= -365 | ↑ | candidate | 29,28 | 0 | 340 |
| `INS_SHARE_LATE_12M` | installments_payments | INS_SHARE_LATE sur échéance >= -365 | ↑ | candidate | 29,28 | 0 | 1 |
| `INS_MEAN_PAYMENT_RATIO_12M` | installments_payments | INS_MEAN_PAYMENT_RATIO sur échéance >= -365 | ↓ | candidate | 29,28 | 0,0056 | 21 563,9277 |
| `INS_SHARE_UNDERPAID_12M` | installments_payments | INS_SHARE_UNDERPAID sur échéance >= -365 | ↑ | candidate | 29,28 | 0 | 1 |

## Créées — POS / cash (`POS_`, database/05) (8)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `POS_NB_MONTHS` | pos_cash_balance | Nombre de mois observés ; 0 sans historique | ↓ | candidate | 0,00 | 0 | 295 |
| `POS_MAX_DPD` | pos_cash_balance | MAX(SK_DPD) | ↑ | candidate | 5,88 | 0 | 4 231 |
| `POS_MEAN_DPD_DEF` | pos_cash_balance | AVG(SK_DPD_DEF) | ↑ | candidate | 5,88 | 0 | 1 740,5545 |
| `POS_SHARE_MONTHS_DPD` | pos_cash_balance | Part des mois avec SK_DPD > 0 | ↑ | candidate | 5,88 | 0 | 1 |
| `POS_NB_MONTHS_12M` | pos_cash_balance | POS_NB_MONTHS sur MONTHS_BALANCE >= -12 (dernier mois = -1) | ↓ | candidate | 0,00 | 0 | 51 |
| `POS_MAX_DPD_12M` | pos_cash_balance | POS_MAX_DPD sur MONTHS_BALANCE >= -12 | ↑ | candidate | 32,72 | 0 | 4 231 |
| `POS_MEAN_DPD_DEF_12M` | pos_cash_balance | POS_MEAN_DPD_DEF sur MONTHS_BALANCE >= -12 | ↑ | candidate | 32,72 | 0 | 2 900,2500 |
| `POS_SHARE_MONTHS_DPD_12M` | pos_cash_balance | POS_SHARE_MONTHS_DPD sur MONTHS_BALANCE >= -12 | ↑ | candidate | 32,72 | 0 | 1 |

## Créées — cartes de crédit (`CC_`, database/06) (12)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `CC_NB_MONTHS` | credit_card_balance | Nombre de mois observés ; 0 sans historique | indéterminé | candidate | 0,00 | 0 | 192 |
| `CC_MEAN_UTILIZATION` | credit_card_balance | AVG(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL) | ↑ | candidate | 72,02 | -0,0848 | 2,1388 |
| `CC_MAX_UTILIZATION` | credit_card_balance | MAX(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL) | ↑ | candidate | 72,02 | 0 | 11,7775 |
| `CC_MAX_DPD` | credit_card_balance | MAX(SK_DPD) | ↑ | candidate | 71,74 | 0 | 2 831 |
| `CC_SHARE_MONTHS_DPD` | credit_card_balance | Part des mois avec SK_DPD > 0 | ↑ | candidate | 71,74 | 0 | 0,9895 |
| `CC_MEAN_DRAWINGS` | credit_card_balance | AVG(AMT_DRAWINGS_CURRENT) | indéterminé | candidate | 71,74 | 0 | 1 125 000 |
| `CC_NB_MONTHS_12M` | credit_card_balance | CC_NB_MONTHS sur MONTHS_BALANCE >= -12 (dernier mois = -1) | indéterminé | candidate | 0,00 | 0 | 30 |
| `CC_MEAN_UTILIZATION_12M` | credit_card_balance | CC_MEAN_UTILIZATION sur MONTHS_BALANCE >= -12 | ↑ | candidate | 76,81 | 0 | 2,7086 |
| `CC_MAX_UTILIZATION_12M` | credit_card_balance | CC_MAX_UTILIZATION sur MONTHS_BALANCE >= -12 | ↑ | candidate | 76,81 | 0 | 11,7775 |
| `CC_MAX_DPD_12M` | credit_card_balance | CC_MAX_DPD sur MONTHS_BALANCE >= -12 | ↑ | candidate | 71,74 | 0 | 2 831 |
| `CC_SHARE_MONTHS_DPD_12M` | credit_card_balance | CC_SHARE_MONTHS_DPD sur MONTHS_BALANCE >= -12 | ↑ | candidate | 71,74 | 0 | 1 |
| `CC_MEAN_DRAWINGS_12M` | credit_card_balance | CC_MEAN_DRAWINGS sur MONTHS_BALANCE >= -12 | indéterminé | candidate | 71,74 | 0 | 1 125 000 |

## Brutes — application (nom d'origine) (120)

| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |
|---|---|---|:---:|---|---:|---:|---:|
| `NAME_CONTRACT_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `CODE_GENDER` | application | Colonne brute, dont 4 lignes 'XNA' dans le train (D4) | — | exclue du modèle — audit d'équité | 0,00 | — | — |
| `FLAG_OWN_CAR` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `FLAG_OWN_REALTY` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `CNT_CHILDREN` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 19 |
| `AMT_INCOME_TOTAL` | application | Colonne brute (description : docs/data_dictionary.md) | ↓ | candidate | 0,00 | 25 650 | 117 000 000 |
| `AMT_CREDIT` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 45 000 | 4 050 000 |
| `AMT_ANNUITY` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 1 615,5000 | 258 025,5000 |
| `AMT_GOODS_PRICE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,09 | 40 500 | 4 050 000 |
| `NAME_TYPE_SUITE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,42 | — | — |
| `NAME_INCOME_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `NAME_EDUCATION_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `NAME_FAMILY_STATUS` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `NAME_HOUSING_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `REGION_POPULATION_RELATIVE` | application | Colonne brute (description : docs/data_dictionary.md) | ↓ | candidate | 0,00 | 0,0003 | 0,0725 |
| `DAYS_BIRTH` | application | Colonne brute, jours avant la demande (négatif) | ↑ | exclue du modèle — doublon de APP_*_YEARS (D3) | 0,00 | -25 229 | -7 489 |
| `DAYS_EMPLOYED` | application | Colonne brute ; 365243 → NULL (D1) | ↑ | exclue du modèle — doublon de APP_*_YEARS (D3) | 18,01 | -17 912 | 0 |
| `DAYS_REGISTRATION` | application | Colonne brute, jours avant la demande (négatif) | ↑ | exclue du modèle — doublon de APP_*_YEARS (D3) | 0,00 | -24 672 | 0 |
| `DAYS_ID_PUBLISH` | application | Colonne brute, jours avant la demande (négatif) | ↑ | exclue du modèle — doublon de APP_*_YEARS (D3) | 0,00 | -7 197 | 0 |
| `OWN_CAR_AGE` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 65,99 | 0 | 91 |
| `FLAG_MOBIL` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_EMP_PHONE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_WORK_PHONE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_CONT_MOBILE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_PHONE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_EMAIL` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `OCCUPATION_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 31,35 | — | — |
| `CNT_FAM_MEMBERS` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 1 | 20 |
| `REGION_RATING_CLIENT` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 1 | 3 |
| `REGION_RATING_CLIENT_W_CITY` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 1 | 3 |
| `WEEKDAY_APPR_PROCESS_START` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `HOUR_APPR_PROCESS_START` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 23 |
| `REG_REGION_NOT_LIVE_REGION` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `REG_REGION_NOT_WORK_REGION` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `LIVE_REGION_NOT_WORK_REGION` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `REG_CITY_NOT_LIVE_CITY` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `REG_CITY_NOT_WORK_CITY` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `LIVE_CITY_NOT_WORK_CITY` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,00 | 0 | 1 |
| `ORGANIZATION_TYPE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | — | — |
| `EXT_SOURCE_1` | application | Colonne brute (description : docs/data_dictionary.md) | ↓ | candidate | 56,38 | 0,0146 | 0,9627 |
| `EXT_SOURCE_2` | application | Colonne brute (description : docs/data_dictionary.md) | ↓ | candidate | 0,21 | 0,0000 | 0,8550 |
| `EXT_SOURCE_3` | application | Colonne brute (description : docs/data_dictionary.md) | ↓ | candidate | 19,83 | 0,0005 | 0,8960 |
| `APARTMENTS_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,75 | 0 | 1 |
| `BASEMENTAREA_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 58,52 | 0 | 1 |
| `YEARS_BEGINEXPLUATATION_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 48,78 | 0 | 1 |
| `YEARS_BUILD_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 66,50 | 0 | 1 |
| `COMMONAREA_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,87 | 0 | 1 |
| `ELEVATORS_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 53,30 | 0 | 1 |
| `ENTRANCES_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,35 | 0 | 1 |
| `FLOORSMAX_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 49,76 | 0 | 1 |
| `FLOORSMIN_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 67,85 | 0 | 1 |
| `LANDAREA_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 59,38 | 0 | 1 |
| `LIVINGAPARTMENTS_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 68,35 | 0 | 1 |
| `LIVINGAREA_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,19 | 0 | 1 |
| `NONLIVINGAPARTMENTS_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,43 | 0 | 1 |
| `NONLIVINGAREA_AVG` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 55,18 | 0 | 1 |
| `APARTMENTS_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,75 | 0 | 1 |
| `BASEMENTAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 58,52 | 0 | 1 |
| `YEARS_BEGINEXPLUATATION_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 48,78 | 0 | 1 |
| `YEARS_BUILD_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 66,50 | 0 | 1 |
| `COMMONAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,87 | 0 | 1 |
| `ELEVATORS_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 53,30 | 0 | 1 |
| `ENTRANCES_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,35 | 0 | 1 |
| `FLOORSMAX_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 49,76 | 0 | 1 |
| `FLOORSMIN_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 67,85 | 0 | 1 |
| `LANDAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 59,38 | 0 | 1 |
| `LIVINGAPARTMENTS_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 68,35 | 0 | 1 |
| `LIVINGAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,19 | 0 | 1 |
| `NONLIVINGAPARTMENTS_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,43 | 0 | 1 |
| `NONLIVINGAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 55,18 | 0 | 1 |
| `APARTMENTS_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,75 | 0 | 1 |
| `BASEMENTAREA_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 58,52 | 0 | 1 |
| `YEARS_BEGINEXPLUATATION_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 48,78 | 0 | 1 |
| `YEARS_BUILD_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 66,50 | 0 | 1 |
| `COMMONAREA_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,87 | 0 | 1 |
| `ELEVATORS_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 53,30 | 0 | 1 |
| `ENTRANCES_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,35 | 0 | 1 |
| `FLOORSMAX_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 49,76 | 0 | 1 |
| `FLOORSMIN_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 67,85 | 0 | 1 |
| `LANDAREA_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 59,38 | 0 | 1 |
| `LIVINGAPARTMENTS_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 68,35 | 0 | 1 |
| `LIVINGAREA_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,19 | 0 | 1 |
| `NONLIVINGAPARTMENTS_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 69,43 | 0 | 1 |
| `NONLIVINGAREA_MEDI` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 55,18 | 0 | 1 |
| `FONDKAPREMONT_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 68,39 | — | — |
| `HOUSETYPE_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,18 | — | — |
| `TOTALAREA_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 48,27 | 0 | 1 |
| `WALLSMATERIAL_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 50,84 | — | — |
| `EMERGENCYSTATE_MODE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 47,40 | — | — |
| `OBS_30_CNT_SOCIAL_CIRCLE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,33 | 0 | 348 |
| `DEF_30_CNT_SOCIAL_CIRCLE` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,33 | 0 | 34 |
| `OBS_60_CNT_SOCIAL_CIRCLE` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,33 | 0 | 344 |
| `DEF_60_CNT_SOCIAL_CIRCLE` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 0,33 | 0 | 24 |
| `DAYS_LAST_PHONE_CHANGE` | application | Colonne brute, jours avant la demande (négatif) | ↑ | exclue du modèle — doublon de APP_*_YEARS (D3) | 0,00 | -4 292 | 0 |
| `FLAG_DOCUMENT_2` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_3` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_4` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_5` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_6` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_7` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_8` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_9` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_10` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_11` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_12` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_13` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_14` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_15` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_16` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_17` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_18` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_19` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_20` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `FLAG_DOCUMENT_21` | application | Colonne brute (description : docs/data_dictionary.md) | indéterminé | candidate | 0,00 | 0 | 1 |
| `AMT_REQ_CREDIT_BUREAU_HOUR` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 4 |
| `AMT_REQ_CREDIT_BUREAU_DAY` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 9 |
| `AMT_REQ_CREDIT_BUREAU_WEEK` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 8 |
| `AMT_REQ_CREDIT_BUREAU_MON` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 27 |
| `AMT_REQ_CREDIT_BUREAU_QRT` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 261 |
| `AMT_REQ_CREDIT_BUREAU_YEAR` | application | Colonne brute (description : docs/data_dictionary.md) | ↑ | candidate | 13,50 | 0 | 25 |
