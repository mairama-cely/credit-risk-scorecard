"""Phase 1 — Chargement des 9 CSV dans DuckDB (database/credit_risk.duckdb).

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/load_to_database.py

- Une table par CSV : nom du fichier en minuscules, sans .csv.
- Gros fichiers lus par DuckDB (read_csv, typage sur le fichier entier, mode strict :
  une ligne tronquée ou mal formée fait échouer le chargement).
- Dictionnaire des colonnes : encodage détecté (UTF-8, puis cp1252, puis latin-1).
- CREATE OR REPLACE : relancer le script remplace les tables, sans duplication.
- Intégrité : lignes physiques du CSV (hors en-tête) comparées aux lignes chargées ;
  résultat enregistré dans la table meta_load_log.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    COLUMNS_DESCRIPTION_FILE,
    COLUMNS_DESCRIPTION_TABLE,
    DB_PATH,
    ENCODINGS_TO_TRY,
    RAW_DIR,
    TABLES,
    ensure_dirs,
)
from verify_raw_data import verify  # noqa: E402


def count_lines(path: Path, chunk: int = 64 * 1024**2) -> tuple[int, bool]:
    """Nombre de sauts de ligne et présence d'un saut de ligne final."""
    n, last = 0, b""
    with path.open("rb") as f:
        while block := f.read(chunk):
            n += block.count(b"\n")
            last = block[-1:]
    return n, last == b"\n"


def read_description() -> tuple[pd.DataFrame, str]:
    raw = (RAW_DIR / COLUMNS_DESCRIPTION_FILE).read_bytes()
    for enc in ENCODINGS_TO_TRY:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        df = pd.read_csv(io.StringIO(text))
        df = df.loc[:, ~df.columns.str.startswith("Unnamed")]  # colonne d'index sans nom
        return df, enc
    raise UnicodeDecodeError("multi", raw, 0, 1, f"aucun encodage parmi {ENCODINGS_TO_TRY}")


def load() -> pd.DataFrame:
    ensure_dirs()
    verify()
    print()
    log = []
    with duckdb.connect(str(DB_PATH)) as con:
        for table, csv_name in TABLES.items():
            path = RAW_DIR / csv_name
            t0 = time.perf_counter()
            if table == COLUMNS_DESCRIPTION_TABLE:
                desc, encoding = read_description()
                con.register("desc_df", desc)
                con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM desc_df")
                con.unregister("desc_df")
            else:
                encoding = "utf-8"
                con.execute(
                    f"CREATE OR REPLACE TABLE {table} AS "
                    "SELECT * FROM read_csv(?, header = true, sample_size = -1, strict_mode = true)",
                    [path.as_posix()],
                )
            n_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            n_cols = len(con.execute(f"DESCRIBE {table}").fetchall())
            n_newlines, final_newline = count_lines(path)
            data_lines = n_newlines - 1 if final_newline else n_newlines  # hors en-tête
            log.append(
                {
                    "table_name": table,
                    "csv_file": csv_name,
                    "size_mb": round(path.stat().st_size / 1024**2, 1),
                    "encoding": encoding,
                    "csv_data_lines": data_lines,
                    "n_rows": n_rows,
                    "n_cols": n_cols,
                    "ends_with_newline": final_newline,
                    "lines_match": data_lines == n_rows,
                }
            )
            print(f"[load] {table:<32} {n_rows:>12,} lignes × {n_cols:>3} col.  ({time.perf_counter() - t0:5.1f} s)")

        log_df = pd.DataFrame(log)
        con.register("log_df", log_df)
        con.execute("CREATE OR REPLACE TABLE meta_load_log AS SELECT * FROM log_df")
        con.unregister("log_df")
    return log_df


def main() -> None:
    try:
        log_df = load()
    except (FileNotFoundError, duckdb.Error, UnicodeDecodeError) as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    print()
    print(log_df[["table_name", "n_rows", "n_cols", "csv_data_lines", "lines_match"]].to_string(index=False))
    if not log_df["lines_match"].all():
        print("\n[ATTENTION] Écart lignes CSV / lignes chargées : voir meta_load_log.", file=sys.stderr)
    print(f"\nBase : {DB_PATH}")


if __name__ == "__main__":
    main()