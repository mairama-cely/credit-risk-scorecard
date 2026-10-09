"""Phase 4a — Challenger LightGBM : apprentissage, ablation EXT_SOURCE, SHAP.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/train_challenger.py [--threads 4] [--skip-shap]

- Variables : toutes celles du catalogue au statut « candidate » (D16), valeurs brutes ;
  NaN laissés à LightGBM ; colonnes texte → category, modalités figées sur le train
  (modalité inconnue → NaN). Booléen → 0/1.
- Apprentissage sur le train, early stopping sur la validation (AUC). Le test reste scellé
  (D15) : il n'est jamais lu ici. predict_frame() servira à le scorer plus tard.
- Deux variantes comparées sur la validation : sans pondération / scale_pos_weight = neg/pos.
  Règle : AUC de validation la plus haute, sauf si le Brier de cette variante dépasse de
  plus de 10 % celui de l'autre (calibration de la PD dégradée) → on garde l'autre.
- Ablation : la variante retenue réentraînée sans aucune variable dont le nom contient
  « EXT_SOURCE » (EXT_SOURCE_1..3, APP_EXT_SOURCE_MEAN, APP_EXT_SOURCE_NB_MISSING).
- SHAP (TreeExplainer) sur 5 000 lignes de validation tirées avec RANDOM_STATE.

Sorties :
    models/lgbm_model.txt, models/lgbm_model_no_ext.txt, models/lgbm_categories.json,
    models/lgbm_valid_scores.parquet,
    output/tables/challenger_metrics.json, output/tables/lgbm_feature_importance.csv,
    output/tables/shap_importance.csv, output/05_*.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from functools import lru_cache
from pathlib import Path

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_feature_catalog import CAND, CATALOG  # noqa: E402
from config import DB_PATH, FIGURES_DIR, MODELS_DIR, RANDOM_STATE, TABLES_DIR, ensure_dirs  # noqa: E402
from make_splits import load_split  # noqa: E402

MODEL_PATH = MODELS_DIR / "lgbm_model.txt"
MODEL_NO_EXT_PATH = MODELS_DIR / "lgbm_model_no_ext.txt"
CATEGORIES_PATH = MODELS_DIR / "lgbm_categories.json"
VALID_SCORES_PATH = MODELS_DIR / "lgbm_valid_scores.parquet"
METRICS_PATH = TABLES_DIR / "challenger_metrics.json"
IMPORTANCE_PATH = TABLES_DIR / "lgbm_feature_importance.csv"
SHAP_IMPORTANCE_PATH = TABLES_DIR / "shap_importance.csv"

NUM_THREADS = 4             # fixé pour la reproductibilité (deterministic=True)
NUM_BOOST_ROUND = 3000      # plafond ; l'early stopping arrête bien avant
EARLY_STOPPING = 100
BRIER_TOLERANCE = 1.10      # Brier > 110 % de l'autre variante = calibration nettement dégradée
SHAP_SAMPLE = 5000
N_DEPENDENCE = 5

BASE_PARAMS: dict = {
    "objective": "binary",
    "metric": "auc",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 100,
    "feature_fraction": 0.7,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 5.0,
    "seed": RANDOM_STATE,
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": NUM_THREADS,
    "verbosity": -1,
}

FEATURES: list[str] = [c for c, v in CATALOG.items() if v[3] == CAND]
EXT_FEATURES: list[str] = [c for c in FEATURES if "EXT_SOURCE" in c]

# Style des figures : identique aux notebooks 00 à 02
BLUE, INK, INK2, GRID, GREY = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df", "#a3a29d"
RED = "#c8553d"
PLOT_STYLE = {
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 11, "font.size": 9,
}


# ---------------------------------------------------------------------------
# Préparation des données
# ---------------------------------------------------------------------------
def fit_categories(train: pd.DataFrame, features: list[str]) -> dict[str, list[str]]:
    """Modalités (triées) des colonnes texte, apprises sur le train seul."""
    cats = {}
    for c in features:
        s = train[c]
        if not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)):
            cats[c] = sorted(s.dropna().astype(str).unique().tolist())
    return cats


def prepare_X(df: pd.DataFrame, features: list[str], categories: dict[str, list[str]]) -> pd.DataFrame:
    """Matrice LightGBM : category pour les colonnes texte, float64 (NaN) pour le reste."""
    out = {}
    for c in features:
        s = df[c]
        if c in categories:
            vals = s.astype(object).where(s.notna(), None)
            vals = vals.map(lambda v: None if v is None else str(v))
            out[c] = pd.Categorical(vals, categories=categories[c])
        elif pd.api.types.is_bool_dtype(s) or s.dtype == object:
            out[c] = s.map({True: 1.0, False: 0.0}).astype("float64")
        else:
            out[c] = pd.to_numeric(s).astype("float64")
    return pd.DataFrame(out, index=df.index)


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------
def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    auc = roc_auc_score(y, p)
    fpr, tpr, _ = roc_curve(y, p)
    return {
        "auc": round(float(auc), 5),
        "gini": round(float(2 * auc - 1), 5),
        "ks": round(float(np.max(tpr - fpr)), 5),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "mean_pd": round(float(np.mean(p)), 5),
        "default_rate": round(float(np.mean(y)), 5),
    }


# ---------------------------------------------------------------------------
# Apprentissage
# ---------------------------------------------------------------------------
def train_one(X_tr, y_tr, X_va, y_va, params: dict) -> lgb.Booster:
    dtr = lgb.Dataset(X_tr, label=y_tr, categorical_feature="auto", free_raw_data=False)
    dva = lgb.Dataset(X_va, label=y_va, reference=dtr, categorical_feature="auto", free_raw_data=False)
    return lgb.train(
        params, dtr, num_boost_round=NUM_BOOST_ROUND, valid_sets=[dva], valid_names=["valid"],
        callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False)],
    )


def evaluate(booster: lgb.Booster, X_tr, y_tr, X_va, y_va) -> dict:
    it = booster.best_iteration
    return {
        "best_iteration": int(it),
        "train": metrics(y_tr, booster.predict(X_tr, num_iteration=it)),
        "valid": metrics(y_va, booster.predict(X_va, num_iteration=it)),
    }


def choose_variant(res: dict[str, dict]) -> tuple[str, str]:
    """Règle documentée : meilleure AUC de validation, sauf Brier > 110 % de l'autre."""
    a, b = "unweighted", "scale_pos_weight"
    best, other = (a, b) if res[a]["valid"]["auc"] >= res[b]["valid"]["auc"] else (b, a)
    if res[best]["valid"]["brier"] > BRIER_TOLERANCE * res[other]["valid"]["brier"]:
        reason = (f"{best} a l'AUC la plus haute ({res[best]['valid']['auc']:.4f} vs "
                  f"{res[other]['valid']['auc']:.4f}) mais un Brier > {BRIER_TOLERANCE:.0%} de celui de "
                  f"{other} ({res[best]['valid']['brier']:.4f} vs {res[other]['valid']['brier']:.4f}) : {other} retenu.")
        return other, reason
    reason = (f"{best} a l'AUC de validation la plus haute ({res[best]['valid']['auc']:.4f} vs "
              f"{res[other]['valid']['auc']:.4f}) sans dégradation du Brier au-delà de {BRIER_TOLERANCE:.0%} "
              f"({res[best]['valid']['brier']:.4f} vs {res[other]['valid']['brier']:.4f}).")
    return best, reason


# ---------------------------------------------------------------------------
# Scoring réutilisable (test en Phase 4)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=2)
def load_artefacts(model_path: str = str(MODEL_PATH)) -> tuple[lgb.Booster, dict[str, list[str]]]:
    booster = lgb.Booster(model_file=model_path)
    categories = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    return booster, categories


def predict_frame(df: pd.DataFrame, model_path: Path = MODEL_PATH) -> pd.DataFrame:
    """PD du challenger pour un DataFrame contenant SK_ID_CURR et les variables du modèle.

    Charge models/lgbm_model.txt (ou model_path) et models/lgbm_categories.json ;
    utilise la meilleure itération enregistrée dans le modèle.
    """
    booster, categories = load_artefacts(str(model_path))
    features = booster.feature_name()
    X = prepare_X(df, features, categories)
    pd_hat = booster.predict(X, num_iteration=booster.best_iteration)
    return pd.DataFrame({"SK_ID_CURR": df["SK_ID_CURR"].to_numpy(), "pd": pd_hat})


# ---------------------------------------------------------------------------
# SHAP
# ---------------------------------------------------------------------------
def shap_sample(X_va: pd.DataFrame, n: int = SHAP_SAMPLE) -> pd.DataFrame:
    """Échantillon fixe de la validation (RANDOM_STATE), ordre d'origine conservé."""
    rng = np.random.default_rng(RANDOM_STATE)
    idx = np.sort(rng.choice(len(X_va), size=min(n, len(X_va)), replace=False))
    return X_va.iloc[idx]


def compute_shap(booster: lgb.Booster, X: pd.DataFrame):
    """Explanation SHAP (log-odds) ; data numérique (codes de modalité) pour les couleurs.

    Contrôle : la somme des contributions + base = marge brute du modèle (additivité).
    """
    import shap

    explainer = shap.TreeExplainer(booster)
    sv = explainer(X)
    values = sv.values[:, :, 1] if sv.values.ndim == 3 else sv.values
    base = np.asarray(sv.base_values)
    base = base[:, 1] if base.ndim == 2 else base
    margin = booster.predict(X, num_iteration=booster.best_iteration, raw_score=True)
    gap = float(np.max(np.abs(values.sum(axis=1) + base - margin)))
    if gap > 1e-4:
        raise RuntimeError(f"Additivité SHAP non vérifiée (écart max {gap:.2e}).")
    data = X.copy()
    for c in data.columns:
        if isinstance(data[c].dtype, pd.CategoricalDtype):
            data[c] = data[c].cat.codes.replace(-1, np.nan).astype("float64")
    return shap.Explanation(values=values, base_values=base, data=data.to_numpy(dtype="float64"),
                            feature_names=list(X.columns)), gap


def shap_importance(expl) -> pd.DataFrame:
    imp = np.abs(expl.values).mean(axis=0)
    t = pd.DataFrame({"feature": expl.feature_names, "mean_abs_shap": imp})
    t = t.sort_values("mean_abs_shap", ascending=False, ignore_index=True)
    t["share_pct"] = 100 * t["mean_abs_shap"] / t["mean_abs_shap"].sum()
    t["rank"] = np.arange(1, len(t) + 1)
    return t


def individual_cases(pd_sample: np.ndarray) -> dict[str, int]:
    """Positions (dans l'échantillon SHAP) des cas PD minimale, médiane, maximale."""
    order = np.argsort(pd_sample, kind="stable")
    return {"low": int(order[0]), "median": int(order[len(order) // 2]), "high": int(order[-1])}


def make_shap_figures(expl, X: pd.DataFrame, pd_sample: np.ndarray, imp: pd.DataFrame,
                      categories: dict[str, list[str]], out_dir: Path = FIGURES_DIR) -> list[Path]:
    """Figures 05_* : bar, beeswarm, 5 dépendances, 3 waterfalls. Renvoie les chemins."""
    import matplotlib.pyplot as plt
    import shap

    plt.rcParams.update(PLOT_STYLE)
    paths = []
    n = len(X)

    def save(fig, name):
        p = out_dir / name
        fig.savefig(p, dpi=150, bbox_inches="tight")
        plt.close(fig)
        paths.append(p)

    # Importance globale (moyenne |SHAP|), 20 premières
    top = imp.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 6.5))
    ax.barh(top["feature"], top["mean_abs_shap"], color=BLUE)
    ax.set_xlabel("moyenne |SHAP| (log-odds)")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_title(f"Importance SHAP globale — 20 premières variables (validation, n = {n:,})")
    save(fig, "05_shap_bar.png")

    # Beeswarm
    shap.plots.beeswarm(expl, max_display=20, show=False, plot_size=(9, 7.5))
    fig = plt.gcf()
    fig.axes[0].set_title(f"Distribution des contributions SHAP — 20 premières variables (n = {n:,})")
    fig.axes[0].set_xlabel("valeur SHAP (log-odds ; > 0 = PD plus élevée)")
    save(fig, "05_shap_beeswarm.png")

    # Dépendances des 5 premières variables
    cols = list(X.columns)
    top5 = imp["feature"].head(N_DEPENDENCE).tolist()
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for ax, f in zip(axes.flat, top5):
        j = cols.index(f)
        x, v = expl.data[:, j], expl.values[:, j]
        miss = np.isnan(x)
        if f in categories:
            codes = x[~miss].astype(int)
            means = pd.Series(v[~miss]).groupby(codes).mean()
            cnt = pd.Series(codes).value_counts()
            keep = cnt[cnt >= 30].index.intersection(means.index)
            m = means.loc[keep]
            m = m.loc[m.abs().sort_values(ascending=False).index[:16]].sort_values()
            ax.barh([categories[f][k][:28] for k in m.index], m.values, color=BLUE)
            ax.axvline(0, color=INK2, lw=0.8)
            ax.set_xlabel("SHAP moyen par modalité (16 plus marquées, ≥ 30 lignes)")
        else:
            ax.scatter(x[~miss], v[~miss], s=4, alpha=0.35, color=BLUE, linewidths=0)
            if miss.any():
                lo = np.nanmin(x) if (~miss).any() else 0.0
                ax.scatter(np.full(miss.sum(), lo), v[miss], s=4, alpha=0.35, color=GREY, linewidths=0,
                           label=f"manquant (n = {miss.sum():,})")
                ax.legend(loc="best", frameon=False, fontsize=8)
            ax.axhline(0, color=INK2, lw=0.8)
            ax.set_xlabel(f)
            ax.set_ylabel("valeur SHAP (log-odds)")
        ax.set_title(f)
        ax.grid(color=GRID, lw=0.6)
    for ax in list(axes.flat)[len(top5):]:
        ax.axis("off")
    fig.suptitle(f"Dépendances SHAP des {N_DEPENDENCE} premières variables (validation, n = {n:,} ; "
                 "manquants en gris, placés au minimum observé)", fontsize=11, fontweight="bold")
    fig.tight_layout()
    save(fig, "05_shap_dependence.png")

    # Cas individuels
    labels = {"low": "PD la plus basse", "median": "PD médiane", "high": "PD la plus haute"}
    for key, pos in individual_cases(pd_sample).items():
        row = expl[pos]
        # Valeurs affichées : modalité en clair pour les catégorielles
        disp = []
        for c in cols:
            val = X.iloc[pos][c]
            disp.append("NaN" if pd.isna(val) else (str(val)[:20] if c in categories else round(float(val), 3)))
        row = type(row)(values=row.values, base_values=row.base_values, data=np.array(disp, dtype=object),
                        feature_names=row.feature_names)
        shap.plots.waterfall(row, max_display=12, show=False)
        fig = plt.gcf()
        fig.set_size_inches(9, 6.5)
        fig.axes[0].set_title(f"Cas « {labels[key]} » — PD = {pd_sample[pos]:.4f} (log-odds, base = moyenne du modèle)")
        save(fig, f"05_shap_waterfall_{key}.png")
    return paths


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=int, default=NUM_THREADS, help="num_threads LightGBM (fixe)")
    ap.add_argument("--skip-shap", action="store_true", help="ne pas recalculer SHAP ni les figures")
    args = ap.parse_args()
    t0 = time.perf_counter()
    ensure_dirs()
    if not DB_PATH.exists():
        print(f"[ERREUR] {DB_PATH} introuvable.", file=sys.stderr)
        sys.exit(1)

    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        cols = ["SK_ID_CURR", "TARGET", *FEATURES]
        train = load_split(con, "train", cols)
        valid = load_split(con, "valid", cols)
    categories = fit_categories(train, FEATURES)
    X_tr, X_va = prepare_X(train, FEATURES, categories), prepare_X(valid, FEATURES, categories)
    y_tr, y_va = train["TARGET"].to_numpy(int), valid["TARGET"].to_numpy(int)
    CATEGORIES_PATH.write_text(json.dumps(categories, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[données] train {X_tr.shape} · valid {X_va.shape} · {len(categories)} catégorielles · "
          f"défaut train {y_tr.mean():.4f} ({time.perf_counter() - t0:.0f}s)")

    params = {**BASE_PARAMS, "num_threads": args.threads}
    spw = float((y_tr == 0).sum() / (y_tr == 1).sum())
    variant_params = {"unweighted": params, "scale_pos_weight": {**params, "scale_pos_weight": spw}}
    boosters, results = {}, {}
    for name, p in variant_params.items():
        t = time.perf_counter()
        boosters[name] = train_one(X_tr, y_tr, X_va, y_va, p)
        results[name] = evaluate(boosters[name], X_tr, y_tr, X_va, y_va)
        r = results[name]
        print(f"[{name}] best_it {r['best_iteration']} · AUC train {r['train']['auc']:.4f} valid "
              f"{r['valid']['auc']:.4f} · Brier valid {r['valid']['brier']:.4f} ({time.perf_counter() - t:.0f}s)")
    chosen, reason = choose_variant(results)
    booster = boosters[chosen]
    print(f"[choix] {chosen} — {reason}")

    # Ablation EXT_SOURCE
    t = time.perf_counter()
    feats_no_ext = [c for c in FEATURES if c not in EXT_FEATURES]
    b_no_ext = train_one(X_tr[feats_no_ext], y_tr, X_va[feats_no_ext], y_va, variant_params[chosen])
    res_no_ext = evaluate(b_no_ext, X_tr[feats_no_ext], y_tr, X_va[feats_no_ext], y_va)
    d_auc = res_no_ext["valid"]["auc"] - results[chosen]["valid"]["auc"]
    d_gini = res_no_ext["valid"]["gini"] - results[chosen]["valid"]["gini"]
    print(f"[ablation] sans {len(EXT_FEATURES)} var. EXT_SOURCE : AUC valid {res_no_ext['valid']['auc']:.4f} "
          f"(Δ {d_auc:+.4f}) · Gini Δ {d_gini:+.4f} ({time.perf_counter() - t:.0f}s)")

    # Artefacts
    booster.save_model(str(MODEL_PATH), num_iteration=booster.best_iteration)
    b_no_ext.save_model(str(MODEL_NO_EXT_PATH), num_iteration=b_no_ext.best_iteration)
    load_artefacts.cache_clear()
    scores = predict_frame(valid)
    gap = float(np.max(np.abs(scores["pd"].to_numpy() - booster.predict(X_va, num_iteration=booster.best_iteration))))
    if gap > 1e-9:
        raise RuntimeError(f"predict_frame ≠ modèle en mémoire (écart {gap:.2e}).")
    scores.to_parquet(VALID_SCORES_PATH, index=False)

    gain = booster.feature_importance("gain", iteration=booster.best_iteration)
    split = booster.feature_importance("split", iteration=booster.best_iteration)
    fi = pd.DataFrame({"feature": booster.feature_name(), "gain": gain, "split": split})
    fi = fi.sort_values("gain", ascending=False, ignore_index=True)
    fi["gain_share_pct"] = 100 * fi["gain"] / fi["gain"].sum()
    fi["rank"] = np.arange(1, len(fi) + 1)
    fi.to_csv(IMPORTANCE_PATH, index=False, encoding="utf-8")

    summary = {
        "model": "LightGBM challenger (Phase 4a)",
        "lightgbm_version": lgb.__version__,
        "params": {**variant_params[chosen], "num_boost_round_max": NUM_BOOST_ROUND,
                   "early_stopping_rounds": EARLY_STOPPING},
        "chosen_variant": chosen,
        "choice_rule": f"AUC valid max, sauf Brier valid > {BRIER_TOLERANCE:.0%} de l'autre variante",
        "choice_reason": reason,
        "scale_pos_weight_value": round(spw, 5),
        "best_iteration": results[chosen]["best_iteration"],
        "metrics": {"train": results[chosen]["train"], "valid": results[chosen]["valid"]},
        "variants": results,
        "ablation_ext_source": {
            "removed_features": EXT_FEATURES,
            "n_features": len(feats_no_ext),
            **res_no_ext,
            "delta_valid_auc": round(d_auc, 5),
            "delta_valid_gini": round(d_gini, 5),
        },
        "n_train": int(len(y_tr)), "n_valid": int(len(y_va)),
        "n_features": len(FEATURES),
        "categorical_features": list(categories),
        "features": FEATURES,
        "note": "Validation utilisée pour l'early stopping et le choix de variante : métriques valid "
                "légèrement optimistes ; mesure finale sur le test scellé (D15).",
    }

    if not args.skip_shap:
        t = time.perf_counter()
        Xs = shap_sample(X_va)
        expl, add_gap = compute_shap(booster, Xs)
        pd_s = booster.predict(Xs, num_iteration=booster.best_iteration)
        imp = shap_importance(expl)
        imp.to_csv(SHAP_IMPORTANCE_PATH, index=False, encoding="utf-8")
        make_shap_figures(expl, Xs, pd_s, imp, categories)
        cases = individual_cases(pd_s)
        summary["shap"] = {
            "sample_size": len(Xs), "seed": RANDOM_STATE, "additivity_max_gap": add_gap,
            "top5": imp["feature"].head(5).tolist(),
            "cases": {k: {"SK_ID_CURR": int(valid["SK_ID_CURR"].iloc[Xs.index[v]]), "pd": round(float(pd_s[v]), 5)}
                      for k, v in cases.items()},
        }
        print(f"[SHAP] n={len(Xs)} · top 5 : {', '.join(summary['shap']['top5'])} ({time.perf_counter() - t:.0f}s)")

    METRICS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    m = results[chosen]
    for s in ("train", "valid"):
        print(f"[{s}] AUC {m[s]['auc']:.4f} · Gini {m[s]['gini']:.4f} · KS {m[s]['ks']:.4f} · Brier {m[s]['brier']:.4f}")
    print(f"[fichiers] {MODEL_PATH.name}, {MODEL_NO_EXT_PATH.name}, {VALID_SCORES_PATH.name}, "
          f"{METRICS_PATH.name}, {IMPORTANCE_PATH.name}" + ("" if args.skip_shap else f", {SHAP_IMPORTANCE_PATH.name}, 05_*.png"))
    print(f"[durée] {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
