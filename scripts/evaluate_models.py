"""Phase 4b — Évaluation finale sur le test scellé : grille de score vs LightGBM.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/evaluate_models.py             # lecture du test (journalisée, D15)
    .venv\\Scripts\\python.exe scripts/evaluate_models.py --dry-run   # répétition : la validation remplace le test

Le test n'est lu qu'ici, par load_split(..., allow_test=True) ; aucune sélection ni réglage n'est fait dessus.
Chaque lecture est journalisée (console, models/test_access_log.csv, evaluation_metrics.json) avec contrôle de l'empreinte SHA-256 des
identifiants contre la table split_meta. Rien n'est ajusté sur le test : modèles figés (Phase 3 et 4a),
calibrage isotone de contrôle et seuils ajustés sur la validation.

Contenu :
- comparaison train / valid / test (AUC, Gini, KS, Brier) pour la grille, LightGBM et LightGBM sans EXT_SOURCE ;
- IC à 95 % par bootstrap (1 000 rééchantillonnages, graine 42) de l'AUC et du Gini de test, et de l'écart
  d'AUC LightGBM − grille (bootstrap apparié : mêmes tirages pour les deux modèles) ;
- calibration sur le test par décile de PD, Brier ; régression isotone ajustée sur la validation si besoin ;
- stabilité : PSI du score (10 tranches = déciles du train) et PSI caractéristique des variables (classes WoE) ;
- équité par CODE_GENDER (exclue du modèle) ; motifs de refus (3 plus grands manques de points).

Les AUC / KS de la grille sont calculés sur le score entier (comme en Phase 3) ; le Brier sur la PD du logit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_cutoff_strategy import recommend, scenario_cutoffs  # noqa: E402
from config import DB_PATH, MODELS_DIR, PROJECT_ROOT, RANDOM_STATE, TABLES_DIR, ensure_dirs  # noqa: E402
from make_splits import fingerprint, load_split  # noqa: E402
from train_challenger import MODEL_NO_EXT_PATH, MODEL_PATH, load_artefacts, predict_frame  # noqa: E402
from train_scorecard import (  # noqa: E402
    SCORECARD_TABLE, load_artifacts, points_from_woe, prepare_X, score_frame, transform_woe,
)

N_BOOT = 1000
PSI_MODERATE, PSI_SEVERE = 0.10, 0.25
CAL_MEAN_GAP_MAX = 0.01     # écart absolu moyen PD − taux observé par décile (1 point)
CAL_MAX_GAP_MAX = 0.03      # écart maximal sur un décile (3 points)
EDGE_SENTINEL = 1e9         # bornes extrêmes des tranches de score (finies pour JSON / Power BI)

FINAL_COMPARISON_CSV = TABLES_DIR / "final_comparison.csv"
EVAL_JSON = TABLES_DIR / "evaluation_metrics.json"
CALIBRATION_CSV = TABLES_DIR / "calibration_test.csv"
PSI_CSV = TABLES_DIR / "psi_table.csv"
FAIRNESS_CSV = TABLES_DIR / "fairness_table.csv"
REFUSAL_CSV = TABLES_DIR / "refusal_reasons.csv"
TEST_SCORES = MODELS_DIR / "test_scores.parquet"
ALL_SCORES = MODELS_DIR / "all_scores.parquet"
ACCESS_LOG = MODELS_DIR / "test_access_log.csv"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------
def model_metrics(y, risk, pd_hat) -> dict[str, float]:
    """risk : valeur croissante avec le risque (AUC, KS) ; pd_hat : probabilité (Brier)."""
    y = np.asarray(y)
    auc = roc_auc_score(y, risk)
    fpr, tpr, _ = roc_curve(y, risk)
    return {"auc": float(auc), "gini": float(2 * auc - 1), "ks": float(np.max(tpr - fpr)),
            "brier": float(brier_score_loss(y, pd_hat)), "mean_pd": float(np.mean(pd_hat)),
            "default_rate": float(np.mean(y))}


def bootstrap_ci(y, risk_a, risk_b, n_boot: int = N_BOOT, seed: int = RANDOM_STATE) -> dict:
    """Bootstrap apparié (mêmes indices pour les deux modèles) ; IC percentiles 2,5 – 97,5 %."""
    y, risk_a, risk_b = map(np.asarray, (y, risk_a, risk_b))
    rng = np.random.default_rng(seed)
    n = len(y)
    a, b = np.empty(n_boot), np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        a[i] = roc_auc_score(y[idx], risk_a[idx])
        b[i] = roc_auc_score(y[idx], risk_b[idx])

    def ci(est: float, draws: np.ndarray) -> dict:
        lo, hi = np.percentile(draws, [2.5, 97.5])
        return {"estimate": float(est), "low": float(lo), "high": float(hi), "se": float(draws.std(ddof=1))}

    auc_a, auc_b = roc_auc_score(y, risk_a), roc_auc_score(y, risk_b)
    return {
        "n_resamples": n_boot, "seed": seed, "method": "percentile, paired",
        "scorecard_auc": ci(auc_a, a), "scorecard_gini": ci(2 * auc_a - 1, 2 * a - 1),
        "lgbm_auc": ci(auc_b, b), "lgbm_gini": ci(2 * auc_b - 1, 2 * b - 1),
        "auc_diff_lgbm_minus_scorecard": ci(auc_b - auc_a, b - a),
        "share_resamples_lgbm_better": float((b > a).mean()),
    }


def calibration_deciles(y, pd_hat, model: str) -> pd.DataFrame:
    d = pd.DataFrame({"y": np.asarray(y), "pd": np.asarray(pd_hat)})
    d["decile"] = pd.qcut(d["pd"].rank(method="first"), 10, labels=False) + 1
    g = d.groupby("decile").agg(n=("y", "size"), pd_mean=("pd", "mean"), observed_rate=("y", "mean"),
                                pd_min=("pd", "min"), pd_max=("pd", "max")).reset_index()
    g["gap"] = g["pd_mean"] - g["observed_rate"]
    g.insert(0, "model", model)
    return g


def psi(expected, actual, eps: float = 1e-6) -> float:
    """PSI = Σ (a − e) · ln(a / e) sur des proportions (planchers à eps)."""
    e = np.clip(np.asarray(expected, dtype=float), eps, None)
    a = np.clip(np.asarray(actual, dtype=float), eps, None)
    return float(np.sum((a - e) * np.log(a / e)))


def shares(codes, categories) -> np.ndarray:
    s = pd.Series(codes).value_counts(normalize=True)
    return np.array([s.get(c, 0.0) for c in categories])


def score_edges(train_score) -> list[float]:
    """Bornes de 10 tranches = déciles du score du train (valeurs dupliquées fusionnées)."""
    q = np.unique(np.quantile(np.asarray(train_score), np.linspace(0.1, 0.9, 9)))
    return [-EDGE_SENTINEL, *map(float, q), EDGE_SENTINEL]


def score_decile(score, edges) -> np.ndarray:
    """1 = scores les plus bas (risque le plus élevé) … 10 = scores les plus hauts."""
    return pd.cut(np.asarray(score), bins=edges, labels=False, right=False).astype(int) + 1


# ---------------------------------------------------------------------------
# Grille : points par variable et motifs de refus
# ---------------------------------------------------------------------------
def points_matrix(df: pd.DataFrame) -> pd.DataFrame:
    bp, res, meta = load_artifacts()
    variables, categorical = meta["variables"], meta["categorical"]
    W = transform_woe(bp, prepare_X(df, variables, [c for c in categorical if c in variables]), variables)
    b0, n = float(res.params["const"]), len(variables)
    return pd.DataFrame({v: points_from_woe(W[v].to_numpy(), float(res.params[v]), b0, n) for v in variables},
                        index=df.index)


def bin_indices(df: pd.DataFrame) -> pd.DataFrame:
    bp, _, meta = load_artifacts()
    variables, categorical = meta["variables"], meta["categorical"]
    X = prepare_X(df, variables, [c for c in categorical if c in variables])
    return pd.DataFrame({v: bp.get_binned_variable(v).transform(X[v].to_numpy(), metric="indices")
                         for v in variables}, index=df.index)


def top_reasons(points: pd.DataFrame, max_points: pd.Series, k: int = 3) -> pd.DataFrame:
    """k variables au plus grand manque (points max − points obtenus) ; vide si manque nul."""
    short = (max_points[points.columns].to_numpy() - points.to_numpy()).clip(min=0)
    order = np.argsort(-short, axis=1, kind="stable")       # égalité : ordre de la grille (IV décroissant)
    cols = np.asarray(points.columns)
    out = {}
    for j in range(k):
        idx = order[:, j]
        val = short[np.arange(len(short)), idx]
        out[f"reason_{j + 1}"] = np.where(val > 0, cols[idx], "")
        out[f"shortfall_{j + 1}"] = val
    return pd.DataFrame(out, index=points.index)


# ---------------------------------------------------------------------------
# Chaîne
# ---------------------------------------------------------------------------
def run(dry_run: bool) -> None:
    t0 = time.perf_counter()
    ensure_dirs()
    _, _, meta = load_artifacts()
    sc_vars = meta["variables"]
    booster, _ = load_artefacts(str(MODEL_PATH))
    booster_no_ext, _ = load_artefacts(str(MODEL_NO_EXT_PATH))
    feats = list(dict.fromkeys([*sc_vars, *booster.feature_name(), *booster_no_ext.feature_name()]))
    cols = list(dict.fromkeys(["SK_ID_CURR", "TARGET", "CODE_GENDER", "AMT_CREDIT", *feats]))

    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        data = {s: load_split(con, s, cols) for s in ("train", "valid")}
        if dry_run:
            log("[DRY-RUN] test NON ouvert : la validation sert de test de répétition (sorties provisoires).")
            data["test"] = data["valid"].copy()
            opening = {"dry_run": True, "timestamp_utc": None, "n_rows": int(len(data["test"])),
                       "fingerprint_match": None}
        else:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            log("=" * 88)
            log(f"[D15] LECTURE DU TEST SCELLÉ — seul script autorisé, lecture journalisée (Phase 4b) — {ts}")
            data["test"] = load_split(con, "test", cols, allow_test=True)
            fp = fingerprint(data["test"]["SK_ID_CURR"])
            ref = con.execute("SELECT ids_sha256 FROM split_meta WHERE split = 'test'").fetchone()[0]
            opening = {"dry_run": False, "timestamp_utc": ts, "n_rows": int(len(data["test"])),
                       "ids_sha256": fp, "fingerprint_match": fp == ref,
                       "script": "scripts/evaluate_models.py", "call": "load_split(con, 'test', allow_test=True)"}
            log(f"[D15] {len(data['test']):,} demandes · empreinte {fp[:16]}… "
                f"{'identique à split_meta' if fp == ref else 'DIFFÉRENTE de split_meta'}")
            log("=" * 88)
            line = pd.DataFrame([{k: opening[k] for k in ("timestamp_utc", "n_rows", "ids_sha256", "fingerprint_match")}])
            line.to_csv(ACCESS_LOG, mode="a", header=not ACCESS_LOG.exists(), index=False)
            if fp != ref:
                raise RuntimeError("Empreinte du test différente de split_meta : arrêt.")

    # --- Scores ---
    frames = []
    for s, df in data.items():
        sc = score_frame(df)
        frames.append(pd.DataFrame({
            "SK_ID_CURR": df["SK_ID_CURR"].to_numpy(), "split": s,
            "score": sc["score"].to_numpy(), "pd_scorecard": sc["pd"].to_numpy(),
            "pd_lgbm": predict_frame(df)["pd"].to_numpy(),
            "pd_lgbm_no_ext": predict_frame(df, MODEL_NO_EXT_PATH)["pd"].to_numpy(),
            "TARGET": df["TARGET"].to_numpy(), "AMT_CREDIT": df["AMT_CREDIT"].to_numpy(),
            "CODE_GENDER": df["CODE_GENDER"].to_numpy(),
        }))
        log(f"[scores] {s} : {len(df):,} demandes scorées ({time.perf_counter() - t0:.0f} s)")
    scores = pd.concat(frames, ignore_index=True)
    S = {s: scores[scores["split"].eq(s)].reset_index(drop=True) for s in data}

    # --- Comparaison train / valid / test ---
    rows, metr = [], {}
    for s, d in S.items():
        metr[s] = {
            "scorecard": model_metrics(d["TARGET"], -d["score"], d["pd_scorecard"]),
            "lgbm": model_metrics(d["TARGET"], d["pd_lgbm"], d["pd_lgbm"]),
            "lgbm_no_ext": model_metrics(d["TARGET"], d["pd_lgbm_no_ext"], d["pd_lgbm_no_ext"]),
        }
        metr[s]["scorecard"]["auc_logit_pd"] = float(roc_auc_score(d["TARGET"], d["pd_scorecard"]))
        for m, v in metr[s].items():
            rows.append({"model": m, "split": s, "n": len(d), **{k: v[k] for k in ("auc", "gini", "ks", "brier", "mean_pd", "default_rate")}})
    comp = pd.DataFrame(rows)
    comp["model"] = pd.Categorical(comp["model"], ["scorecard", "lgbm", "lgbm_no_ext"])
    comp = comp.sort_values("model", kind="stable")   # ordre des échantillons conservé : train, valid, test
    comp["model"] = comp["model"].astype(str)
    te = S["test"]
    boot = bootstrap_ci(te["TARGET"], -te["score"], te["pd_lgbm"])
    log(f"[bootstrap] AUC grille {boot['scorecard_auc']['estimate']:.4f} "
        f"[{boot['scorecard_auc']['low']:.4f}; {boot['scorecard_auc']['high']:.4f}] · LightGBM "
        f"{boot['lgbm_auc']['estimate']:.4f} [{boot['lgbm_auc']['low']:.4f}; {boot['lgbm_auc']['high']:.4f}] · écart "
        f"{boot['auc_diff_lgbm_minus_scorecard']['estimate']:.4f} [{boot['auc_diff_lgbm_minus_scorecard']['low']:.4f}; "
        f"{boot['auc_diff_lgbm_minus_scorecard']['high']:.4f}] ({time.perf_counter() - t0:.0f} s)")

    # --- Calibration (test) ; isotone ajustée sur la validation ---
    va = S["valid"]
    cal_tables, calib = [], {"criterion": {"mean_abs_decile_gap_max": CAL_MEAN_GAP_MAX,
                                           "max_abs_decile_gap_max": CAL_MAX_GAP_MAX}}
    for m, col in (("scorecard", "pd_scorecard"), ("lgbm", "pd_lgbm")):
        ct = calibration_deciles(te["TARGET"], te[col], m)
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(va[col], va["TARGET"])
        p_iso = iso.predict(te[col])
        ct["pd_mean_isotonic_valid"] = calibration_deciles(te["TARGET"], p_iso, m)["pd_mean"].to_numpy() \
            if len(np.unique(p_iso)) >= 10 else np.nan
        cal_tables.append(ct)
        mean_gap, max_gap = float(ct["gap"].abs().mean()), float(ct["gap"].abs().max())
        mis = bool(mean_gap > CAL_MEAN_GAP_MAX or max_gap > CAL_MAX_GAP_MAX)
        calib[m] = {"brier": metr["test"][m]["brier"], "mean_pd": float(te[col].mean()),
                    "default_rate": float(te["TARGET"].mean()), "mean_abs_decile_gap": mean_gap,
                    "max_abs_decile_gap": max_gap, "miscalibrated": mis,
                    "isotonic_valid_brier_test": float(brier_score_loss(te["TARGET"], p_iso)),
                    "isotonic_applied": mis}
        log(f"[calibration] {m} : Brier {calib[m]['brier']:.5f} · écart moyen {mean_gap:.4f} · max {max_gap:.4f} → "
            f"{'MAL calibré' if mis else 'calibré'} · Brier isotone(valid) {calib[m]['isotonic_valid_brier_test']:.5f}")
    cal = pd.concat(cal_tables, ignore_index=True)

    # --- Déciles de score et PSI ---
    edges = score_edges(S["train"]["score"])
    scores["decile"] = score_decile(scores["score"], edges)
    cats = list(range(1, len(edges)))
    sh = {s: shares(scores.loc[scores["split"].eq(s), "decile"], cats) for s in data}
    psi_rows = [{"level": "score", "name": "score", "n_bins": len(cats),
                 "psi": psi(sh["train"], sh["test"]), "psi_train_valid": psi(sh["train"], sh["valid"])}]
    idx = {s: bin_indices(data[s]) for s in data}
    for v in sc_vars:
        bins = sorted(set(idx["train"][v]) | set(idx["test"][v]) | set(idx["valid"][v]))
        e = shares(idx["train"][v], bins)
        psi_rows.append({"level": "variable", "name": v, "n_bins": len(bins),
                         "psi": psi(e, shares(idx["test"][v], bins)),
                         "psi_train_valid": psi(e, shares(idx["valid"][v], bins))})
    psi_t = pd.DataFrame(psi_rows)
    psi_t["flag"] = np.where(psi_t["psi"] > PSI_SEVERE, "instable",
                             np.where(psi_t["psi"] > PSI_MODERATE, "a_surveiller", "stable"))
    log(f"[PSI] score {psi_t.iloc[0]['psi']:.5f} · max variable {psi_t.iloc[1:]['psi'].max():.5f} "
        f"({psi_t.iloc[1:].sort_values('psi').iloc[-1]['name']})")

    # --- Seuil recommandé (choisi sur la validation) ---
    cutoffs = scenario_cutoffs(va["score"])
    reco, _ = recommend(va, cutoffs)
    cut = cutoffs[reco]["cutoff"]

    # --- Équité par CODE_GENDER ---
    fr = []
    for g in ("F", "M"):
        d = te[te["CODE_GENDER"].eq(g)]
        acc = d["score"] >= cut
        goods = d["TARGET"].eq(0)
        fr.append({"group": g, "n": len(d), "default_rate": d["TARGET"].mean(), "mean_score": d["score"].mean(),
                   "mean_pd_scorecard": d["pd_scorecard"].mean(), "mean_pd_lgbm": d["pd_lgbm"].mean(),
                   "auc_scorecard": roc_auc_score(d["TARGET"], -d["score"]),
                   "auc_lgbm": roc_auc_score(d["TARGET"], d["pd_lgbm"]),
                   "cutoff": cut, "scenario": reco, "approval_rate": acc.mean(),
                   "approval_rate_goods": acc[goods].mean(), "approval_rate_bads": acc[~goods].mean(),
                   "bad_rate_accepted": d.loc[acc, "TARGET"].mean()})
    fair = pd.DataFrame(fr)
    fv = fair.set_index("group")
    fairness = {"cutoff": cut, "scenario": reco, "xna_count_test": int(te["CODE_GENDER"].eq("XNA").sum()),
                "xna_count_all": int(scores["CODE_GENDER"].eq("XNA").sum()),
                "approval_ratio_f_over_m": float(fv.loc["F", "approval_rate"] / fv.loc["M", "approval_rate"]),
                "approval_ratio_goods_f_over_m": float(fv.loc["F", "approval_rate_goods"] / fv.loc["M", "approval_rate_goods"]),
                "auc_gap_f_minus_m_scorecard": float(fv.loc["F", "auc_scorecard"] - fv.loc["M", "auc_scorecard"])}
    log(f"[équité] seuil {cut} ({reco}) · acceptation F {fv.loc['F', 'approval_rate']:.1%} / M "
        f"{fv.loc['M', 'approval_rate']:.1%} · défaut F {fv.loc['F', 'default_rate']:.2%} / M {fv.loc['M', 'default_rate']:.2%}")

    # --- Motifs de refus ---
    grid = pd.read_csv(SCORECARD_TABLE)
    max_pts = grid.groupby("variable")["points"].max()
    reasons = []
    for s in data:
        pts = points_matrix(data[s])
        if not np.array_equal(pts.sum(axis=1).to_numpy(), S[s]["score"].to_numpy()):
            raise RuntimeError(f"Somme des points ≠ score ({s}).")
        reasons.append(top_reasons(pts, max_pts))
    rs = pd.concat(reasons, ignore_index=True)
    scores = pd.concat([scores.reset_index(drop=True), rs], axis=1)
    te_r = scores[scores["split"].eq("test")]
    refused = te_r[te_r["score"] < cut]
    top3 = pd.concat([refused[f"reason_{j}"] for j in (1, 2, 3)])
    rr = pd.DataFrame({
        "n_reason1_refused": refused["reason_1"].value_counts(),
        "n_top3_refused": top3[top3 != ""].value_counts(),
        "n_reason1_all_test": te_r["reason_1"].value_counts(),
    }).fillna(0).astype(int)
    rr = rr[rr.index != ""]
    rr.index.name = "variable"
    rr["pct_reason1_refused"] = rr["n_reason1_refused"] / len(refused)
    rr["pct_top3_refused"] = rr["n_top3_refused"] / len(refused)
    rr["pct_reason1_all_test"] = rr["n_reason1_all_test"] / len(te_r)
    rr["max_points"] = max_pts.reindex(rr.index).to_numpy()
    rr = rr.sort_values(["n_reason1_refused", "n_top3_refused"], ascending=False).reset_index()
    rr.insert(1, "scenario", reco)
    rr.insert(2, "cutoff", cut)
    log(f"[motifs] {len(refused):,} refusés au test (seuil {cut}) · 1er motif le plus fréquent : "
        f"{rr.iloc[0]['variable']} ({rr.iloc[0]['pct_reason1_refused']:.1%})")

    # --- Écritures ---
    ext_vars = [v for v in sc_vars if "EXT_SOURCE" in v]
    out = {
        "dry_run": dry_run, "test_opening": opening,
        "n": {s: int(len(d)) for s, d in S.items()},
        "train_metrics": metr["train"], "valid_metrics": metr["valid"], "test_metrics": metr["test"],
        "bootstrap": boot, "calibration": calib,
        "psi": {"score_train_test": float(psi_t.iloc[0]["psi"]), "score_train_valid": float(psi_t.iloc[0]["psi_train_valid"]),
                "max_variable": float(psi_t.iloc[1:]["psi"].max()),
                "max_variable_name": str(psi_t.iloc[1:].sort_values("psi").iloc[-1]["name"]),
                "thresholds": {"moderate": PSI_MODERATE, "severe": PSI_SEVERE}},
        "decile_edges": edges, "decile_convention": "1 = scores les plus bas (risque élevé), bornes = déciles du train",
        "fairness": fairness,
        "recommended_cutoff": {"scenario": reco, "cutoff": cut},
        "scorecard_n_vars": len(sc_vars), "scorecard_ext_vars": ext_vars, "scorecard_ext_vars_count": len(ext_vars),
        "metric_notes": "Grille : AUC/KS sur le score entier, Brier sur la PD du logit. LightGBM : PD.",
    }
    comp.to_csv(FINAL_COMPARISON_CSV, index=False, float_format="%.6f")
    cal.to_csv(CALIBRATION_CSV, index=False, float_format="%.6f")
    psi_t.to_csv(PSI_CSV, index=False, float_format="%.6f")
    fair.to_csv(FAIRNESS_CSV, index=False, float_format="%.6f")
    rr.to_csv(REFUSAL_CSV, index=False, float_format="%.6f")
    EVAL_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    keep = ["SK_ID_CURR", "split", "score", "pd_scorecard", "pd_lgbm", "TARGET", "decile",
            "pd_lgbm_no_ext", "AMT_CREDIT", "CODE_GENDER", "reason_1", "reason_2", "reason_3"]
    scores[keep].to_parquet(ALL_SCORES, index=False)
    scores.loc[scores["split"].eq("test"), keep].to_parquet(TEST_SCORES, index=False)
    for p in (FINAL_COMPARISON_CSV, EVAL_JSON, CALIBRATION_CSV, PSI_CSV, FAIRNESS_CSV, REFUSAL_CSV, TEST_SCORES, ALL_SCORES):
        log(f"[écrit] {p.relative_to(PROJECT_ROOT).as_posix()}")
    log(f"[durée] {time.perf_counter() - t0:.0f} s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="la validation remplace le test (le test n'est pas ouvert)")
    run(ap.parse_args().dry_run)


if __name__ == "__main__":
    main()
