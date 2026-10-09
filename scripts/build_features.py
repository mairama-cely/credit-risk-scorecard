"""Phase 2 — Construction de la table de modélisation (1 ligne = 1 SK_ID_CURR) dans DuckDB.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/build_features.py

1. Contrôle préalable : compte la valeur 365243 dans toutes les colonnes DAYS_* des tables
   brutes et vérifie que seules ces colonnes sont traitées comme sentinelles en SQL.
2. Exécute database/01 … 06 puis database/10 dans l'ordre (CREATE OR REPLACE : relance sans
   duplication) et journalise durée et nombre de lignes.
3. Contrôles bloquants : lignes = volumes de la Phase 1 (meta_load_log), SK_ID_CURR unique,
   TARGET (présente, sans NULL, valeurs 0 ou 1, absente du test), infinis / NaN, sentinelles
   restantes. Tous les contrôles sont exécutés et affichés ; arrêt si au moins un échoue.
4. Export Parquet : data/processed/model_table_{train,test}.parquet.
5. Nombre de variables par préfixe, comparé au nombre validé (D13 amendé le 29/09 : 86) ;
   tout écart est signalé, pour détecter une variable perdue ou ajoutée involontairement.

Les étapes 2 et 3 s'exécutent dans une seule transaction : si un fichier SQL ou un contrôle
bloquant échoue, la transaction est annulée et la base reste dans son état antérieur (aucune
table partiellement reconstruite, aucune table en échec conservée). L'export Parquet n'a lieu
qu'après validation.

Reproductibilité exacte : les étapes 2 et 3 tournent avec SET threads = 1. En parallèle, l'ordre
des additions des SUM / AVG sur des DOUBLE varie d'une exécution à l'autre et change le dernier
bit de certains agrégats ; en mono-thread, deux exécutions donnent des tables identiques au bit
près. Le réglage d'origine est rétabli ensuite, y compris en cas d'échec.

Aussi importé par notebooks/01_Feature_Engineering.ipynb (sentinel_scan, blocking_checks,
count_by_prefix), sur une connexion en lecture seule.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, PROCESSED_DIR, SQL_DIR, ensure_dirs  # noqa: E402

SENTINEL = 365243

# D13 amendé le 29/09 : nombre de variables créées validé après revue
VALIDATED_CREATED = 86

RAW_TABLES = [
    "application_train",
    "application_test",
    "bureau",
    "bureau_balance",
    "previous_application",
    "pos_cash_balance",
    "installments_payments",
    "credit_card_balance",
]

# Fichier SQL -> tables qu'il crée (ordre d'exécution)
SQL_STEPS = [
    ("01_application_features.sql", ["application_all"]),
    ("02_bureau_features.sql", ["feat_bureau_balance_credit", "feat_bureau"]),
    ("03_previous_application_features.sql", ["previous_application_clean", "feat_previous_application"]),
    ("04_installments_features.sql", ["feat_installments"]),
    ("05_pos_cash_features.sql", ["feat_pos_cash"]),
    ("06_credit_card_features.sql", ["feat_credit_card"]),
    ("10_model_table.sql", ["model_table_train", "model_table_test"]),
]

# Colonnes traitées comme sentinelles en SQL : table brute -> (colonne, table(s) nettoyée(s))
TREATED_SENTINELS = {
    ("application_train", "DAYS_EMPLOYED"): ["application_all", "model_table_train"],
    ("application_test", "DAYS_EMPLOYED"): ["application_all", "model_table_test"],
    ("previous_application", "DAYS_FIRST_DRAWING"): ["previous_application_clean"],
    ("previous_application", "DAYS_FIRST_DUE"): ["previous_application_clean"],
    ("previous_application", "DAYS_LAST_DUE_1ST_VERSION"): ["previous_application_clean"],
    ("previous_application", "DAYS_LAST_DUE"): ["previous_application_clean"],
    ("previous_application", "DAYS_TERMINATION"): ["previous_application_clean"],
}

PREFIXES = ["APP_", "BUR_", "BB_", "PREV_", "INS_", "POS_", "CC_", "HAS_"]
MODEL_TABLES = {"model_table_train": "application_train", "model_table_test": "application_test"}


class CheckError(RuntimeError):
    """Échec d'un contrôle bloquant."""


def columns(con: duckdb.DuckDBPyConnection, table: str) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in con.execute(f"DESCRIBE {table}").fetchall()]


def sentinel_scan(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Occurrences de 365243 dans chaque colonne DAYS_* des tables brutes."""
    rows = []
    for table in RAW_TABLES:
        for col, _ in columns(con, table):
            if not col.startswith("DAYS_"):
                continue
            n, n_rows = con.execute(
                f"SELECT COUNT(*) FILTER (WHERE {col} = {SENTINEL}), COUNT(*) FROM {table}"
            ).fetchone()
            rows.append(
                {
                    "table_name": table,
                    "colonne": col,
                    "n_365243": n,
                    "pct_lignes": round(100 * n / n_rows, 2),
                    "traitee_en_sql": (table, col) in TREATED_SENTINELS,
                }
            )
    return pd.DataFrame(rows)


def check_sentinel_scope(scan: pd.DataFrame) -> None:
    """Seules les colonnes où 365243 apparaît sont traitées, et toutes le sont."""
    found = {(r.table_name, r.colonne) for r in scan.itertuples() if r.n_365243 > 0}
    if found != set(TREATED_SENTINELS):
        raise CheckError(
            f"Sentinelles : colonnes observées {sorted(found)} ≠ colonnes traitées {sorted(TREATED_SENTINELS)}"
        )


def run_sql(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Exécute les fichiers SQL dans l'ordre ; durée par fichier, volumes par table créée."""
    log = []
    for sql_file, tables in SQL_STEPS:
        t0 = time.perf_counter()
        con.execute((SQL_DIR / sql_file).read_text(encoding="utf-8"))
        seconds = time.perf_counter() - t0
        print(f"[sql] {sql_file:<40} ({seconds:5.1f} s)")
        for table in tables:
            n_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            n_cols = len(columns(con, table))
            log.append({"fichier": sql_file, "secondes_fichier": round(seconds, 1),
                        "table_name": table, "n_rows": n_rows, "n_cols": n_cols})
            print(f"        {table:<28} {n_rows:>10,} lignes × {n_cols:>3} col.")
    return pd.DataFrame(log)


def blocking_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Contrôles bloquants de la table modèle ; renvoie un DataFrame (contrôle, résultat, ok)."""
    expected = dict(con.execute("SELECT table_name, n_rows FROM meta_load_log").fetchall())
    res = []

    def add(name: str, result: str, ok: bool) -> None:
        res.append({"controle": name, "resultat": result, "ok": ok})

    for table, source in MODEL_TABLES.items():
        n_rows, n_ids = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT SK_ID_CURR) FROM {table}").fetchone()
        add(f"{table} : lignes = {source} (Phase 1)", f"{n_rows:,} / {expected[source]:,} attendues", n_rows == expected[source])
        add(f"{table} : SK_ID_CURR unique", f"{n_ids:,} distincts / {n_rows:,} lignes", n_ids == n_rows)

    train_cols = [c for c, _ in columns(con, "model_table_train")]
    test_cols = [c for c, _ in columns(con, "model_table_test")]
    n_null = con.execute("SELECT COUNT(*) FILTER (WHERE TARGET IS NULL) FROM model_table_train").fetchone()[0] \
        if "TARGET" in train_cols else None
    add("TARGET présente et sans NULL (train)", f"présente : {'TARGET' in train_cols}, NULL : {n_null}",
        "TARGET" in train_cols and n_null == 0)
    n_other = con.execute("SELECT COUNT(*) FILTER (WHERE TARGET NOT IN (0, 1)) FROM model_table_train").fetchone()[0] \
        if "TARGET" in train_cols else None
    add("TARGET ∈ {0, 1} (train)", f"{n_other} valeur(s) hors {{0, 1}}", n_other == 0)
    add("TARGET absente (test)", f"présente : {'TARGET' in test_cols}", "TARGET" not in test_cols)

    for table in MODEL_TABLES:
        floats = [c for c, t in columns(con, table) if t in ("DOUBLE", "FLOAT", "REAL")]
        n_bad = 0
        if floats:  # sans colonne décimale, aucune valeur infinie ni NaN possible
            expr = " + ".join(f"COUNT(*) FILTER (WHERE isinf({c}) OR isnan({c}))" for c in floats)
            n_bad = con.execute(f"SELECT {expr} FROM {table}").fetchone()[0]
        add(f"{table} : aucune valeur infinie ni NaN ({len(floats)} colonnes décimales)", f"{n_bad} valeur(s)", n_bad == 0)

    for (_, col), cleaned in TREATED_SENTINELS.items():
        for table in cleaned:
            n = con.execute(f"SELECT COUNT(*) FILTER (WHERE {col} = {SENTINEL}) FROM {table}").fetchone()[0]
            name = f"{table}.{col} : aucune valeur {SENTINEL} restante"
            if name not in {r["controle"] for r in res}:
                add(name, f"{n} valeur(s)", n == 0)
    return pd.DataFrame(res)


def count_by_prefix(con: duckdb.DuckDBPyConnection, table: str = "model_table_train") -> pd.DataFrame:
    cols = [c for c, _ in columns(con, table)]
    rows = [{"famille": p, "n_variables": sum(c.startswith(p) for c in cols)} for p in PREFIXES]
    created = sum(r["n_variables"] for r in rows)
    special = [c for c in ("SK_ID_CURR", "TARGET") if c in cols]
    rows.append({"famille": "total créées", "n_variables": created})
    rows.append({"famille": "brutes (application)", "n_variables": len(cols) - created - len(special)})
    rows.append({"famille": "identifiant / cible", "n_variables": len(special)})
    rows.append({"famille": "total colonnes", "n_variables": len(cols)})
    return pd.DataFrame(rows)


def export_parquet(con: duckdb.DuckDBPyConnection) -> None:
    for table in MODEL_TABLES:
        path = PROCESSED_DIR / f"{table}.parquet"
        literal = path.as_posix().replace("'", "''")  # apostrophe doublée dans le littéral SQL
        con.execute(f"COPY {table} TO '{literal}' (FORMAT parquet)")
        print(f"[parquet] {path.relative_to(PROCESSED_DIR.parents[1])}  ({path.stat().st_size / 1024**2:.1f} Mo)")


def main() -> None:
    ensure_dirs()
    if not DB_PATH.exists():
        print(f"[ERREUR] {DB_PATH} introuvable : lancer d'abord scripts/load_to_database.py", file=sys.stderr)
        sys.exit(1)
    try:
        with duckdb.connect(str(DB_PATH)) as con:
            scan = sentinel_scan(con)
            print("--- Contrôle préalable des sentinelles (365243 dans les DAYS_*)")
            print(scan.to_string(index=False))
            check_sentinel_scope(scan)
            print()
            default_threads = con.execute("SELECT current_setting('threads')").fetchone()[0]
            con.execute("SET threads = 1")  # reproductibilité exacte des agrégats décimaux
            print(f"[threads] construction en mono-thread (réglage d'origine : {default_threads})")
            t0 = time.perf_counter()
            try:
                con.execute("BEGIN TRANSACTION")
                try:
                    run_sql(con)
                    print("\n--- Contrôles bloquants")
                    checks = blocking_checks(con)
                    print(checks.to_string(index=False))
                    if not checks["ok"].all():
                        raise CheckError("contrôle(s) en échec : " + " ; ".join(checks.loc[~checks["ok"], "controle"]))
                except BaseException:
                    con.execute("ROLLBACK")
                    print("[transaction] annulée : la base est inchangée.", file=sys.stderr)
                    raise
                con.execute("COMMIT")
            finally:
                con.execute(f"SET threads = {int(default_threads)}")
            print(f"[transaction] validée. Durée totale de la construction (SQL + contrôles) : "
                  f"{time.perf_counter() - t0:.1f} s ; threads rétablis à {default_threads}.\n")
            export_parquet(con)
            print("\n--- Variables par famille (model_table_train)")
            by_prefix = count_by_prefix(con)
            print(by_prefix.to_string(index=False))
            created = int(by_prefix.loc[by_prefix["famille"] == "total créées", "n_variables"].iloc[0])
            if created == VALIDATED_CREATED:
                print(f"\n[D13] {created} variables créées : conforme au nombre validé.")
            else:
                print(f"\n[ATTENTION D13] {created} variables créées au lieu des {VALIDATED_CREATED} validées : "
                      "mettre à jour build_feature_catalog.py et le cahier des charges.")
    except (CheckError, duckdb.Error, OSError) as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()