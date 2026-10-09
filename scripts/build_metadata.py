"""Phases 1 à 5 — Génère docs/data_dictionary.md depuis la base DuckDB (lecture seule).

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/build_metadata.py

Phase 1 : volumes lus dans meta_load_log, clés orphelines (requête d_integrite_referentielle),
constats sur les variables clés d'application_train et dictionnaire colonne par colonne lu dans
homecredit_columns_description.
Phase 2 : volumes des tables produites par scripts/build_features.py, renvoi vers
docs/feature_catalog.md.
Phase 3 : volumes des tables du découpage (scripts/make_splits.py), si elles existent.
Phases 3 à 5 : tableaux de résultats versionnés de output/tables/ (CSV), dimensions lues dans les
fichiers s'ils existent.
Le fichier ne contient pas de date : il est identique octet pour octet tant que la base ne change
pas. Relancer le script réécrit le fichier entier (aucun ajout en double).
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import COLUMNS_DESCRIPTION_TABLE, DB_PATH, PROJECT_ROOT, TABLES_DIR  # noqa: E402
from run_quality_checks import parse_checks  # noqa: E402

VERSION = "0.6.0"
OUT = PROJECT_ROOT / "docs" / "data_dictionary.md"

# Tables produites après la Phase 1 : (table, contenu, phase) ; volumes lus dans la base
PRODUCED_TABLES = [
    ("application_all", "`application_train` ∪ `application_test`, `IS_TRAIN`, variables `APP_` (database/01)", "P2"),
    ("feat_bureau_balance_credit", "`bureau_balance` agrégé par `SK_ID_BUREAU` (database/02)", "P2"),
    ("feat_bureau", "Agrégats `BUR_` et `BB_` par `SK_ID_CURR` (database/02)", "P2"),
    ("previous_application_clean", "`previous_application`, sentinelles 365243 → NULL (database/03)", "P2"),
    ("feat_previous_application", "Agrégats `PREV_` par `SK_ID_CURR` (database/03)", "P2"),
    ("feat_installments", "Agrégats `INS_` par `SK_ID_CURR` (database/04)", "P2"),
    ("feat_pos_cash", "Agrégats `POS_` par `SK_ID_CURR` (database/05)", "P2"),
    ("feat_credit_card", "Agrégats `CC_` par `SK_ID_CURR` (database/06)", "P2"),
    ("model_table_train", "Table de modélisation du train, avec `TARGET` (database/10)", "P2"),
    ("model_table_test", "Table de modélisation du test, sans `TARGET` (database/10)", "P2"),
    ("split_assignment", "Affectation de chaque `SK_ID_CURR` à train / valid / test (`make_splits.py`, D14)", "P3"),
    ("split_meta", "Effectifs, taux de défaut et empreintes SHA-256 par échantillon (D15)", "P3"),
]

# Tableaux de résultats versionnés (output/tables/, D22) : (fichier, contenu, script, phase) ;
# dimensions lues dans le CSV. Les JSON du même dossier (métriques) ne sont pas listés ici.
OUTPUT_TABLES = [
    ("iv_table.csv", "IV, classes, monotonie, sens observé et motif d'exclusion de chaque candidate", "train_scorecard.py", "P3"),
    ("scorecard_table.csv", "Grille de points : variable, classe, effectif, taux de défaut, WoE, points", "train_scorecard.py", "P3"),
    ("lgbm_feature_importance.csv", "Importance des variables du challenger LightGBM (gain, nombre de splits)", "train_challenger.py", "P4"),
    ("shap_importance.csv", "Importance SHAP moyenne absolue du challenger (validation)", "train_challenger.py", "P4"),
    ("final_comparison.csv", "AUC, Gini, KS, Brier par modèle et par échantillon (train / valid / test)", "evaluate_models.py", "P4"),
    ("calibration_test.csv", "Calibration par décile de PD sur le test, avec contrôle isotone", "evaluate_models.py", "P4"),
    ("psi_table.csv", "PSI du score et des 17 variables retenues (train → test, train → valid)", "evaluate_models.py", "P4"),
    ("fairness_table.csv", "Audit d'équité par `CODE_GENDER` au seuil recommandé", "evaluate_models.py", "P4"),
    ("refusal_reasons.csv", "Motifs de refus : 1er motif et top 3 parmi les refusés", "evaluate_models.py", "P4"),
    ("cutoff_scenarios.csv", "3 scénarios de seuil × échantillon × LGD : acceptation, défaut, perte attendue", "build_cutoff_strategy.py", "P4"),
    ("score_deciles.csv", "Déciles de score : défaut observé, PD moyenne, approbation cumulée", "build_cutoff_strategy.py", "P4"),
]

# Relations dont le taux de clés orphelines est reporté sous le schéma relationnel
# (préfixe du libellé `relation` de la requête d_integrite_referentielle)
ORPHAN_RELATIONS = ("bureau_balance.SK_ID_BUREAU", "credit_card_balance.SK_ID_PREV")

ER_DIAGRAM = [
    "```mermaid",
    "erDiagram",
    "    application {",
    '        int SK_ID_CURR PK "application_train et application_test"',
    "    }",
    "    bureau {",
    "        int SK_ID_BUREAU PK",
    "        int SK_ID_CURR FK",
    "    }",
    "    bureau_balance {",
    "        int SK_ID_BUREAU FK",
    "    }",
    "    previous_application {",
    "        int SK_ID_PREV PK",
    "        int SK_ID_CURR FK",
    "    }",
    "    pos_cash_balance {",
    "        int SK_ID_PREV FK",
    "        int SK_ID_CURR FK",
    "    }",
    "    installments_payments {",
    "        int SK_ID_PREV FK",
    "        int SK_ID_CURR FK",
    "    }",
    "    credit_card_balance {",
    "        int SK_ID_PREV FK",
    "        int SK_ID_CURR FK",
    "    }",
    '    application ||--o{ bureau : "SK_ID_CURR"',
    '    bureau ||--o{ bureau_balance : "SK_ID_BUREAU"',
    '    application ||--o{ previous_application : "SK_ID_CURR"',
    '    previous_application ||--o{ pos_cash_balance : "SK_ID_PREV"',
    '    previous_application ||--o{ installments_payments : "SK_ID_PREV"',
    '    previous_application ||--o{ credit_card_balance : "SK_ID_PREV"',
    '    application ||--o{ pos_cash_balance : "SK_ID_CURR"',
    '    application ||--o{ installments_payments : "SK_ID_CURR"',
    '    application ||--o{ credit_card_balance : "SK_ID_CURR"',
    "```",
]

# Table DuckDB -> (grain, clé propre, clé(s) de jointure, rôle dans le projet)
TABLE_INFO = {
    "application_train": ("1 demande de crédit, avec `TARGET`", "`SK_ID_CURR`", "—", "✅ table de base"),
    "application_test": ("1 demande de crédit, sans `TARGET`", "`SK_ID_CURR`", "—", "❌ jamais pour la performance (pas de cible)"),
    "bureau": ("1 crédit externe déclaré au bureau", "`SK_ID_BUREAU`", "`SK_ID_CURR`", "✅ agrégée (P2)"),
    "bureau_balance": ("1 mois d'un crédit externe", "—", "`SK_ID_BUREAU`", "✅ agrégée via `bureau` (P2)"),
    "previous_application": ("1 demande antérieure chez Home Credit", "`SK_ID_PREV`", "`SK_ID_CURR`", "✅ agrégée (P2)"),
    "pos_cash_balance": ("1 mois d'un prêt POS / cash antérieur", "—", "`SK_ID_PREV`, `SK_ID_CURR`", "✅ agrégée (P2)"),
    "installments_payments": ("1 échéance d'un prêt antérieur", "—", "`SK_ID_PREV`, `SK_ID_CURR`", "✅ agrégée (P2)"),
    "credit_card_balance": ("1 mois d'une carte antérieure", "—", "`SK_ID_PREV`, `SK_ID_CURR`", "✅ agrégée (P2)"),
    "homecredit_columns_description": ("1 colonne documentée", "—", "—", "Dictionnaire"),
}


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def cell(v) -> str:
    return "" if v is None else str(v).replace("|", "\\|").replace("\n", " ").strip()


def pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def build() -> str:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        existing = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        log = con.execute("SELECT table_name, csv_file, n_rows, n_cols FROM meta_load_log").fetchall()
        desc = con.execute(
            f'SELECT "Table", "Row", "Description", "Special" FROM {COLUMNS_DESCRIPTION_TABLE}'
        ).fetchall()
        integrity = con.execute(parse_checks()["d_integrite_referentielle"]).fetchall()
        pct_target, pct_sentinel, *pct_ext_missing = con.execute(
            """
            SELECT 100.0 * AVG(TARGET),
                   100.0 * COUNT(*) FILTER (WHERE DAYS_EMPLOYED = 365243) / COUNT(*),
                   100.0 * COUNT(*) FILTER (WHERE EXT_SOURCE_1 IS NULL) / COUNT(*),
                   100.0 * COUNT(*) FILTER (WHERE EXT_SOURCE_2 IS NULL) / COUNT(*),
                   100.0 * COUNT(*) FILTER (WHERE EXT_SOURCE_3 IS NULL) / COUNT(*)
            FROM application_train
            """
        ).fetchone()
        produced = [
            (t, content, phase, *con.execute(
                f"SELECT COUNT(*), (SELECT COUNT(*) FROM (DESCRIBE {t})) FROM {t}"
            ).fetchone())
            for t, content, phase in PRODUCED_TABLES
            if t in existing
        ]

    outputs = []
    with duckdb.connect() as mem:
        for f, content, script, phase in OUTPUT_TABLES:
            path = TABLES_DIR / f
            if path.exists():
                quoted = str(path).replace("'", "''")
                n, c = mem.execute(
                    f"SELECT COUNT(*), (SELECT COUNT(*) FROM (DESCRIBE SELECT * FROM read_csv('{quoted}'))) "
                    f"FROM read_csv('{quoted}')"
                ).fetchone()
                outputs.append((f, content, script, phase, n, c))

    orphans = [
        f"- `{relation}` : {fmt(n - found)} clés distinctes sur {fmt(n)} sans correspondance, "
        f"soit {pct(100 * (n - found) / n)} % de clés orphelines."
        for relation, n, found, _ in integrity
        if relation.startswith(ORPHAN_RELATIONS)
    ]

    out = [
        "# Métadonnées — Dictionnaire de données",
        "",
        f"> Version {VERSION}. Généré par `scripts/build_metadata.py` depuis `database/credit_risk.duckdb` : "
        "volumes mesurés au chargement (Phase 1), après construction de la table modèle (Phase 2) et après le découpage "
        "(Phase 3), tableaux de résultats de `output/tables/` (Phases 3 à 5) ; dictionnaire issu de `HomeCredit_columns_description.csv`.",
        "",
        "## Source",
        "",
        "| Élément | Valeur |",
        "|---------|--------|",
        "| Nom | Home Credit Default Risk |",
        "| Fournisseur | Home Credit Group, via Kaggle (compétition 2018) |",
        "| Accès | Téléchargement manuel depuis l'onglet *Data* de la compétition `home-credit-default-risk` (API Kaggle non utilisée) |",
        "| Licence | Règles de la compétition Kaggle home-credit-default-risk (onglet Rules de la compétition) |",
        "| Format | 9 CSV (8 tables + dictionnaire), chargés dans DuckDB `database/credit_risk.duckdb` |",
        "| Encodage | UTF-8, sauf `HomeCredit_columns_description.csv` (cp1252) |",
        "",
        "## Tables et clés (volumes mesurés)",
        "",
        "| Table DuckDB | Fichier source | Grain (1 ligne =) | Clé propre | Clé de jointure | Lignes | Colonnes | Rôle |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for table, csv_file, n_rows, n_cols in log:
        grain, pk, fk, role = TABLE_INFO[table]
        out.append(f"| `{table}` | `{csv_file}` | {grain} | {pk} | {fk} | {fmt(n_rows)} | {n_cols} | {role} |")

    out += [
        "",
        "## Schéma relationnel",
        "",
        *ER_DIAGRAM,
        "",
        "Structure établie d'après la documentation de la compétition Kaggle Home Credit Default Risk.",
        "",
        "Clés orphelines mesurées en Phase 1 (requête `d_integrite_referentielle`, clés distinctes de la table enfant absentes de la table parent) :",
        "",
        *orphans,
        "",
        "Les tables enfants ont plusieurs lignes par client : elles sont agrégées au grain `SK_ID_CURR` avant toute jointure (Phase 2). "
        "Intégrité mesurée en Phase 1 : voir `docs/data_quality_report.md`.",
        "",
        "## Variables clés de `application_train`",
        "",
        "| Variable | Description | Constat Phase 1 |",
        "|---|---|---|",
        f"| `TARGET` | 1 = difficultés de paiement, 0 = sinon | Cible, {pct(pct_target)} % de 1 |",
        f"| `DAYS_EMPLOYED` | Ancienneté dans l'emploi, en jours (négatif) | Sentinelle `365243` sur {pct(pct_sentinel)} % des lignes |",
        "| `DAYS_BIRTH` | Âge en jours (négatif) | Aucune valeur positive |",
        f"| `EXT_SOURCE_1/2/3` | Scores externes normalisés | Manquants : {' / '.join(f'{pct(x)} %' for x in pct_ext_missing)} |",
        "| `CODE_GENDER` | Sexe | 4 lignes `XNA` ; **exclu du modèle**, audit d'équité seulement |",
        "",
        "## Tables produites",
        "",
        "| Table | Contenu | Phase |",
        "|---|---|---|",
        "| `meta_load_log` | Journal de chargement : fichier, taille, encodage, lignes CSV vs lignes chargées | P1 |",
    ]
    out += [f"| `{t}` | {content} ({fmt(n)} lignes × {c} col.) | {phase} |" for t, content, phase, n, c in produced]
    out += [
        "",
        "Variables de la table modèle (source, formule, sens attendu, statut, manquants, min, max) : "
        "[`docs/feature_catalog.md`](feature_catalog.md), généré par `scripts/build_feature_catalog.py`. "
        "Exports Parquet (non versionnés) : `data/processed/model_table_train.parquet`, `model_table_test.parquet` "
        "et `data/interim/split_assignment.parquet`.",
        "",
        "## Tableaux de résultats versionnés (`output/tables/`)",
        "",
        "| Fichier | Contenu | Produit par | Phase |",
        "|---|---|---|---|",
    ]
    out += [
        f"| `{f}` | {content} ({fmt(n)} lignes × {c} col.) | `scripts/{script}` | {phase} |"
        for f, content, script, phase, n, c in outputs
    ]
    out += [
        "",
        "Métriques au format JSON dans le même dossier (`scorecard_metrics.json`, `challenger_metrics.json`, "
        "`evaluation_metrics.json`, `cutoff_strategy.json`). Rapports : [`docs/scorecard_report.md`](scorecard_report.md), "
        "[`docs/model_performance_report.md`](model_performance_report.md). Modèles sérialisés (`models/`) et exports "
        "Power BI (`powerbi_data/`) : non versionnés, régénérés par les scripts.",
        "",
        f"## Dictionnaire des colonnes ({len(desc)} entrées)",
        "",
        "Reproduit tel que fourni par Home Credit (descriptions en anglais). Colonne *Table* = fichier source d'origine.",
        "",
        "| Table | Colonne | Description | Remarque |",
        "|---|---|---|---|",
    ]
    out += [f"| {cell(t)} | `{cell(r)}` | {cell(d)} | {cell(s)} |" for t, r, d, s in desc]
    return "\n".join(out) + "\n"


def main() -> None:
    try:
        text = build()
    except duckdb.Error as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(PROJECT_ROOT)} écrit ({text.count(chr(10))} lignes)")


if __name__ == "__main__":
    main()