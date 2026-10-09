# Guide Power BI — tableau de bord « Risque de crédit »

> Statut : tâche reportée — le tableau de bord sera construit ultérieurement à partir de ce guide.

> Phase 5. Données produites par `scripts/export_to_powerbi.py` dans `powerbi_data/` (dossier non versionné, régénéré par le script). Ce guide décrit le modèle de données, l'import Power Query, les mesures DAX, les 4 pages du rapport, la charte graphique et la procédure d'export vers `deployment/`. Aucun chiffre de référence n'est recopié ici : les valeurs de contrôle se lisent dans `dim_scenario.csv`, `model_comparison.csv` et `docs/model_performance_report.md`.

## 1. Fichiers et format

| Fichier | Lignes | Grain | Rôle |
|---|---:|---|---|
| `fact_applications.csv` | 307 511 | une demande | table de faits |
| `dim_applicant.csv` | 307 511 | une demande | attributs de segmentation (1:1) |
| `dim_split.csv` | 3 | un échantillon | libellé et ordre train / validation / test |
| `dim_score_band.csv` | 10 | une tranche de score | bornes, classe de risque A–E, statistiques du train |
| `dim_scenario.csv` | 3 | un scénario | seuil, zone de revue, résultats du test (LGD 45 %) |
| `scenario_results.csv` | 18 | scénario × échantillon × LGD | sensibilité (copie de `cutoff_scenarios.csv`) |
| `model_comparison.csv` | 9 | modèle × échantillon | AUC, Gini, KS, Brier, IC bootstrap (test) |
| `scorecard_points.csv` | 137 | classe d'une variable | grille de score (WoE, points) |
| `shap_importance.csv` | 200 | variable LightGBM | importance SHAP moyenne |
| `fairness.csv` | 2 | genre | audit d'équité (test, scénario recommandé) |
| `calibration.csv` | 20 | modèle × décile de PD | PD prédite vs taux observé (test) |
| `psi.csv` | 18 | score ou variable | indice de stabilité (train → test, train → validation) |

**Format** : UTF-8 avec BOM, séparateur de colonnes `,`, séparateur décimal `.`, pas de séparateur de milliers, booléens en `0/1`, valeur manquante = cellule vide. Sur un poste Windows en français, il faut donc importer avec les paramètres régionaux **Anglais (États-Unis)** (§ 3), sinon `0.219580` devient `219580`.

### Colonnes de `fact_applications`

| Colonne | Type | Description |
|---|---|---|
| `SK_ID_CURR` | entier | identifiant de la demande (clé) |
| `split` | texte | `train`, `valid` ou `test` (clé vers `dim_split`) |
| `score` | entier | score de la grille (élevé = risque faible) |
| `pd_scorecard` | décimal | PD du logit de la grille |
| `pd_lgbm` | décimal | PD du challenger LightGBM |
| `score_band` | entier | tranche 1 (risque le plus élevé) à 10 (clé vers `dim_score_band`) |
| `TARGET` | 0/1 | défaut observé |
| `AMT_CREDIT` | décimal | montant du crédit = exposition (EAD) |
| `expected_loss` | décimal | perte attendue = `pd_scorecard` × 45 % × `AMT_CREDIT` |
| `approved_<scénario>` | 0/1 | décision binaire `score ≥ seuil` (base des indicateurs de la Phase 4) |
| `decision_<scénario>` | texte | zone : `Accepter` (score ≥ seuil + 10), `Revoir` (seuil − 10 ≤ score < seuil + 10), `Refuser` |
| `reason_1` … `reason_3` | texte | trois motifs de refus (variables au plus grand manque de points) ; vide si aucun manque |

`<scénario>` ∈ {`prudent`, `equilibre`, `croissance`}. `dim_applicant` contient : genre, type de contrat, type de revenu, niveau d'études, situation familiale, profession (`Non renseigné` si manquante), secteur de l'employeur, notation de la région, revenu, âge, et des tranches d'âge, de revenu et de montant (`*_band`) avec leur colonne d'ordre (`*_band_order`). Les modalités sont celles du jeu Home Credit (en anglais), non traduites.

## 2. Modèle de données

```
                 dim_split (split)            dim_score_band (score_band)
                        \ 1                     1 /
                         \ *                   * /
 dim_applicant 1 ——— 1  fact_applications (SK_ID_CURR)
 (SK_ID_CURR)

 Tables déconnectées (segments / paramètres) : dim_scenario, Seuil simulé, LGD simulée, dim_decision
 Tables de restitution isolées : model_comparison, scorecard_points, shap_importance, fairness, calibration, psi
 scenario_results[scenario] * ——— 1 dim_scenario[scenario_key]
```

| De (plusieurs) | Vers (un) | Cardinalité | Filtrage croisé | Remarque |
|---|---|---|---|---|
| `fact_applications[split]` | `dim_split[split]` | * : 1 | simple | |
| `fact_applications[score_band]` | `dim_score_band[score_band]` | * : 1 | simple | |
| `fact_applications[SK_ID_CURR]` | `dim_applicant[SK_ID_CURR]` | 1 : 1 | les deux (imposé par Power BI) | les segments de `dim_applicant` filtrent les faits |
| `scenario_results[scenario]` | `dim_scenario[scenario_key]` | * : 1 | simple | |

`dim_scenario` n'est **pas** reliée aux faits : elle sert de segment, et les mesures lisent le seuil choisi avec `SELECTEDVALUE`. Désactiver la détection automatique des relations (Fichier › Options › Fichier actif › Chargement des données) puis créer les relations ci-dessus à la main dans la vue Modèle.

**Tri par colonne** (Outils de colonne › Trier par colonne) : `dim_score_band[band_label]` et `[risk_grade_label]` par `score_band` ; `dim_split[split_label]` par `split_order` ; `dim_scenario[scenario]` par `sort_order` ; `dim_applicant[age_band]`, `[income_band]`, `[credit_band]` par leur colonne `*_order`. Masquer les clés côté faits (`split`, `score_band`) et les colonnes d'ordre.

## 3. Import Power Query

1. Fichier › Options › **Fichier actif › Paramètres régionaux** › « Paramètres régionaux pour l'importation » = **Anglais (États-Unis)**.
2. Accueil › Transformer les données › Gérer les paramètres › **Nouveau paramètre** `DossierDonnees` (Texte), valeur = chemin absolu de `powerbi_data\` **terminé par `\`** (exemple : `C:\Users\<vous>\credit-risk-scorecard\powerbi_data\`).
3. Pour chaque fichier : Obtenir les données › Texte/CSV › origine du fichier **65001 : Unicode (UTF-8)**, délimiteur **Virgule**, détection des types **sur l'ensemble du jeu de données** › Transformer les données. Ou bien Nouvelle source › Requête vide › Éditeur avancé, avec ce modèle (une requête par fichier, nommée comme le fichier) :

```powerquery
let
    Source   = Csv.Document(
                   File.Contents(DossierDonnees & "fact_applications.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Entetes  = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Types    = Table.TransformColumnTypes(Entetes, {
                   {"SK_ID_CURR", Int64.Type}, {"split", type text}, {"score", Int64.Type},
                   {"pd_scorecard", type number}, {"pd_lgbm", type number}, {"score_band", Int64.Type},
                   {"TARGET", Int64.Type}, {"AMT_CREDIT", type number}, {"expected_loss", type number},
                   {"approved_prudent", Int64.Type}, {"decision_prudent", type text},
                   {"approved_equilibre", Int64.Type}, {"decision_equilibre", type text},
                   {"approved_croissance", Int64.Type}, {"decision_croissance", type text},
                   {"reason_1", type text}, {"reason_2", type text}, {"reason_3", type text}},
                   "en-US")
in
    Types
```

   Le dernier argument `"en-US"` de `Table.TransformColumnTypes` garantit la lecture du point décimal quel que soit le paramètre régional du poste.
4. Contrôles dans l'éditeur : `fact_applications` et `dim_applicant` comptent 307 511 lignes ; aucune erreur dans « Qualité de colonne » (Affichage › Qualité de colonne, profil sur l'ensemble du jeu) ; `pd_scorecard` entre 0 et 1.
5. Fermer et appliquer. Pour une mise à jour : relancer `scripts/export_to_powerbi.py` puis Accueil › Actualiser.

Tables DAX à créer ensuite (Modélisation › Nouvelle table) :

```dax
dim_decision =
DATATABLE ( "decision", STRING, "ordre", INTEGER,
    { { "Accepter", 1 }, { "Revoir", 2 }, { "Refuser", 3 } } )
```

Paramètres What-if (Modélisation › Nouveau paramètre › Plage numérique) :

| Nom | Min | Max | Pas | Défaut | Mesure créée |
|---|---:|---:|---:|---:|---|
| `Seuil simulé` | 480 | 640 | 1 | seuil du scénario recommandé (`dim_scenario`, `recommended = 1`) | `[Valeur Seuil simulé]` |
| `LGD simulée` | 0,20 | 0,80 | 0,05 | 0,45 | `[Valeur LGD simulée]` |

## 4. Mesures DAX

Créer une table vide `_Mesures` (Accueil › Entrer des données › Charger) et y ranger les mesures. Formats : taux en pourcentage (1 ou 2 décimales), montants en nombre décimal avec unité « M » (format personnalisé `#,0.0,,"M"`).

### 4.1 Portefeuille

```dax
Nb demandes        = COUNTROWS ( fact_applications )
Nb défauts         = SUM ( fact_applications[TARGET] )
Taux de défaut     = DIVIDE ( [Nb défauts], [Nb demandes] )
Exposition         = SUM ( fact_applications[AMT_CREDIT] )
Perte attendue     = SUM ( fact_applications[expected_loss] )           -- LGD 45 %
PD moyenne grille  = AVERAGE ( fact_applications[pd_scorecard] )
PD moyenne LightGBM = AVERAGE ( fact_applications[pd_lgbm] )
Score moyen        = AVERAGE ( fact_applications[score] )
Perte attendue % exposition = DIVIDE ( [Perte attendue], [Exposition] )
```

### 4.2 Scénario choisi (segment `dim_scenario`)

```dax
Demi-largeur revue = 10      -- points, cutoff_strategy.json : review_half_width_points

Seuil scénario =
VAR reco = CALCULATE ( MAX ( dim_scenario[cutoff] ), dim_scenario[recommended] = 1 )
RETURN COALESCE ( SELECTEDVALUE ( dim_scenario[cutoff] ), reco )

Nb acceptés =
VAR c = [Seuil scénario]
RETURN CALCULATE ( [Nb demandes], fact_applications[score] >= c )

Taux d'acceptation = DIVIDE ( [Nb acceptés], [Nb demandes] )

Taux de défaut des acceptés =
VAR c = [Seuil scénario]
RETURN DIVIDE ( CALCULATE ( [Nb défauts], fact_applications[score] >= c ), [Nb acceptés] )

Bons refusés =
VAR c = [Seuil scénario]
RETURN CALCULATE ( [Nb demandes], fact_applications[score] < c, fact_applications[TARGET] = 0 )

% bons refusés =
DIVIDE ( [Bons refusés], CALCULATE ( [Nb demandes], fact_applications[TARGET] = 0 ) )

Perte attendue acceptée =
VAR c = [Seuil scénario]
RETURN CALCULATE ( [Perte attendue], fact_applications[score] >= c )

Perte évitée =
VAR c = [Seuil scénario]
RETURN CALCULATE ( [Perte attendue], fact_applications[score] < c )

% perte évitée = DIVIDE ( [Perte évitée], [Perte attendue] )

% zone de revue =
VAR c = [Seuil scénario]
VAR h = [Demi-largeur revue]
RETURN DIVIDE (
    CALCULATE ( [Nb demandes], fact_applications[score] >= c - h, fact_applications[score] < c + h ),
    [Nb demandes] )
```

Contrôle : avec `dim_split = test` et le scénario recommandé sélectionné, `[Taux d'acceptation]`, `[Taux de défaut des acceptés]`, `[% bons refusés]`, `[Perte évitée]` et `[% zone de revue]` doivent égaler les colonnes `test_*` de `dim_scenario` (le script d'export vérifie déjà cette égalité côté Python).

### 4.3 Simulateur What-if (seuil et LGD libres)

```dax
Seuil actif = [Valeur Seuil simulé]
LGD active  = [Valeur LGD simulée]

PA (LGD simulée) =
SUMX ( fact_applications, fact_applications[pd_scorecard] * fact_applications[AMT_CREDIT] ) * [LGD active]

Sim - Taux d'acceptation =
VAR c = [Seuil actif]
RETURN DIVIDE ( CALCULATE ( [Nb demandes], fact_applications[score] >= c ), [Nb demandes] )

Sim - Taux de défaut des acceptés =
VAR c = [Seuil actif]
RETURN DIVIDE (
    CALCULATE ( [Nb défauts], fact_applications[score] >= c ),
    CALCULATE ( [Nb demandes], fact_applications[score] >= c ) )

Sim - % bons refusés =
VAR c = [Seuil actif]
RETURN DIVIDE (
    CALCULATE ( [Nb demandes], fact_applications[score] < c, fact_applications[TARGET] = 0 ),
    CALCULATE ( [Nb demandes], fact_applications[TARGET] = 0 ) )

Sim - PA acceptée =
VAR c = [Seuil actif]
RETURN CALCULATE ( [PA (LGD simulée)], fact_applications[score] >= c )

Sim - Perte évitée =
VAR c = [Seuil actif]
RETURN CALCULATE ( [PA (LGD simulée)], fact_applications[score] < c )

Sim - % perte évitée = DIVIDE ( [Sim - Perte évitée], [PA (LGD simulée)] )

Sim - Perte observée évitée =      -- défauts réels × LGD × montant, refusés seulement
VAR c = [Seuil actif]
RETURN CALCULATE (
    SUMX ( fact_applications, fact_applications[TARGET] * fact_applications[AMT_CREDIT] ),
    fact_applications[score] < c ) * [LGD active]

Sim - Critère (évitée − bons refusés) = [Sim - % perte évitée] - [Sim - % bons refusés]

-- Décision dynamique : nombre de demandes par zone (axe = dim_decision[decision])
Sim - Nb par décision =
VAR c = [Seuil actif]
VAR h = [Demi-largeur revue]
RETURN SWITCH ( SELECTEDVALUE ( dim_decision[decision] ),
    "Accepter", CALCULATE ( [Nb demandes], fact_applications[score] >= c + h ),
    "Revoir",   CALCULATE ( [Nb demandes], fact_applications[score] >= c - h, fact_applications[score] < c + h ),
    "Refuser",  CALCULATE ( [Nb demandes], fact_applications[score] < c - h ) )

-- Décision dynamique au niveau d'une demande (visuel Table avec SK_ID_CURR)
Sim - Décision =
VAR s = SELECTEDVALUE ( fact_applications[score] )
VAR c = [Seuil actif]
VAR h = [Demi-largeur revue]
RETURN IF ( ISBLANK ( s ), BLANK (),
    IF ( s >= c + h, "Accepter", IF ( s >= c - h, "Revoir", "Refuser" ) ) )
```

Le critère `[Sim - Critère]` reproduit la règle de recommandation de la Phase 4 (part de perte attendue évitée − part de bons clients refusés) ; la part évitée ne dépend pas de la LGD.

### 4.4 Modèle, stabilité, équité

```dax
AUC grille test     = CALCULATE ( MAX ( model_comparison[auc] ), model_comparison[model] = "scorecard", model_comparison[split] = "test" )
AUC LightGBM test   = CALCULATE ( MAX ( model_comparison[auc] ), model_comparison[model] = "lgbm",      model_comparison[split] = "test" )
Écart AUC LightGBM − grille = [AUC LightGBM test] - [AUC grille test]

PSI score (train → test) = CALCULATE ( MAX ( psi[psi] ), psi[level] = "score" )
PSI max variables        = CALCULATE ( MAX ( psi[psi] ), psi[level] = "variable" )
PSI statut =
VAR p = [PSI score (train → test)]
RETURN SWITCH ( TRUE (), p < 0.10, "Stable", p < 0.25, "À surveiller", "Instable" )
PSI couleur =                      -- mise en forme conditionnelle « Valeur du champ »
VAR p = [PSI score (train → test)]
RETURN SWITCH ( TRUE (), p < 0.10, "#2a78d6", p < 0.25, "#a3a29d", "#c8553d" )

-- PSI recalculé dans le rapport : train (attendu) vs échantillon filtré (observé), sur les 10 tranches
PSI dynamique =
VAR tot_e = CALCULATE ( [Nb demandes], dim_split[split] = "train", REMOVEFILTERS ( dim_score_band ) )
VAR tot_a = CALCULATE ( [Nb demandes], REMOVEFILTERS ( dim_score_band ) )
RETURN SUMX ( VALUES ( dim_score_band[score_band] ),
    VAR e = MAX ( DIVIDE ( CALCULATE ( [Nb demandes], dim_split[split] = "train" ), tot_e ), 1E-6 )
    VAR a = MAX ( DIVIDE ( [Nb demandes], tot_a ), 1E-6 )      -- plancher 1e-6 comme evaluate_models.psi
    RETURN ( a - e ) * LN ( a / e ) )

Ratio acceptation H/F =
VAR m = CALCULATE ( [Taux d'acceptation], dim_applicant[CODE_GENDER] = "M" )
VAR f = CALCULATE ( [Taux d'acceptation], dim_applicant[CODE_GENDER] = "F" )
RETURN DIVIDE ( m, f )
Règle des 4/5 = IF ( [Ratio acceptation H/F] >= 0.8, "Respectée", "Non respectée" )

Refus – 1er motif =                 -- axe = fact_applications[reason_1]
VAR c = [Seuil scénario]
RETURN CALCULATE ( [Nb demandes], fact_applications[score] < c )
```

`PSI dynamique`, filtré sur `dim_split = test`, doit égaler la ligne `score` de `psi.csv` (train → test ; même formule et même plancher que `scripts/evaluate_models.py`, vérifié en Python sur les CSV exportés).

## 5. Pages du rapport

Format de page 16:9 (1280 × 720). En haut de chaque page : titre (Segoe UI Semibold 20, encre), sous-titre de source, segments `dim_split[split_label]` (défaut : **Test**) et, pages 1, 2 et 4, `dim_scenario[scenario]` (sélection unique, défaut : scénario recommandé).

### Page 1 — Portefeuille de risque

| Visuel | Champs |
|---|---|
| 5 cartes | `[Nb demandes]`, `[Taux de défaut]`, `[Exposition]`, `[Perte attendue]`, `[PD moyenne grille]` |
| Graphique combiné (colonnes + ligne) | axe `dim_score_band[band_label]` ; colonnes `[Nb demandes]` ; ligne `[Taux de défaut]` (axe secondaire) |
| Histogramme empilé 100 % | axe `dim_score_band[risk_grade_label]` ; valeurs `[Exposition]` et `[Perte attendue]` |
| Courbe | axe `dim_score_band[band_label]` ; `[PD moyenne grille]` vs `[Taux de défaut]` (calibration par tranche) |
| Tableau | `dim_split[split_label]`, `[Nb demandes]`, `[Taux de défaut]`, `[Score moyen]`, `[Perte attendue % exposition]` |

Message clé : le taux de défaut décroît de façon monotone de la tranche T01 à T10.

### Page 2 — Segments

| Visuel | Champs |
|---|---|
| Matrice | lignes `dim_applicant[NAME_INCOME_TYPE]` › `[NAME_EDUCATION_TYPE]` ; valeurs `[Nb demandes]`, `[Taux de défaut]`, `[Score moyen]`, `[Taux d'acceptation]`, `[Taux de défaut des acceptés]` ; barres de données sur `[Taux de défaut]` |
| Barres groupées | axe `dim_applicant[age_band]` ; `[Taux de défaut]` et `[Taux d'acceptation]` |
| Barres groupées | axe `dim_applicant[income_band]` ; idem |
| Nuage de points | détails `dim_applicant[OCCUPATION_TYPE]` ; X `[Taux de défaut]`, Y `[Taux d'acceptation]`, taille `[Nb demandes]` |
| Barres | axe `dim_applicant[CODE_GENDER]` ; `[Taux d'acceptation]` ; carte `[Ratio acceptation H/F]` avec `[Règle des 4/5]` |
| Segments | `dim_applicant[NAME_CONTRACT_TYPE]`, `[REGION_RATING_CLIENT_W_CITY]`, `[credit_band]` |

Note de bas de page : le genre ne fait pas partie du modèle ; il est affiché pour l'audit d'équité seulement.

### Page 3 — Simulateur de cut-off (What-if)

| Visuel | Champs |
|---|---|
| Curseurs | `Seuil simulé`, `LGD simulée` (segments de paramètre, style « Valeur unique ») |
| 6 cartes | `[Sim - Taux d'acceptation]`, `[Sim - Taux de défaut des acceptés]`, `[Sim - % bons refusés]`, `[Sim - PA acceptée]`, `[Sim - Perte évitée]`, `[Sim - % perte évitée]` |
| Histogramme | axe `dim_decision[decision]` (trié par `ordre`) ; `[Sim - Nb par décision]` ; couleurs Accepter = bleu, Revoir = gris, Refuser = rouge |
| Courbe de compromis | axe X `'Seuil simulé'[Seuil simulé]` ; Y `[Sim - Taux d'acceptation]`, `[Sim - Taux de défaut des acceptés]` ; ligne constante X = `[Seuil scénario]` (volet Analytique) |
| Courbe du critère | axe X `'Seuil simulé'[Seuil simulé]` ; Y `[Sim - Critère (évitée − bons refusés)]` |
| Tableau des scénarios | `dim_scenario` : `scenario`, `cutoff`, `review_low`, `review_high`, `test_approval_rate`, `test_bad_rate_accepted`, `test_el_avoided_pct`, `test_breakeven_margin` ; mise en évidence de `recommended = 1` |
| Tableau détaillé | `fact_applications[SK_ID_CURR]`, `[score]`, `[pd_scorecard]`, `[Sim - Décision]`, `[reason_1]`, `[reason_2]`, `[reason_3]` (filtre Top N 100 sur le score le plus proche du seuil, ou recherche par identifiant) |

Pour les deux courbes, ne pas appliquer le curseur `Seuil simulé` au visuel (Format › Modifier les interactions › Aucun) : chaque point de l'axe porte sa propre valeur de seuil.

### Page 4 — Modèle & explicabilité

| Visuel | Champs |
|---|---|
| Histogramme groupé | axe `model_comparison[model_label]` ; légende `split_label` (trié par `split_order`) ; valeur `auc` ; barres d'erreur `auc_ci_low` / `auc_ci_high` (test) |
| 3 cartes | `[AUC grille test]`, `[AUC LightGBM test]`, `[Écart AUC LightGBM − grille]` |
| Courbe | `calibration` : axe `decile`, `pd_mean` et `observed_rate`, légende `model_label` |
| Barres horizontales | `scorecard_points` : axe `variable`, valeur `var_max_points − var_min_points` (colonne calculée « amplitude ») triée décroissante |
| Barres horizontales | `shap_importance` : axe `feature`, valeur `share_pct`, filtre Top N 15 ; couleur conditionnelle `is_ext_source` |
| Tableau PSI | `psi` : `name`, `psi`, `psi_train_valid`, `flag` ; carte `[PSI score (train → test)]` colorée par `[PSI couleur]`, sous-titre `[PSI statut]` |
| Barres | axe `fact_applications[reason_1]` ; `[Refus – 1er motif]` |
| Tableau | `fairness` : `group`, `approval_rate`, `approval_rate_goods`, `approval_ratio_vs_max`, `four_fifths_ok` |

## 6. Charte graphique

Palette identique aux figures des notebooks (`output/*.png`) :

| Rôle | Couleur |
|---|---|
| Accent principal (grille, accepté, séries 1) | bleu `#2a78d6` |
| Texte, titres | encre `#0b0b0b` |
| Texte secondaire, axes | `#52514e` |
| Série de comparaison (LightGBM vs grille, revue) | gris `#a3a29d` |
| Quadrillage, bordures | `#e4e3df` |
| Alerte, refus, défaut | rouge `#c8553d` |
| Fond de page et des visuels | `#fcfcfb` |

Thème à enregistrer sous `deployment/credit_risk_theme.json` puis Affichage › Thèmes › Rechercher des thèmes :

```json
{
  "name": "Credit Risk Scorecard",
  "dataColors": ["#2a78d6", "#a3a29d", "#c8553d", "#0b0b0b", "#52514e", "#e4e3df"],
  "foreground": "#0b0b0b",
  "foregroundNeutralSecondary": "#52514e",
  "background": "#fcfcfb",
  "tableAccent": "#2a78d6",
  "good": "#2a78d6",
  "neutral": "#a3a29d",
  "bad": "#c8553d",
  "textClasses": {
    "title":  { "fontFace": "Segoe UI Semibold", "fontSize": 14, "color": "#0b0b0b" },
    "label":  { "fontFace": "Segoe UI", "fontSize": 10, "color": "#52514e" },
    "callout": { "fontFace": "Segoe UI Semibold", "fontSize": 28, "color": "#0b0b0b" }
  },
  "visualStyles": {
    "*": { "*": {
      "background": [{ "color": { "solid": { "color": "#fcfcfb" } }, "transparency": 0 }],
      "border": [{ "color": { "solid": { "color": "#e4e3df" } } }]
    } }
  }
}
```

Règles : une seule couleur d'accent par visuel ; rouge réservé aux refus, défauts et alertes ; pas de dégradés ni d'effets 3D ; axes commençant à 0 pour les histogrammes ; libellés de données en pourcentage à 1 décimale (taux de défaut des acceptés : 2 décimales).

## 7. Export vers `deployment/` — liste de contrôle

- [ ] `scripts/export_to_powerbi.py` relancé ; la console affiche le contrôle de cohérence et les effectifs (307 511 lignes pour les deux grandes tables).
- [ ] Paramètres régionaux d'import = Anglais (États-Unis) ; aucune erreur de type dans Power Query.
- [ ] Relations conformes au § 2 ; détection automatique désactivée ; tris par colonne appliqués.
- [ ] Contrôle des mesures (§ 4.2) : test + scénario recommandé = colonnes `test_*` de `dim_scenario`.
- [ ] `Seuil simulé` placé sur le seuil recommandé à l'enregistrement ; `LGD simulée` sur 0,45 ; segment d'échantillon sur Test.
- [ ] Thème appliqué ; titres et sous-titres de source (« Home Credit (Kaggle) — test scellé ») sur chaque page.
- [ ] Rapport enregistré sous `deployment/credit_risk_scorecard.pbix` (vérifier la taille : la limite GitHub est de 100 Mo par fichier ; au-delà, versionner seulement le PDF et les captures).
- [ ] Fichier › Exporter › PDF → `deployment/credit_risk_scorecard.pdf` (4 pages).
- [ ] Une capture PNG par page (1280 × 720 minimum) : `deployment/powerbi_01_portefeuille.png`, `powerbi_02_segments.png`, `powerbi_03_simulateur.png`, `powerbi_04_modele.png`.
- [ ] Captures relues : aucun chiffre tronqué, légendes lisibles, unités (« M » = millions d'unités monétaires du jeu de données, non converties en FCFA).
