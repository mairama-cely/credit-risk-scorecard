"""Phase 5 — Export des tables Power BI (schéma en étoile) dans powerbi_data/.

Usage (depuis la racine du projet, après scripts/build_cutoff_strategy.py) :
    .venv\\Scripts\\python.exe scripts/export_to_powerbi.py

Entrées (aucun recalcul de modèle) :
- models/all_scores.parquet : scores, PD, décile, motifs de refus de chaque demande (train / valid / test) ;
- output/tables/*.csv|json : tables produites aux Phases 3 et 4 ;
- database/credit_risk.duckdb (lecture seule) : attributs descriptifs des demandeurs (model_table_train).
  Le test a déjà été ouvert et évalué (D15, Phase 4) : on n'en relit ici que des attributs descriptifs
  pour la segmentation, aucun modèle ni seuil n'est ajusté.

Format des CSV (documenté dans docs/powerbi_guide.md) :
- encodage UTF-8 avec BOM (utf-8-sig, lu sans erreur d'accent par Power Query sous Windows) ;
- séparateur de colonnes « , » ; séparateur décimal « . » (paramètres régionaux « Anglais (États-Unis) »
  à choisir dans Power Query sur un poste en français) ; pas de séparateur de milliers ;
- booléens en 0/1 ; valeurs manquantes = cellule vide.
Volume : environ 90 Mo au total (deux tables de 307 511 lignes) ; powerbi_data/ n'est pas versionné
(.gitignore) et se régénère avec ce script.

Tables écrites :
    fact_applications   une ligne par demande (train / valid / test) — table de faits
    dim_applicant       attributs de segmentation (1:1 avec fact_applications)
    dim_split           3 échantillons (train / valid / test) avec libellé et ordre
    dim_score_band      10 tranches de score (bornes = déciles du score du train)
    dim_scenario        3 scénarios de seuil (table déconnectée, sert de segment)
    scenario_results    indicateurs de chaque scénario par échantillon et LGD (cutoff_scenarios)
    model_comparison    AUC / Gini / KS / Brier par modèle et échantillon, IC bootstrap du test
    scorecard_points    grille de score : points par classe de chaque variable
    shap_importance     importance SHAP du challenger LightGBM
    fairness            audit d'équité par genre (test, scénario recommandé)
    calibration         PD prédite vs taux observé par décile (test)
    psi                 indice de stabilité de la population (score et variables)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, MODELS_DIR, POWERBI_DIR, TABLES_DIR, ensure_dirs  # noqa: E402

LGD = 0.45                      # LGD de base (cutoff_strategy.json, lgd_base) — vérifiée ci-dessous
ENCODING = "utf-8-sig"
SEP = ","

ALL_SCORES = MODELS_DIR / "all_scores.parquet"
CUTOFF_JSON = TABLES_DIR / "cutoff_strategy.json"
EVAL_JSON = TABLES_DIR / "evaluation_metrics.json"

SPLIT_LABELS = {"train": "Apprentissage", "valid": "Validation", "test": "Test"}
MODEL_LABELS = {"scorecard": "Grille de score", "lgbm": "LightGBM", "lgbm_no_ext": "LightGBM sans EXT_SOURCE"}
SCENARIO_LABELS = {"prudent": "Prudent", "equilibre": "Équilibré", "croissance": "Croissance"}
DECISION_LABELS = {"accepter": "Accepter", "revoir": "Revoir", "refuser": "Refuser"}

# Classes de risque (regroupement des déciles de score : 10 = meilleur score)
GRADES = {10: "A", 9: "A", 8: "B", 7: "B", 6: "C", 5: "C", 4: "D", 3: "D", 2: "E", 1: "E"}
GRADE_LABELS = {"A": "A – Très faible", "B": "B – Faible", "C": "C – Modéré", "D": "D – Élevé", "E": "E – Très élevé"}

APPLICANT_COLS = [
    "SK_ID_CURR", "CODE_GENDER", "NAME_CONTRACT_TYPE", "NAME_INCOME_TYPE", "NAME_EDUCATION_TYPE",
    "NAME_FAMILY_STATUS", "OCCUPATION_TYPE", "ORGANIZATION_TYPE", "REGION_RATING_CLIENT_W_CITY",
    "AMT_INCOME_TOTAL", "APP_AGE_YEARS",
]
AGE_BINS, AGE_LABELS = [0, 30, 40, 50, 60, np.inf], ["20-29 ans", "30-39 ans", "40-49 ans", "50-59 ans", "60 ans et +"]
INCOME_BINS = [0, 100_000, 150_000, 200_000, 300_000, np.inf]
INCOME_LABELS = ["< 100 k", "100-150 k", "150-200 k", "200-300 k", ">= 300 k"]
CREDIT_BINS = [0, 250_000, 500_000, 1_000_000, np.inf]
CREDIT_LABELS = ["< 250 k", "250-500 k", "500 k-1 M", ">= 1 M"]


def log(msg: str) -> None:
    print(msg, flush=True)


def _band(x: pd.Series, bins, labels) -> pd.Series:
    return pd.cut(x, bins=bins, labels=labels, right=False).astype("string")


def _band_order(x: pd.Series, bins) -> pd.Series:
    return (pd.cut(x, bins=bins, labels=False, right=False) + 1).astype("Int64")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def build_dim_scenario(st: dict, scen: pd.DataFrame) -> pd.DataFrame:
    test = scen[scen["split"].eq("test") & np.isclose(scen["lgd"], LGD)].set_index("scenario")
    rows = []
    for i, (key, c) in enumerate(st["cutoffs"].items(), start=1):
        t = test.loc[key]
        rows.append({
            "scenario_key": key, "scenario": SCENARIO_LABELS[key], "sort_order": i,
            "target_approval": c["target_approval"], "cutoff": c["cutoff"],
            "review_low": c["cutoff"] - st["review_half_width_points"],
            "review_high": c["cutoff"] + st["review_half_width_points"],
            "recommended": int(key == st["recommended"]),
            "criterion_valid": st["recommendation_criterion_valid"][key],
            "test_approval_rate": t["approval_rate"], "test_bad_rate_accepted": t["bad_rate_accepted"],
            "test_good_refused_pct": t["good_refused_pct"], "test_el_accepted": t["el_accepted"],
            "test_el_avoided": t["el_avoided"], "test_el_avoided_pct": t["el_avoided_pct"],
            "test_zone_review_pct": t["zone_review_pct"], "test_breakeven_margin": t["breakeven_margin"],
        })
    return pd.DataFrame(rows)


def build_fact(scores: pd.DataFrame, dim_scenario: pd.DataFrame, half_width: int) -> pd.DataFrame:
    f = scores[["SK_ID_CURR", "split", "score", "pd_scorecard", "pd_lgbm", "decile", "TARGET", "AMT_CREDIT"]].copy()
    f = f.rename(columns={"decile": "score_band"})
    f["expected_loss"] = f["pd_scorecard"] * LGD * f["AMT_CREDIT"]
    s = f["score"].to_numpy()
    for _, r in dim_scenario.iterrows():
        k, c = r["scenario_key"], int(r["cutoff"])
        f[f"approved_{k}"] = (s >= c).astype(int)               # décision binaire (base des indicateurs)
        f[f"decision_{k}"] = np.where(s >= c + half_width, DECISION_LABELS["accepter"],
                                      np.where(s >= c - half_width, DECISION_LABELS["revoir"],
                                               DECISION_LABELS["refuser"]))
    for j in (1, 2, 3):
        f[f"reason_{j}"] = scores[f"reason_{j}"].replace("", pd.NA)
    # Arrondis (taille des CSV) : PD à 6 décimales, montants au centime
    return f.round({"pd_scorecard": 6, "pd_lgbm": 6, "AMT_CREDIT": 2, "expected_loss": 2})


def build_dim_applicant(con: duckdb.DuckDBPyConnection, ids: pd.Series, amt_credit: pd.DataFrame) -> pd.DataFrame:
    cols = ", ".join(f'"{c}"' for c in APPLICANT_COLS)
    d = con.execute(f"SELECT {cols} FROM model_table_train ORDER BY SK_ID_CURR").df()
    d = d[d["SK_ID_CURR"].isin(ids)].merge(amt_credit, on="SK_ID_CURR", how="left")
    d["OCCUPATION_TYPE"] = d["OCCUPATION_TYPE"].fillna("Non renseigné")
    d["age_band"] = _band(d["APP_AGE_YEARS"], AGE_BINS, AGE_LABELS)
    d["age_band_order"] = _band_order(d["APP_AGE_YEARS"], AGE_BINS)
    d["income_band"] = _band(d["AMT_INCOME_TOTAL"], INCOME_BINS, INCOME_LABELS)
    d["income_band_order"] = _band_order(d["AMT_INCOME_TOTAL"], INCOME_BINS)
    d["credit_band"] = _band(d["AMT_CREDIT"], CREDIT_BINS, CREDIT_LABELS)
    d["credit_band_order"] = _band_order(d["AMT_CREDIT"], CREDIT_BINS)
    d["APP_AGE_YEARS"] = d["APP_AGE_YEARS"].round(1)
    return d.drop(columns="AMT_CREDIT")


def build_dim_score_band(scores: pd.DataFrame, edges: list[float]) -> pd.DataFrame:
    tr = scores[scores["split"].eq("train")]
    g = tr.groupby("decile").agg(n_train=("TARGET", "size"), default_rate_train=("TARGET", "mean"),
                                 pd_mean_train=("pd_scorecard", "mean"),
                                 score_min_obs=("score", "min"), score_max_obs=("score", "max"))
    rows = []
    for b in range(1, len(edges)):
        lo, hi = edges[b - 1], edges[b]
        lo_i = None if lo <= -1e8 else int(lo)
        hi_i = None if hi >= 1e8 else int(hi)
        if lo_i is None:
            label = f"< {hi_i}"
        elif hi_i is None:
            label = f">= {lo_i}"
        else:
            label = f"{lo_i}-{hi_i - 1}"
        grade = GRADES[b]
        rows.append({"score_band": b, "band_label": f"T{b:02d} ({label})", "score_low": lo_i,
                     "score_high_excl": hi_i, "risk_grade": grade, "risk_grade_label": GRADE_LABELS[grade],
                     **g.loc[b].to_dict()})
    out = pd.DataFrame(rows)
    out["n_train"] = out["n_train"].astype(int)
    out["score_low"] = out["score_low"].astype("Int64")
    out["score_high_excl"] = out["score_high_excl"].astype("Int64")
    out["score_min_obs"] = out["score_min_obs"].astype(int)
    out["score_max_obs"] = out["score_max_obs"].astype(int)
    return out


def build_model_comparison(ev: dict) -> pd.DataFrame:
    comp = pd.read_csv(TABLES_DIR / "final_comparison.csv")
    comp.insert(1, "model_label", comp["model"].map(MODEL_LABELS))
    comp.insert(3, "split_label", comp["split"].map(SPLIT_LABELS))
    comp["split_order"] = comp["split"].map({"train": 1, "valid": 2, "test": 3})
    b = ev["bootstrap"]
    ci = {"scorecard": ("scorecard_auc", "scorecard_gini"), "lgbm": ("lgbm_auc", "lgbm_gini")}
    for col in ("auc_ci_low", "auc_ci_high", "gini_ci_low", "gini_ci_high"):
        comp[col] = np.nan
    for m, (ka, kg) in ci.items():
        msk = comp["model"].eq(m) & comp["split"].eq("test")
        comp.loc[msk, ["auc_ci_low", "auc_ci_high"]] = [b[ka]["low"], b[ka]["high"]]
        comp.loc[msk, ["gini_ci_low", "gini_ci_high"]] = [b[kg]["low"], b[kg]["high"]]
    return comp


def build_scorecard_points() -> pd.DataFrame:
    sc = pd.read_csv(TABLES_DIR / "scorecard_table.csv")
    iv = pd.read_csv(TABLES_DIR / "iv_table.csv").set_index("variable")
    sc.insert(1, "bin_order", sc.groupby("variable").cumcount() + 1)
    sc["var_max_points"] = sc.groupby("variable")["points"].transform("max")
    sc["var_min_points"] = sc.groupby("variable")["points"].transform("min")
    sc["iv"] = sc["variable"].map(iv["iv"])
    sc["var_rank_iv"] = sc["iv"].rank(method="dense", ascending=False).astype(int)
    return sc


def build_shap() -> pd.DataFrame:
    sh = pd.read_csv(TABLES_DIR / "shap_importance.csv")
    sel = json.loads((TABLES_DIR / "scorecard_metrics.json").read_text(encoding="utf-8"))["variables"]
    sh["in_scorecard"] = sh["feature"].isin(sel).astype(int)
    sh["is_ext_source"] = sh["feature"].str.contains("EXT_SOURCE").astype(int)
    return sh


def build_fairness() -> pd.DataFrame:
    fa = pd.read_csv(TABLES_DIR / "fairness_table.csv")
    ref = fa.loc[fa["approval_rate"].idxmax()]
    fa["approval_ratio_vs_max"] = fa["approval_rate"] / ref["approval_rate"]
    fa["approval_ratio_goods_vs_max"] = fa["approval_rate_goods"] / ref["approval_rate_goods"]
    fa["four_fifths_ok"] = (fa["approval_ratio_vs_max"] >= 0.8).astype(int)
    return fa


def build_calibration() -> pd.DataFrame:
    cal = pd.read_csv(TABLES_DIR / "calibration_test.csv")
    cal.insert(1, "model_label", cal["model"].map(MODEL_LABELS))
    return cal


def build_psi() -> pd.DataFrame:
    p = pd.read_csv(TABLES_DIR / "psi_table.csv")
    p["sort_order"] = np.arange(1, len(p) + 1)
    return p


# ---------------------------------------------------------------------------
# Contrôles de cohérence avec les sorties de la Phase 4
# ---------------------------------------------------------------------------
def check_consistency(fact: pd.DataFrame, scen: pd.DataFrame, st: dict) -> None:
    test = fact[fact["split"].eq("test")]
    ref = scen[scen["split"].eq("test") & np.isclose(scen["lgd"], LGD)].set_index("scenario")
    for k in SCENARIO_LABELS:
        appr = test[f"approved_{k}"].mean()
        rev = test[f"decision_{k}"].eq("Revoir").mean()
        el_acc = test.loc[test[f"approved_{k}"].eq(1), "expected_loss"].sum()
        assert np.isclose(appr, ref.loc[k, "approval_rate"]), f"{k} : acceptation {appr} ≠ {ref.loc[k, 'approval_rate']}"
        assert np.isclose(rev, ref.loc[k, "zone_review_pct"]), f"{k} : zone de revue incohérente"
        assert np.isclose(el_acc, ref.loc[k, "el_accepted"], rtol=1e-6), f"{k} : perte attendue acceptée incohérente"
    assert np.isclose(test["expected_loss"].sum(), st["approve_all_test"]["el_all"], rtol=1e-6)
    log("Contrôle : acceptation, zone de revue et perte attendue du test identiques à cutoff_scenarios.csv.")


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------
def write(df: pd.DataFrame, name: str, float_format: str | None = None) -> tuple[str, int, int]:
    path = POWERBI_DIR / f"{name}.csv"
    df.to_csv(path, index=False, sep=SEP, decimal=".", encoding=ENCODING, float_format=float_format,
              lineterminator="\n")
    return name, len(df), path.stat().st_size


def run() -> list[tuple[str, int, int]]:
    ensure_dirs()
    st = json.loads(CUTOFF_JSON.read_text(encoding="utf-8"))
    ev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    if not np.isclose(st["lgd_base"], LGD):
        raise ValueError(f"LGD de base {st['lgd_base']} ≠ {LGD} : mettre à jour LGD.")
    if ev["dry_run"]:
        raise RuntimeError("Sorties de répétition (--dry-run) : relancer evaluate_models.py avant l'export.")
    scores = pd.read_parquet(ALL_SCORES)
    scen = pd.read_csv(TABLES_DIR / "cutoff_scenarios.csv")

    dim_scenario = build_dim_scenario(st, scen)
    fact = build_fact(scores, dim_scenario, st["review_half_width_points"])
    check_consistency(fact, scen, st)  # après arrondi au centime : tolérance relative 1e-6

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        dim_app = build_dim_applicant(con, fact["SK_ID_CURR"], scores[["SK_ID_CURR", "AMT_CREDIT"]])
    finally:
        con.close()
    if len(dim_app) != len(fact) or dim_app["SK_ID_CURR"].duplicated().any():
        raise ValueError("dim_applicant doit contenir exactement une ligne par demande de fact_applications.")

    tables = [
        (fact, "fact_applications", None),
        (dim_app, "dim_applicant", None),
        (pd.DataFrame({"split": list(SPLIT_LABELS), "split_label": list(SPLIT_LABELS.values()),
                       "split_order": [1, 2, 3]}), "dim_split", None),
        (build_dim_score_band(scores, ev["decile_edges"]), "dim_score_band", "%.6f"),
        (dim_scenario, "dim_scenario", "%.6f"),
        (scen, "scenario_results", "%.6f"),
        (build_model_comparison(ev), "model_comparison", "%.6f"),
        (build_scorecard_points(), "scorecard_points", "%.6f"),
        (build_shap(), "shap_importance", "%.6f"),
        (build_fairness(), "fairness", "%.6f"),
        (build_calibration(), "calibration", "%.6f"),
        (build_psi(), "psi", "%.6f"),
    ]
    out = [write(df, name, ff) for df, name, ff in tables]
    total = sum(s for _, _, s in out)
    log(f"\nExport Power BI → {POWERBI_DIR}")
    log(f"{'table':<20} {'lignes':>9} {'taille':>10}")
    for name, n, size in out:
        log(f"{name:<20} {n:>9,} {size / 1e6:>8.2f} Mo")
    log(f"{'total':<20} {'':>9} {total / 1e6:>8.2f} Mo")
    return out


def main() -> None:
    run()


if __name__ == "__main__":
    main()
