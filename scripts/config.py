"""Chemins et constantes partagés par tous les scripts et notebooks.

Structure alignée sur le projet réfugiés du portfolio :
- data/raw, data/interim, data/processed, data/final ;
- database/ : base DuckDB (non versionnée) et fichiers SQL (versionnés) ;
- output/ : figures préfixées par le numéro du notebook qui les produit (NN_nom.png),
  et output/tables/ pour les tableaux CSV ;
- docs/ : cahier des charges et rapports ;
- models/, powerbi_data/, tests/, deployment/.
"""
from pathlib import Path

# Racine du projet = dossier parent de scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
FINAL_DIR = DATA_DIR / "final"

DB_DIR = PROJECT_ROOT / "database"
DB_PATH = DB_DIR / "credit_risk.duckdb"
SQL_DIR = DB_DIR  # fichiers SQL versionnés à côté de la base

OUTPUT_DIR = PROJECT_ROOT / "output"
FIGURES_DIR = OUTPUT_DIR  # figures à la racine de output/, nommées NN_nom.png
TABLES_DIR = OUTPUT_DIR / "tables"

DOCS_DIR = PROJECT_ROOT / "docs"
MODELS_DIR = PROJECT_ROOT / "models"
POWERBI_DIR = PROJECT_ROOT / "powerbi_data"

# Les 9 CSV attendus (noms exacts, casse comprise) -> nom de la table DuckDB
# (nom de fichier en minuscules, sans .csv).
EXPECTED_CSV = [
    "application_train.csv",
    "application_test.csv",
    "bureau.csv",
    "bureau_balance.csv",
    "previous_application.csv",
    "POS_CASH_balance.csv",
    "credit_card_balance.csv",
    "installments_payments.csv",
    "HomeCredit_columns_description.csv",
]
TABLES = {Path(f).stem.lower(): f for f in EXPECTED_CSV}

# Dictionnaire des colonnes : encodage non UTF-8, chargé à part (petit fichier)
COLUMNS_DESCRIPTION_FILE = "HomeCredit_columns_description.csv"
COLUMNS_DESCRIPTION_TABLE = "homecredit_columns_description"
ENCODINGS_TO_TRY = ("utf-8", "cp1252", "latin-1")

RANDOM_STATE = 42


def ensure_dirs() -> None:
    for d in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, FINAL_DIR, DB_DIR, OUTPUT_DIR, TABLES_DIR,
              DOCS_DIR, MODELS_DIR, POWERBI_DIR):
        d.mkdir(parents=True, exist_ok=True)