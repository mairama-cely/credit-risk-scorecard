"""Phase 1 — Exécution de database/00_quality_checks.sql sur la base DuckDB (lecture seule).

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/run_quality_checks.py

Aussi importé par notebooks/00_Data_Audit.ipynb et scripts/build_metadata.py :
run_checks() renvoie {nom de la requête: DataFrame} ; parse_checks() renvoie les requêtes.
Aucun fichier n'est écrit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, SQL_DIR  # noqa: E402

CHECKS_FILE = SQL_DIR / "00_quality_checks.sql"


def parse_checks(path: Path = CHECKS_FILE) -> dict[str, str]:
    """Découpe le fichier SQL en requêtes nommées par « -- name: <nom> »."""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^--\s*name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    return {name: sql.strip().rstrip(";") for name, sql in zip(blocks[1::2], blocks[2::2])}


def run_checks(con: duckdb.DuckDBPyConnection | None = None) -> dict[str, pd.DataFrame]:
    own = con is None
    if own:
        if not DB_PATH.exists():
            raise FileNotFoundError(f"{DB_PATH} introuvable : lancer d'abord scripts/load_to_database.py")
        con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return {name: con.execute(sql).df() for name, sql in parse_checks().items()}
    finally:
        if own:
            con.close()


def main() -> None:
    # Les libellés contiennent des caractères absents de l'encodage Windows par défaut (cp1252),
    # par exemple « ∩ » : on force l'UTF-8 pour que l'affichage ne plante pas quand la sortie
    # est redirigée (Select-Object, fichier).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        results = run_checks()
    except (FileNotFoundError, duckdb.Error) as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        for name, df in results.items():
            print(f"\n--- {name}")
            print(df.to_string(index=False))


if __name__ == "__main__":
    main()