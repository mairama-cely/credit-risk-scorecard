"""Phase 3a — Découpage train / validation / test (70 / 15 / 15), stratifié sur TARGET.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/make_splits.py

D14 : deux train_test_split successifs de scikit-learn (70 % / 30 %, puis 50 / 50 du reste),
      stratifiés sur TARGET, random_state = 42. Affectation persistée dans DuckDB (table
      split_assignment, 1 ligne par SK_ID_CURR) et dans data/interim/split_assignment.parquet.
D15 : test scellé. load_split() refuse le test sauf allow_test=True (réservé à la Phase 4).
      L'empreinte SHA-256 de la liste triée des SK_ID_CURR de chaque échantillon est enregistrée
      (table split_meta). Si une relance produit un test différent de celui déjà enregistré, le
      script s'arrête sans rien modifier.

Contrôles bloquants (dans une transaction, annulée en cas d'échec) :
- les trois échantillons couvrent exactement model_table_train, sans doublon ni recouvrement ;
- tailles à ±1 ligne des proportions 70 / 15 / 15 ;
- taux de défaut de chaque échantillon à moins de 0,1 point du taux global.
Seuls des comptages de TARGET par échantillon sont calculés sur la validation et le test
(contrôle de la stratification) : aucune variable n'y est lue, aucune analyse n'y est faite.

Aussi importé par les scripts et notebooks suivants : load_split(con, name, columns, allow_test).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, INTERIM_DIR, PROJECT_ROOT, ensure_dirs  # noqa: E402

RANDOM_STATE = 42
SHARE_TRAIN = 0.70          # le reste (30 %) est coupé en deux moitiés : validation et test
SPLITS = ("train", "valid", "test")
EXPECTED_SHARE = {"train": 0.70, "valid": 0.15, "test": 0.15}
MAX_RATE_GAP_PT = 0.1       # écart maximal toléré, en points, entre taux de défaut
OUT_PARQUET = INTERIM_DIR / "split_assignment.parquet"


class SplitError(RuntimeError):
    """Échec d'un contrôle du découpage."""


def fingerprint(ids) -> str:
    """Empreinte SHA-256 de la liste triée des identifiants."""
    data = "\n".join(str(int(i)) for i in sorted(ids)).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()[0] > 0


def load_split(
    con: duckdb.DuckDBPyConnection,
    name: str,
    columns: list[str] | None = None,
    allow_test: bool = False,
) -> pd.DataFrame:
    """Lignes de model_table_train appartenant à un échantillon, triées par SK_ID_CURR.

    Le test est scellé (D15) : il n'est renvoyé qu'avec allow_test=True (Phase 4).
    """
    if name not in SPLITS:
        raise ValueError(f"Échantillon inconnu : {name!r} (attendus : {SPLITS})")
    if name == "test" and not allow_test:
        raise PermissionError(
            "Échantillon de test scellé (D15) : ouverture réservée à la Phase 4 (allow_test=True)."
        )
    cols = "m.*" if columns is None else ", ".join(f'm."{c}"' for c in columns)
    return con.execute(
        f"SELECT {cols} FROM model_table_train m "
        "JOIN split_assignment s USING (SK_ID_CURR) "
        "WHERE s.split = ? ORDER BY m.SK_ID_CURR",
        [name],
    ).df()


def compute_assignment(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Affectation de chaque SK_ID_CURR à train / valid / test (D14)."""
    df = con.execute("SELECT SK_ID_CURR, TARGET FROM model_table_train ORDER BY SK_ID_CURR").df()
    ids = df["SK_ID_CURR"].to_numpy()
    y = df["TARGET"].to_numpy()
    id_train, id_rest, _, y_rest = train_test_split(
        ids, y, train_size=SHARE_TRAIN, stratify=y, random_state=RANDOM_STATE
    )
    id_valid, id_test = train_test_split(
        id_rest, test_size=0.5, stratify=y_rest, random_state=RANDOM_STATE
    )
    parts = [
        pd.DataFrame({"SK_ID_CURR": id_train, "split": "train"}),
        pd.DataFrame({"SK_ID_CURR": id_valid, "split": "valid"}),
        pd.DataFrame({"SK_ID_CURR": id_test, "split": "test"}),
    ]
    return pd.concat(parts, ignore_index=True).sort_values("SK_ID_CURR", ignore_index=True)


def split_summary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Effectif, nombre de défauts et taux de défaut par échantillon (comptages seulement)."""
    return con.execute(
        """
        SELECT s.split,
               COUNT(*)                         AS n_rows,
               CAST(SUM(m.TARGET) AS BIGINT)    AS n_default,
               100.0 * AVG(m.TARGET)            AS default_rate_pct
        FROM split_assignment s
        JOIN model_table_train m USING (SK_ID_CURR)
        GROUP BY s.split
        ORDER BY CASE s.split WHEN 'train' THEN 1 WHEN 'valid' THEN 2 ELSE 3 END
        """
    ).df()


def run_checks(con: duckdb.DuckDBPyConnection, summary: pd.DataFrame) -> pd.DataFrame:
    """Contrôles bloquants du découpage ; renvoie (contrôle, résultat, ok)."""
    res = []

    def add(name: str, result: str, ok: bool) -> None:
        res.append({"controle": name, "resultat": result, "ok": ok})

    n_model, rate_global = con.execute(
        "SELECT COUNT(*), 100.0 * AVG(TARGET) FROM model_table_train"
    ).fetchone()
    n_assign, n_distinct = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT SK_ID_CURR) FROM split_assignment"
    ).fetchone()
    n_unmatched = con.execute(
        "SELECT COUNT(*) FROM split_assignment s "
        "LEFT JOIN model_table_train m USING (SK_ID_CURR) WHERE m.SK_ID_CURR IS NULL"
    ).fetchone()[0]

    add("Couverture : lignes affectées = model_table_train", f"{n_assign:,} / {n_model:,}", n_assign == n_model)
    add("Aucun doublon ni recouvrement entre échantillons", f"{n_distinct:,} identifiants distincts", n_distinct == n_assign)
    add("Tous les identifiants existent dans model_table_train", f"{n_unmatched} orphelin(s)", n_unmatched == 0)

    for row in summary.itertuples():
        expected = EXPECTED_SHARE[row.split] * n_model
        add(f"Taille {row.split} ≈ {EXPECTED_SHARE[row.split]:.0%}",
            f"{row.n_rows:,} (attendu ≈ {expected:,.1f})", abs(row.n_rows - expected) <= 1)
        gap = abs(row.default_rate_pct - rate_global)
        add(f"Taux de défaut {row.split} (global {rate_global:.2f} %)",
            f"{row.default_rate_pct:.2f} % (écart {gap:.3f} pt)", gap < MAX_RATE_GAP_PT)
    return pd.DataFrame(res)


def main() -> None:
    ensure_dirs()
    if not DB_PATH.exists():
        print(f"[ERREUR] {DB_PATH} introuvable.", file=sys.stderr)
        sys.exit(1)
    try:
        with duckdb.connect(str(DB_PATH)) as con:
            if not table_exists(con, "model_table_train"):
                raise SplitError("model_table_train absente : lancer d'abord scripts/build_features.py")

            previous = {}
            if table_exists(con, "split_meta"):
                previous = dict(con.execute("SELECT split, ids_sha256 FROM split_meta").fetchall())

            assignment = compute_assignment(con)
            new_fp = {s: fingerprint(assignment.loc[assignment["split"] == s, "SK_ID_CURR"]) for s in SPLITS}

            if previous and previous.get("test") != new_fp["test"]:
                raise SplitError(
                    "Le test scellé a changé par rapport au découpage enregistré "
                    f"({previous.get('test')} ≠ {new_fp['test']}) : aucun changement appliqué."
                )

            con.execute("BEGIN TRANSACTION")
            try:
                con.register("assignment_df", assignment)
                con.execute(
                    "CREATE OR REPLACE TABLE split_assignment AS "
                    "SELECT CAST(SK_ID_CURR AS BIGINT) AS SK_ID_CURR, CAST(split AS VARCHAR) AS split "
                    "FROM assignment_df ORDER BY SK_ID_CURR"
                )
                con.unregister("assignment_df")

                summary = split_summary(con)
                checks = run_checks(con, summary)
                print("--- Contrôles du découpage")
                print(checks.to_string(index=False))
                if not checks["ok"].all():
                    raise SplitError("contrôle(s) en échec : " + " ; ".join(checks.loc[~checks["ok"], "controle"]))

                meta = summary.assign(
                    ids_sha256=summary["split"].map(new_fp),
                    random_state=RANDOM_STATE,
                )
                con.register("meta_df", meta)
                con.execute("CREATE OR REPLACE TABLE split_meta AS SELECT * FROM meta_df")
                con.unregister("meta_df")
            except BaseException:
                con.execute("ROLLBACK")
                print("[transaction] annulée : la base est inchangée.", file=sys.stderr)
                raise
            con.execute("COMMIT")

            literal = OUT_PARQUET.as_posix().replace("'", "''")
            con.execute(f"COPY (SELECT * FROM split_assignment ORDER BY SK_ID_CURR) TO '{literal}' (FORMAT parquet)")

            print("\n--- Échantillons")
            print(summary.to_string(index=False, formatters={"default_rate_pct": "{:.2f}".format}))
            print("\n--- Empreintes SHA-256 des identifiants (D15)")
            for s in SPLITS:
                print(f"{s:<6} {new_fp[s]}")
            if previous:
                print("\n[D15] Test identique au découpage déjà enregistré : scellé intact.")
            else:
                print("\n[D15] Premier découpage : empreintes enregistrées dans split_meta.")
            print(f"[parquet] {OUT_PARQUET.relative_to(PROJECT_ROOT)}")
    except (SplitError, duckdb.Error, OSError) as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()