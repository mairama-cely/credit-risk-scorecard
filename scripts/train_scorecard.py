"""Phase 3c–3e — Binning WoE / IV, sélection des variables, régression logistique et grille de score.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/train_scorecard.py            # chaîne complète
    .venv\\Scripts\\python.exe scripts/train_scorecard.py --report   # régénère seulement le rapport

Décisions appliquées (cahier des charges, §12) :
D16 candidates = variables au statut « candidate » de CATALOG (build_feature_catalog.py).
D17 BinningProcess d'optbinning ajusté sur le train seul : tendance monotone automatique
    (« auto_asc_desc ») pour les numériques, au moins 5 % des individus par classe, manquants
    dans une classe à part (WoE empirique), catégorielles regroupées selon le taux de défaut.
D18 IV < 0,02 exclue ; IV > 0,5 conservée mais signalée.
D19 Corrélation des WoE > 0,7 → on garde l'IV le plus élevé ; puis VIF > 5 retiré itérativement ;
    au plus 20 variables (IV décroissant).
D20 Logit non pondéré (statsmodels) sur les WoE du train ; retrait itératif p > 0,05 puis des
    coefficients de signe incohérent. Convention optbinning vérifiée : WoE = ln(%non-défauts /
    %défauts), donc WoE élevé = risque faible et tous les coefficients attendus < 0 (cible = défaut).
D21 600 points pour des odds 50:1 (bons:mauvais), PDO = 20 ; score élevé = risque faible.
    factor = PDO / ln 2 ; offset = 600 − factor · ln 50 ;
    points(var j, classe i) = round(−factor · (b_j · WoE_ij + b_0 / n) + offset / n).
D22 Artefacts non versionnés dans models/ ; tableaux versionnés dans output/tables/.

Le test n'est jamais chargé (load_split refuse le test, D15). Validation : métriques seulement.

Aussi importé par les notebooks 03 et 04 : score_frame(), load_artifacts(), prepare_X(),
binning_table(), discrimination(), ks_curve(), score_bands(), write_report().
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
import time
import warnings
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score, roc_curve

# cvxpy (importé par optbinning) journalise à l'import l'échec éventuel d'un solveur optionnel
# qu'optbinning n'utilise pas (solveur CP d'OR-Tools) : message masqué pendant l'import seulement.
logging.disable(logging.WARNING)
try:
    from optbinning import BinningProcess
finally:
    logging.disable(logging.NOTSET)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_feature_catalog import CAND, CATALOG  # noqa: E402
from config import DB_PATH, DOCS_DIR, MODELS_DIR, PROJECT_ROOT, TABLES_DIR, ensure_dirs  # noqa: E402
from make_splits import load_split  # noqa: E402

VERSION = "0.4.0"

# --- Paramètres (D17 à D21) ---
MIN_BIN_SIZE = 0.05
MONOTONIC_TREND = "auto_asc_desc"
IV_MIN, IV_FLAG = 0.02, 0.5
CORR_MAX, VIF_MAX, MAX_VARS = 0.7, 5.0, 20
P_MAX = 0.05
EXPECTED_SIGN = -1          # convention optbinning : WoE élevé = risque faible → coefficient < 0
BASE_SCORE, BASE_ODDS, PDO = 600, 50, 20
AUC_GAP_MAX = 0.02
METRIC_MISSING = "empirical"  # WoE de la classe « Missing » apprise sur le train (pas 0)

# --- Artefacts ---
BINNING_PKL = MODELS_DIR / "binning_process.pkl"
LOGIT_PKL = MODELS_DIR / "scorecard_logit.pkl"
SELECTED_JSON = MODELS_DIR / "scorecard_selected_vars.json"
VALID_SCORES = MODELS_DIR / "scorecard_valid_scores.parquet"
IV_TABLE = TABLES_DIR / "iv_table.csv"
SCORECARD_TABLE = TABLES_DIR / "scorecard_table.csv"
METRICS_JSON = TABLES_DIR / "scorecard_metrics.json"
REPORT_MD = DOCS_DIR / "scorecard_report.md"

FACTOR = PDO / np.log(2)
OFFSET = BASE_SCORE - FACTOR * np.log(BASE_ODDS)


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
def candidate_columns(con: duckdb.DuckDBPyConnection) -> tuple[list[str], list[str]]:
    """Candidates D16 dans l'ordre de la table, et sous-liste des catégorielles (VARCHAR)."""
    desc = con.execute("DESCRIBE model_table_train").df()
    cand = [c for c in desc["column_name"] if CATALOG[c][3] == CAND]
    cat = desc.loc[desc["column_type"].eq("VARCHAR") & desc["column_name"].isin(cand), "column_name"].tolist()
    return cand, cat


def prepare_X(df: pd.DataFrame, variables: list[str], categorical: list[str]) -> pd.DataFrame:
    """Types attendus par optbinning : catégorielles en object (NaN), le reste en float (NaN)."""
    cols = {}
    for c in variables:
        s = df[c]
        if c in categorical:
            cols[c] = s.astype(object).where(s.notna(), np.nan)
        else:
            cols[c] = s.astype("Float64").astype(float)
    return pd.DataFrame(cols, index=df.index)


# ---------------------------------------------------------------------------
# 3c — Binning et IV
# ---------------------------------------------------------------------------
def fit_binning(X: pd.DataFrame, y: np.ndarray, categorical: list[str]) -> BinningProcess:
    params = {c: {"monotonic_trend": MONOTONIC_TREND} for c in X.columns if c not in categorical}
    bp = BinningProcess(
        variable_names=list(X.columns),
        categorical_variables=categorical,
        min_bin_size=MIN_BIN_SIZE,
        binning_fit_params=params,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bp.fit(X, y)
    return bp


def binning_table(bp: BinningProcess, var: str) -> pd.DataFrame:
    """Table de binning optbinning d'une variable, sans la ligne Totals (classe Special incluse)."""
    bt = bp.get_binned_variable(var).binning_table.build()
    bt = bt.drop(index="Totals").reset_index(drop=True)
    bt["Bin"] = bt["Bin"].map(lambda b: ", ".join(map(str, b)) if isinstance(b, (list, np.ndarray)) else str(b))
    return bt


def woe_trend(bt: pd.DataFrame, is_cat: bool) -> tuple[bool, str]:
    """Monotonie du WoE sur les classes régulières (hors Special et Missing)."""
    reg = bt[~bt["Bin"].isin(["Special", "Missing"])]
    w = reg["WoE"].astype(float).to_numpy()
    if len(w) <= 1:
        return True, "constant"
    d = np.diff(w)
    if is_cat:
        return bool((d >= 0).all() or (d <= 0).all()), "catégorielle (ordonnée par taux)"
    if (d > 0).all():
        return True, "croissant"      # WoE ↑ → risque ↓ quand la variable ↑
    if (d < 0).all():
        return True, "décroissant"    # WoE ↓ → risque ↑ quand la variable ↑
    return False, "non monotone"


def iv_table_base(bp: BinningProcess, variables: list[str], categorical: list[str]) -> pd.DataFrame:
    summ = bp.summary().set_index("name")
    rows = []
    for v in variables:
        bt = binning_table(bp, v)
        is_cat = v in categorical
        mono, trend = woe_trend(bt, is_cat)
        n_reg = int((~bt["Bin"].isin(["Special", "Missing"])).sum())
        miss = bt.loc[bt["Bin"].eq("Missing"), "Count"]
        sense = "—"
        if not is_cat and trend in ("croissant", "décroissant"):
            sense = "↓" if trend == "croissant" else "↑"
        rows.append({
            "variable": v,
            "source": CATALOG[v][0],
            "dtype": "categorical" if is_cat else "numerical",
            "iv": float(summ.loc[v, "iv"]),
            "gini_univ": float(summ.loc[v, "gini"]),
            "n_bins": n_reg,
            "missing_bin_count": int(miss.iloc[0]) if len(miss) else 0,
            "monotone": mono,
            "woe_trend": trend,
            "expected_sense": CATALOG[v][2],
            "observed_sense": sense,
            "optb_status": str(summ.loc[v, "status"]),
            "iv_gt_0_5": float(summ.loc[v, "iv"]) > IV_FLAG,
        })
    t = pd.DataFrame(rows).sort_values(["iv", "variable"], ascending=[False, True], ignore_index=True)
    t["status"] = "selected"
    t["exclusion_reason"] = ""
    t["vif"] = np.nan
    return t


def transform_woe(bp: BinningProcess, X: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    out = {}
    for v in variables:
        out[v] = bp.get_binned_variable(v).transform(
            X[v].to_numpy(), metric="woe", metric_missing=METRIC_MISSING, metric_special=0
        )
    return pd.DataFrame(out, index=X.index)


# ---------------------------------------------------------------------------
# 3d — Sélection
# ---------------------------------------------------------------------------
def vif_values(W: pd.DataFrame) -> pd.Series:
    """VIF_j = diag(R⁻¹) (R : matrice de corrélation) = VIF d'une régression avec constante."""
    r = np.corrcoef(W.to_numpy(), rowvar=False)
    return pd.Series(np.diag(np.linalg.inv(r)), index=W.columns)


def select_variables(t: pd.DataFrame, W: pd.DataFrame) -> tuple[list[str], dict[str, int]]:
    """Applique D18 (IV) puis D19 (corrélation, VIF, plafond) ; complète t en place."""
    funnel = {"candidates": len(t)}
    excl = t["iv"] < IV_MIN
    t.loc[excl, ["status", "exclusion_reason"]] = ["excluded", "iv_low"]
    kept = t.loc[~excl, "variable"].tolist()  # déjà trié par IV décroissant
    funnel["iv_ge_0_02"] = len(kept)

    corr = W[kept].corr().abs()
    retained: list[str] = []
    for v in kept:
        hit = [r for r in retained if corr.loc[v, r] > CORR_MAX]
        if hit:
            t.loc[t["variable"].eq(v), ["status", "exclusion_reason"]] = ["excluded", f"corr_with_{hit[0]}"]
        else:
            retained.append(v)
    funnel["after_corr"] = len(retained)

    while True:
        vif = vif_values(W[retained])
        worst = vif.idxmax()
        if vif[worst] <= VIF_MAX:
            break
        t.loc[t["variable"].eq(worst), ["status", "exclusion_reason", "vif"]] = ["excluded", "vif", vif[worst]]
        retained.remove(worst)
    funnel["after_vif"] = len(retained)

    for v in retained[MAX_VARS:]:
        t.loc[t["variable"].eq(v), ["status", "exclusion_reason"]] = ["excluded", "cap20"]
    retained = retained[:MAX_VARS]
    funnel["after_cap20"] = len(retained)
    return retained, funnel


# ---------------------------------------------------------------------------
# 3e — Régression et grille
# ---------------------------------------------------------------------------
def fit_logit(W: pd.DataFrame, y: np.ndarray, variables: list[str], t: pd.DataFrame):
    """Retrait itératif : p > 0,05 d'abord (p maximale), puis signe incohérent (p maximale)."""
    variables = list(variables)
    while True:
        res = sm.Logit(y, sm.add_constant(W[variables], has_constant="add")).fit(disp=0, maxiter=200)
        p = res.pvalues.drop("const")
        coef = res.params.drop("const")
        if (p > P_MAX).any():
            v, reason = p.idxmax(), "pvalue"
        elif (np.sign(coef) != EXPECTED_SIGN).any():
            bad = coef.index[np.sign(coef) != EXPECTED_SIGN]
            v, reason = p[bad].idxmax(), "sign"
        else:
            return res, variables
        t.loc[t["variable"].eq(v), ["status", "exclusion_reason"]] = ["excluded", reason]
        variables.remove(v)


def points_from_woe(woe: np.ndarray, coef: float, intercept: float, n: int) -> np.ndarray:
    return np.round(-FACTOR * (coef * woe + intercept / n) + OFFSET / n).astype(int)


def pd_from_score(score) -> np.ndarray:
    """PD implicite d'un score : odds(bon:mauvais) = exp((score − offset) / factor)."""
    return 1.0 / (1.0 + np.exp((np.asarray(score, dtype=float) - OFFSET) / FACTOR))


def build_scorecard_table(bp: BinningProcess, res, variables: list[str]) -> pd.DataFrame:
    n, b0 = len(variables), float(res.params["const"])
    parts = []
    for v in variables:
        bt = binning_table(bp, v)
        bt = bt[bt["Bin"].ne("Special")]
        woe = bt["WoE"].astype(float).to_numpy()
        parts.append(pd.DataFrame({
            "variable": v,
            "bin": bt["Bin"].to_numpy(),
            "count": bt["Count"].astype(int).to_numpy(),
            "count_pct": bt["Count (%)"].astype(float).to_numpy(),
            "event_rate": bt["Event rate"].astype(float).to_numpy(),
            "woe": woe,
            "points": points_from_woe(woe, float(res.params[v]), b0, n),
        }))
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------
def discrimination(y, score) -> dict[str, float]:
    """AUC, Gini, KS d'un score où une valeur élevée = risque faible."""
    y = np.asarray(y)
    risk = -np.asarray(score, dtype=float)
    auc = roc_auc_score(y, risk)
    fpr, tpr, _ = roc_curve(y, risk)
    return {"auc": float(auc), "gini": float(2 * auc - 1), "ks": float(np.max(tpr - fpr))}


def ks_curve(y, score) -> pd.DataFrame:
    """Répartitions cumulées des mauvais et des bons par score croissant (pour la courbe KS)."""
    d = pd.DataFrame({"score": np.asarray(score), "bad": np.asarray(y)}).sort_values("score")
    g = d.groupby("score")["bad"].agg(n="size", bad="sum")
    g["good"] = g["n"] - g["bad"]
    g["cum_bad"] = g["bad"].cumsum() / g["bad"].sum()
    g["cum_good"] = g["good"].cumsum() / g["good"].sum()
    g["gap"] = g["cum_bad"] - g["cum_good"]
    return g.reset_index()


def score_bands(score, y, pd_hat=None, q: int = 10) -> pd.DataFrame:
    """Taux de défaut observé (et PD moyenne) par tranche de score (quantiles)."""
    d = pd.DataFrame({"score": np.asarray(score), "y": np.asarray(y)})
    if pd_hat is not None:
        d["pd"] = np.asarray(pd_hat)
    d["tranche"] = pd.qcut(d["score"], q=q, duplicates="drop")
    agg = {"n": ("y", "size"), "defauts": ("y", "sum"), "taux_defaut": ("y", "mean"),
           "score_min": ("score", "min"), "score_max": ("score", "max")}
    if pd_hat is not None:
        agg["pd_moyenne"] = ("pd", "mean")
    return d.groupby("tranche", observed=True).agg(**agg).reset_index()


# ---------------------------------------------------------------------------
# Scoring réutilisable (Phase 4 : test ; Phase 5 : restitution)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_artifacts() -> tuple[BinningProcess, object, dict]:
    with open(BINNING_PKL, "rb") as f:
        bp = pickle.load(f)
    with open(LOGIT_PKL, "rb") as f:
        res = pickle.load(f)
    meta = json.loads(SELECTED_JSON.read_text(encoding="utf-8"))
    return bp, res, meta


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Score entier (somme des points de la grille) et PD du logit pour chaque ligne de df.

    df doit contenir SK_ID_CURR et les variables retenues (colonnes de model_table_*).
    Renvoie un DataFrame [SK_ID_CURR, score, pd] dans l'ordre de df.
    """
    bp, res, meta = load_artifacts()
    variables, categorical = meta["variables"], meta["categorical"]
    X = prepare_X(df, variables, [c for c in categorical if c in variables])
    W = transform_woe(bp, X, variables)
    b0, n = float(res.params["const"]), len(variables)
    score = np.zeros(len(df), dtype=int)
    for v in variables:
        score += points_from_woe(W[v].to_numpy(), float(res.params[v]), b0, n)
    pd_hat = res.predict(sm.add_constant(W[variables], has_constant="add")).to_numpy()
    return pd.DataFrame({"SK_ID_CURR": df["SK_ID_CURR"].to_numpy(), "score": score, "pd": pd_hat})


# ---------------------------------------------------------------------------
# Rapport (aucun chiffre saisi à la main)
# ---------------------------------------------------------------------------
def _f(x: float, d: int = 4) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _p(x: float) -> str:
    return "< 1e-300" if x == 0 else f"{x:.2e}".replace(".", ",")


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


def write_report() -> Path:
    m = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    iv = pd.read_csv(IV_TABLE)
    sc = pd.read_csv(SCORECARD_TABLE)
    fu, s = m["funnel"], m["scaling"]
    tr, va = m["metrics"]["train"], m["metrics"]["valid"]
    reasons = iv.loc[iv["status"].eq("excluded"), "exclusion_reason"].str.replace(r"^corr_with_.*", "corr", regex=True)
    rc = reasons.value_counts()
    flagged = iv[iv["iv_gt_0_5"]]
    nonmono = iv[~iv["monotone"]]

    L = [
        "# Rapport de la grille de score — Phase 3 (3c à 3e)",
        "",
        f"> Version {VERSION}. Généré par `scripts/train_scorecard.py` (fonction `write_report`) à partir de "
        "`output/tables/scorecard_metrics.json`, `iv_table.csv` et `scorecard_table.csv`. "
        "Aucun chiffre n'est saisi à la main. Échantillons : train (ajustement) et validation (contrôle) ; "
        "**le test n'a pas été lu** (D15).",
        "",
        "## 1. Méthode",
        "",
        f"- **Candidates (D16)** : {fu['candidates']} variables au statut « candidate » du catalogue.",
        f"- **Binning (D17)** : `BinningProcess` d'optbinning {m['versions']['optbinning']}, ajusté sur le train "
        f"({_n(m['n_train'])} demandes) ; tendance `{MONOTONIC_TREND}` pour les numériques, au moins "
        f"{_f(100 * MIN_BIN_SIZE, 0)} % des individus par classe, manquants dans une classe à part (WoE empirique), "
        "catégorielles regroupées selon le taux de défaut.",
        f"- **Convention WoE** : WoE = ln(%non-défauts / %défauts) ; un WoE élevé correspond à un risque faible, "
        "donc tous les coefficients du logit (cible = défaut) doivent être **négatifs** (D20).",
        f"- **Filtres (D18, D19)** : IV < {_f(IV_MIN, 2)} exclue ; IV > {_f(IV_FLAG, 1)} conservée mais signalée ; "
        f"corrélation des WoE > {_f(CORR_MAX, 1)} → IV le plus élevé conservé ; VIF > {VIF_MAX:g} retiré itérativement ; "
        f"au plus {MAX_VARS} variables.",
        f"- **Régression (D20)** : logit non pondéré (statsmodels {m['versions']['statsmodels']}) ; retrait itératif "
        f"des p-valeurs > {_f(P_MAX, 2)} puis des signes incohérents.",
        f"- **Mise à l'échelle (D21)** : {s['base_score']} points pour des odds {s['base_odds']}:1 (bons:mauvais), "
        f"PDO = {s['pdo']} ; factor = {_f(s['factor'])}, offset = {_f(s['offset'])} ; l'intercept est réparti à parts "
        "égales entre les variables ; points arrondis à l'entier ; score élevé = risque faible.",
        "",
        "## 2. Entonnoir de sélection",
        "",
        "| Étape | Variables restantes |",
        "|---|---:|",
        f"| Candidates (D16) | {fu['candidates']} |",
        f"| IV ≥ {_f(IV_MIN, 2)} (D18) | {fu['iv_ge_0_02']} |",
        f"| Corrélation des WoE ≤ {_f(CORR_MAX, 1)} (D19) | {fu['after_corr']} |",
        f"| VIF ≤ {VIF_MAX:g} (D19) | {fu['after_vif']} |",
        f"| Plafond {MAX_VARS} variables (D19) | {fu['after_cap20']} |",
        f"| p ≤ {_f(P_MAX, 2)} et signe cohérent (D20) | {fu['final']} |",
        "",
        "Motifs d'exclusion : " + " ; ".join(f"`{k}` {v}" for k, v in rc.items()) + ".",
        "",
        "## 3. Variables retenues",
        "",
        "| Variable | IV | Classes | Monotone | Coefficient | p-valeur | VIF | Points min | Points max |",
        "|---|---:|---:|:---:|---:|---:|---:|---:|---:|",
    ]
    for v in m["variables"]:
        r = iv.set_index("variable").loc[v]
        pts = sc.loc[sc["variable"].eq(v), "points"]
        L.append(
            f"| `{v}` | {_f(r['iv'])} | {int(r['n_bins'])} | {'oui' if r['monotone'] else 'non'} | "
            f"{_f(m['coefficients'][v])} | {_p(m['pvalues'][v])} | {_f(m['vif'][v], 2)} | {int(pts.min())} | {int(pts.max())} |"
        )
    L += [
        "",
        f"Intercept : {_f(m['coefficients']['const'])} (p {_p(m['pvalues']['const']) if m['pvalues']['const'] == 0 else '= ' + _p(m['pvalues']['const'])}). "
        f"Score théorique : de {m['score_range']['min']} à {m['score_range']['max']} points.",
        "",
        "## 4. Performance",
        "",
        "| Échantillon | Effectif | AUC | Gini | KS |",
        "|---|---:|---:|---:|---:|",
        f"| Train | {_n(m['n_train'])} | {_f(tr['auc'])} | {_f(tr['gini'])} | {_f(tr['ks'])} |",
        f"| Validation | {_n(m['n_valid'])} | {_f(va['auc'])} | {_f(va['gini'])} | {_f(va['ks'])} |",
        "",
        f"Écart d'AUC train − validation : **{_f(m['auc_gap'])}** (seuil {_f(AUC_GAP_MAX, 2)}) → "
        f"**{'conforme' if m['auc_gap_pass'] else 'NON conforme'}**. "
        "Métriques calculées sur le score entier de la grille.",
        "",
        f"Cohérence score ↔ PD : à {s['base_score']} points, PD = {_f(m['mapping_check']['pd_at_base'], 5)} "
        f"(= 1 / {s['base_odds'] + 1}) ; +{s['pdo']} points doublent les odds "
        f"(rapport mesuré {_f(m['mapping_check']['odds_ratio_per_pdo'], 3)}). Écart entre la PD implicite du score "
        f"arrondi et la PD du logit (validation) : moyen {_f(m['mapping_check']['mean_abs_pd_diff_valid'], 5)}, "
        f"maximal {_f(m['mapping_check']['max_abs_pd_diff_valid'], 5)} (cumul des arrondis de {m['n_vars']} variables). "
        f"AUC de validation calculée sur la PD du logit : {_f(m['mapping_check']['auc_valid_logit_pd'])}.",
        "",
        "## 5. Signalements",
        "",
    ]
    if len(flagged):
        L.append(f"- **IV > {_f(IV_FLAG, 1)} (D18, revue manuelle)** : " + " ; ".join(
            f"`{r.variable}` (IV {_f(r.iv)}, {'retenue' if r.status == 'selected' else 'exclue : ' + r.exclusion_reason})"
            for r in flagged.itertuples()) + ".")
    else:
        L.append(f"- Aucune variable à IV > {_f(IV_FLAG, 1)}.")
    L.append(f"- **WoE non monotone** : {len(nonmono)} variable(s) sur {len(iv)}"
             + (" (" + ", ".join(f"`{v}`" for v in nonmono['variable']) + ")" if 0 < len(nonmono) <= 15 else "") + ".")
    sel = iv[iv["status"].eq("selected") & iv["expected_sense"].isin(["↑", "↓"]) & iv["observed_sense"].isin(["↑", "↓"])]
    contra = sel[sel["expected_sense"] != sel["observed_sense"]]
    L.append(f"- **Sens a priori du catalogue vs sens observé (variables retenues numériques)** : "
             f"{len(sel) - len(contra)} concordant(s) sur {len(sel)} comparables"
             + (" ; discordant(s) : " + ", ".join(f"`{v}`" for v in contra['variable']) if len(contra) else "") + ".")
    L += [
        "",
        "## 6. Limites",
        "",
        "- Régression non pondérée : la PD reflète le taux de défaut du train ; la calibration sera contrôlée en Phase 4.",
        "- La sélection (corrélation, VIF, plafond) est gloutonne et ordonnée par IV : une autre combinaison de "
        "variables pourrait donner une performance voisine.",
        "- Arrondi des points à l'entier : écart entre la PD implicite du score et celle du logit (§4).",
        "- Les variables `EXT_SOURCE_*` sont des scores externes opaques ; leur poids sera mesuré par ablation (D8, Phase 4).",
        "- Performance mesurée sur la validation seulement ; le test reste scellé jusqu'à la Phase 4.",
        "",
    ]
    REPORT_MD.write_text("\n".join(L), encoding="utf-8")
    return REPORT_MD


# ---------------------------------------------------------------------------
# Chaîne complète
# ---------------------------------------------------------------------------
def run() -> None:
    import optbinning
    import sklearn
    import statsmodels

    t0 = time.perf_counter()
    ensure_dirs()
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH} introuvable.")
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        cand, cat = candidate_columns(con)
        train = load_split(con, "train", ["SK_ID_CURR", "TARGET", *cand])
        valid = load_split(con, "valid", ["SK_ID_CURR", "TARGET", *cand])
    y_tr, y_va = train["TARGET"].to_numpy(), valid["TARGET"].to_numpy()
    log(f"[données] train {len(train):,} · valid {len(valid):,} · candidates {len(cand)} (dont {len(cat)} catégorielles)")

    X_tr = prepare_X(train, cand, cat)
    bp = fit_binning(X_tr, y_tr, cat)
    t = iv_table_base(bp, cand, cat)
    log(f"[3c] binning ajusté ({time.perf_counter() - t0:.0f} s) · non monotones {int((~t['monotone']).sum())} · "
        f"IV > {IV_FLAG} : {int(t['iv_gt_0_5'].sum())}")

    keep_iv = t.loc[t["iv"] >= IV_MIN, "variable"].tolist()
    W_tr = transform_woe(bp, X_tr, keep_iv)
    retained, funnel = select_variables(t, W_tr)
    log(f"[3d] IV≥{IV_MIN}: {funnel['iv_ge_0_02']} → corr: {funnel['after_corr']} → VIF: {funnel['after_vif']} "
        f"→ plafond: {funnel['after_cap20']}")

    res, final = fit_logit(W_tr, y_tr, retained, t)
    funnel["final"] = len(final)
    vif_final = vif_values(W_tr[final])
    t.loc[t["variable"].isin(final), "vif"] = t.loc[t["variable"].isin(final), "variable"].map(vif_final)
    log(f"[3e] logit : {len(final)} variables · coefficients tous < 0 : {bool((res.params.drop('const') < 0).all())}")

    # Persistance des artefacts (models/ non versionné)
    with open(BINNING_PKL, "wb") as f:
        pickle.dump(bp, f)
    params, pvalues = res.params.copy(), res.pvalues.copy()
    res.remove_data()
    with open(LOGIT_PKL, "wb") as f:
        pickle.dump(res, f)
    SELECTED_JSON.write_text(json.dumps({"variables": final, "categorical": [c for c in cat if c in final]},
                                        indent=2, ensure_ascii=False), encoding="utf-8")
    load_artifacts.cache_clear()

    sc = build_scorecard_table(bp, res, final)
    s_tr, s_va = score_frame(train), score_frame(valid)
    # Contrôle : chaque point attribué figure dans la grille de sa variable (train)
    W_check = transform_woe(bp, prepare_X(train, final, cat), final)
    for v in final:
        pts = points_from_woe(W_check[v].to_numpy(), float(res.params[v]), float(res.params["const"]), len(final))
        if not set(np.unique(pts)) <= set(sc.loc[sc["variable"].eq(v), "points"]):
            raise RuntimeError(f"Points de {v} absents de la grille.")

    m_tr, m_va = discrimination(y_tr, s_tr["score"]), discrimination(y_va, s_va["score"])
    gap = m_tr["auc"] - m_va["auc"]
    pd_imp = pd_from_score(s_va["score"])
    mapping = {
        "pd_at_base": float(pd_from_score(BASE_SCORE)),
        "odds_at_base": float((1 - pd_from_score(BASE_SCORE)) / pd_from_score(BASE_SCORE)),
        "odds_ratio_per_pdo": float(
            ((1 - pd_from_score(BASE_SCORE + PDO)) / pd_from_score(BASE_SCORE + PDO))
            / ((1 - pd_from_score(BASE_SCORE)) / pd_from_score(BASE_SCORE))),
        "max_abs_pd_diff_valid": float(np.max(np.abs(pd_imp - s_va["pd"].to_numpy()))),
        "mean_abs_pd_diff_valid": float(np.mean(np.abs(pd_imp - s_va["pd"].to_numpy()))),
        "auc_valid_logit_pd": float(roc_auc_score(y_va, s_va["pd"])),
    }
    rng = sc.groupby("variable")["points"].agg(["min", "max"]).sum()

    metrics = {
        "version": VERSION,
        "n_train": int(len(train)), "n_valid": int(len(valid)),
        "default_rate_train": float(y_tr.mean()), "default_rate_valid": float(y_va.mean()),
        "metrics": {"train": m_tr, "valid": m_va},
        "auc_gap": float(gap), "auc_gap_max": AUC_GAP_MAX, "auc_gap_pass": bool(gap < AUC_GAP_MAX),
        "n_vars": len(final), "variables": final,
        "coefficients": {k: float(v) for k, v in params.items()},
        "pvalues": {k: float(v) for k, v in pvalues.items()},
        "vif": {k: float(v) for k, v in vif_final.items()},
        "funnel": funnel,
        "iv_flagged_gt_0_5": t.loc[t["iv_gt_0_5"], "variable"].tolist(),
        "scaling": {"base_score": BASE_SCORE, "base_odds": BASE_ODDS, "pdo": PDO,
                    "factor": float(FACTOR), "offset": float(OFFSET), "intercept_split": "equal",
                    "rounding": "integer per bin", "higher_score": "lower risk"},
        "score_range": {"min": int(rng["min"]), "max": int(rng["max"])},
        "mapping_check": mapping,
        "params": {"min_bin_size": MIN_BIN_SIZE, "monotonic_trend": MONOTONIC_TREND, "iv_min": IV_MIN,
                   "iv_flag": IV_FLAG, "corr_max": CORR_MAX, "vif_max": VIF_MAX, "max_vars": MAX_VARS,
                   "p_max": P_MAX, "metric_missing": METRIC_MISSING},
        "versions": {"optbinning": optbinning.__version__, "statsmodels": statsmodels.__version__,
                     "sklearn": sklearn.__version__, "pandas": pd.__version__},
    }

    t.to_csv(IV_TABLE, index=False, float_format="%.6f")
    sc.to_csv(SCORECARD_TABLE, index=False, float_format="%.6f")
    METRICS_JSON.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    s_va.to_parquet(VALID_SCORES, index=False)
    write_report()

    log(f"[métriques] train AUC {m_tr['auc']:.4f} Gini {m_tr['gini']:.4f} KS {m_tr['ks']:.4f} | "
        f"valid AUC {m_va['auc']:.4f} Gini {m_va['gini']:.4f} KS {m_va['ks']:.4f} | "
        f"écart {gap:.4f} → {'OK' if gap < AUC_GAP_MAX else 'ÉCHEC'}")
    log(f"[variables] {', '.join(final)}")
    for p in (IV_TABLE, SCORECARD_TABLE, METRICS_JSON, REPORT_MD, BINNING_PKL, LOGIT_PKL, SELECTED_JSON, VALID_SCORES):
        log(f"[écrit] {p.relative_to(PROJECT_ROOT).as_posix()}")
    log(f"[durée] {time.perf_counter() - t0:.0f} s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="régénère seulement docs/scorecard_report.md")
    args = ap.parse_args()
    if args.report:
        log(f"[écrit] {write_report().relative_to(PROJECT_ROOT).as_posix()}")
    else:
        run()


if __name__ == "__main__":
    main()
