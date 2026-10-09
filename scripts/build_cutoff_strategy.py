"""Phase 4c — Stratégie de seuils (cut-off) sur le score de la grille, et rapport de performance.

Usage (depuis la racine du projet, après scripts/evaluate_models.py) :
    .venv\\Scripts\\python.exe scripts/build_cutoff_strategy.py            # scénarios + rapport
    .venv\\Scripts\\python.exe scripts/build_cutoff_strategy.py --report   # régénère seulement le rapport

Principe : les seuils sont CHOISIS sur la validation et ÉVALUÉS sur le test.
Le test n'est pas relu dans la base : ce script lit models/all_scores.parquet, écrit par
evaluate_models.py, seul script autorisé à lire le test (D15).

Scénarios (taux d'acceptation cibles sur la validation) :
- prudent    60 % : refuse les 40 % de scores les plus bas ;
- équilibré  75 % : refuse le quartile inférieur ;
- croissance 85 % : ne refuse que les 15 % les plus risqués.
Le taux de défaut du portefeuille étant d'environ 8 %, la croissance (85 %) ne refuse guère plus de
deux fois la part des mauvais payeurs ; en deçà de 60 %, on refuserait une majorité de bons clients
(voir colonne good_refused_pct). Les trois cibles encadrent donc la zone utile.

Zones : accepter si score ≥ seuil + 10 ; revoir (analyse manuelle) si seuil − 10 ≤ score < seuil + 10 ;
refuser si score < seuil − 10. 10 points = PDO / 2 : les odds varient d'un facteur √2 de part et d'autre.
Les taux d'acceptation, taux de défaut et pertes sont calculés à la décision binaire « score ≥ seuil »
(les dossiers en revue sont tranchés par le seuil).

Perte attendue : EL = PD × LGD × EAD, EAD = AMT_CREDIT, PD = PD du logit de la grille, LGD = 45 %
(sensibilité 35 / 45 / 55 %). Comme la LGD est constante, les PARTS de perte évitée n'en dépendent pas.

Règle de recommandation (sur la validation, sans paramètre de marge) : le scénario qui maximise
« part de la perte attendue évitée − part des bons clients refusés » (séparation pondérée par l'EL,
équivalent d'un KS en montant). Elle pèse à égalité 1 % de perte évitée et 1 % de bons clients perdus :
avec des données de marge, une règle de rentabilité la remplacerait.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DOCS_DIR, MODELS_DIR, PROJECT_ROOT, TABLES_DIR, ensure_dirs  # noqa: E402

SCENARIOS = {"prudent": 0.60, "equilibre": 0.75, "croissance": 0.85}
SCENARIO_LABELS = {"prudent": "Prudent", "equilibre": "Équilibré", "croissance": "Croissance"}
REVIEW_HALF_WIDTH = 10
LGD_BASE = 0.45
LGD_SENSITIVITY = (0.35, 0.45, 0.55)

ALL_SCORES = MODELS_DIR / "all_scores.parquet"
CUTOFF_SCENARIOS_CSV = TABLES_DIR / "cutoff_scenarios.csv"
SCORE_DECILES_CSV = TABLES_DIR / "score_deciles.csv"
CUTOFF_JSON = TABLES_DIR / "cutoff_strategy.json"
REPORT_MD = DOCS_DIR / "model_performance_report.md"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Choix des seuils (validation uniquement)
# ---------------------------------------------------------------------------
def scenario_cutoffs(valid_score) -> dict[str, dict]:
    """Seuil entier dont le taux d'acceptation (score ≥ seuil) sur la validation est le plus proche de la cible."""
    s = np.asarray(valid_score)
    grid = np.arange(int(s.min()), int(s.max()) + 2)
    approval = np.array([(s >= c).mean() for c in grid])
    out = {}
    for name, target in SCENARIOS.items():
        i = int(np.argmin(np.abs(approval - target)))
        out[name] = {"target_approval": target, "cutoff": int(grid[i]), "valid_approval": float(approval[i])}
    return out


def zone(score, cutoff: int) -> np.ndarray:
    s = np.asarray(score)
    return np.where(s >= cutoff + REVIEW_HALF_WIDTH, "accepter",
                    np.where(s >= cutoff - REVIEW_HALF_WIDTH, "revoir", "refuser"))


def scenario_metrics(df: pd.DataFrame, cutoff: int, lgd: float = LGD_BASE) -> dict:
    """Indicateurs d'un seuil sur un échantillon (colonnes score, pd_scorecard, TARGET, AMT_CREDIT)."""
    acc = df["score"].to_numpy() >= cutoff
    y = df["TARGET"].to_numpy()
    el = df["pd_scorecard"].to_numpy() * lgd * df["AMT_CREDIT"].to_numpy()
    loss_obs = y * lgd * df["AMT_CREDIT"].to_numpy()
    z = zone(df["score"], cutoff)
    goods = y == 0
    return {
        "n": int(len(df)),
        "approval_rate": float(acc.mean()),
        "bad_rate_accepted": float(y[acc].mean()),
        "bad_rate_refused": float(y[~acc].mean()) if (~acc).any() else float("nan"),
        "bads_refused_pct": float((~acc & ~goods).sum() / (~goods).sum()),
        "good_refused_n": int((~acc & goods).sum()),
        "good_refused_pct": float((~acc & goods).sum() / goods.sum()),
        "el_all": float(el.sum()),
        "el_accepted": float(el[acc].sum()),
        "el_avoided": float(el[~acc].sum()),
        "el_avoided_pct": float(el[~acc].sum() / el.sum()),
        "el_accepted_pct_exposure": float(el[acc].sum() / df["AMT_CREDIT"].to_numpy()[acc].sum()),
        "observed_loss_accepted": float(loss_obs[acc].sum()),
        "observed_loss_avoided": float(loss_obs[~acc].sum()),
        "exposure_accepted": float(df["AMT_CREDIT"].to_numpy()[acc].sum()),
        "zone_accept_pct": float((z == "accepter").mean()),
        "zone_review_pct": float((z == "revoir").mean()),
        "zone_refuse_pct": float((z == "refuser").mean()),
        "bad_rate_review": float(y[z == "revoir"].mean()) if (z == "revoir").any() else float("nan"),
    }


def marginal_tranche(df: pd.DataFrame, cutoff: int, prev_cutoff: int | None, lgd: float) -> dict:
    """Tranche acceptée en plus par rapport au scénario plus prudent (cutoff ≤ score < prev_cutoff).

    breakeven_margin = marge nette (en % du montant prêté) qu'un bon crédit doit rapporter pour que
    l'acceptation de la tranche compense sa perte attendue : LGD · Σ PD·EAD / Σ (1 − PD)·EAD.
    """
    if prev_cutoff is None:
        return {"marginal_n": np.nan, "marginal_bad_rate": np.nan, "marginal_pd_mean": np.nan,
                "breakeven_margin": np.nan}
    s = df["score"].to_numpy()
    t = (s >= cutoff) & (s < prev_cutoff)
    p, ead = df["pd_scorecard"].to_numpy()[t], df["AMT_CREDIT"].to_numpy()[t]
    return {"marginal_n": int(t.sum()), "marginal_bad_rate": float(df["TARGET"].to_numpy()[t].mean()),
            "marginal_pd_mean": float(p.mean()),
            "breakeven_margin": float(lgd * (p * ead).sum() / ((1 - p) * ead).sum())}


def recommend(valid: pd.DataFrame, cutoffs: dict[str, dict]) -> tuple[str, dict[str, float]]:
    """Règle documentée : max(part d'EL évitée − part de bons refusés) sur la validation."""
    crit = {}
    for name, c in cutoffs.items():
        m = scenario_metrics(valid, c["cutoff"])
        crit[name] = m["el_avoided_pct"] - m["good_refused_pct"]
    return max(crit, key=crit.get), crit


def decile_table(df: pd.DataFrame, edges: list[float]) -> pd.DataFrame:
    """Déciles de score (bornes = déciles du train), du meilleur score au plus risqué, avec cumuls."""
    d = df.assign(decile=pd.cut(df["score"], bins=edges, labels=False, right=False) + 1)
    g = d.groupby("decile").agg(n=("TARGET", "size"), defaults=("TARGET", "sum"),
                                score_min=("score", "min"), score_max=("score", "max"),
                                pd_mean=("pd_scorecard", "mean")).sort_index(ascending=False)
    g["default_rate"] = g["defaults"] / g["n"]
    g["cum_approval_rate"] = g["n"].cumsum() / g["n"].sum()
    g["cum_bad_rate_accepted"] = g["defaults"].cumsum() / g["n"].cumsum()
    return g.reset_index()


# ---------------------------------------------------------------------------
# Chaîne
# ---------------------------------------------------------------------------
def run() -> None:
    ensure_dirs()
    if not ALL_SCORES.exists():
        raise FileNotFoundError(f"{ALL_SCORES} introuvable : lancer d'abord scripts/evaluate_models.py")
    scores = pd.read_parquet(ALL_SCORES)
    valid = scores[scores["split"].eq("valid")]
    test = scores[scores["split"].eq("test")]
    train = scores[scores["split"].eq("train")]
    log(f"[données] {ALL_SCORES.name} : train {len(train):,} · valid {len(valid):,} · test {len(test):,}")

    cutoffs = scenario_cutoffs(valid["score"])
    reco, crit = recommend(valid, cutoffs)
    for k, c in cutoffs.items():
        log(f"[seuil] {k:<10} cible {c['target_approval']:.0%} → seuil {c['cutoff']} "
            f"(acceptation valid {c['valid_approval']:.1%}) · critère {crit[k]:+.4f}")
    log(f"[recommandation] {reco} (règle : max part EL évitée − part bons refusés, sur la validation)")

    rows = []
    names = list(cutoffs)       # du plus prudent au plus large (seuils décroissants)
    for k, (name, c) in enumerate(cutoffs.items()):
        prev = cutoffs[names[k - 1]]["cutoff"] if k else None
        for split, df in (("valid", valid), ("test", test)):
            for lgd in LGD_SENSITIVITY:
                m = scenario_metrics(df, c["cutoff"], lgd)
                m.update(marginal_tranche(df, c["cutoff"], prev, lgd))
                rows.append({"scenario": name, "target_approval": c["target_approval"], "cutoff": c["cutoff"],
                             "review_low": c["cutoff"] - REVIEW_HALF_WIDTH,
                             "review_high": c["cutoff"] + REVIEW_HALF_WIDTH,
                             "split": split, "lgd": lgd, "recommended": name == reco, **m})
    scen = pd.DataFrame(rows)

    edges = json.loads((TABLES_DIR / "evaluation_metrics.json").read_text(encoding="utf-8"))["decile_edges"]
    dec = pd.concat([decile_table(df, edges).assign(split=s) for s, df in (("valid", valid), ("test", test))],
                    ignore_index=True)

    base_t = scen[(scen["split"] == "test") & (scen["lgd"] == LGD_BASE)].set_index("scenario")
    approve_all_t = scenario_metrics(test, -10**9)
    strategy = {
        "rule": "seuils choisis sur la validation, évalués sur le test",
        "scenarios_target_approval": SCENARIOS,
        "review_half_width_points": REVIEW_HALF_WIDTH,
        "lgd_base": LGD_BASE, "lgd_sensitivity": list(LGD_SENSITIVITY),
        "ead": "AMT_CREDIT", "pd": "PD du logit de la grille",
        "cutoffs": cutoffs,
        "recommendation_rule": "max (part de la perte attendue évitée − part des bons clients refusés) sur la validation",
        "recommendation_criterion_valid": crit,
        "recommended": reco,
        "recommended_test": base_t.loc[reco].drop(["split", "recommended"]).to_dict(),
        "approve_all_test": approve_all_t,
        "n_valid": int(len(valid)), "n_test": int(len(test)),
    }
    strategy["recommended_test"] = {k: (v.item() if hasattr(v, "item") else v)
                                    for k, v in strategy["recommended_test"].items()}

    scen.to_csv(CUTOFF_SCENARIOS_CSV, index=False, float_format="%.6f")
    dec.to_csv(SCORE_DECILES_CSV, index=False, float_format="%.6f")
    CUTOFF_JSON.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")
    r = strategy["recommended_test"]
    log(f"[test] {reco} : acceptation {r['approval_rate']:.1%} · défaut acceptés {r['bad_rate_accepted']:.2%} "
        f"(vs {approve_all_t['bad_rate_accepted']:.2%} sans seuil) · EL évitée {r['el_avoided_pct']:.1%} · "
        f"bons refusés {r['good_refused_pct']:.1%}")
    out = write_report()
    for p in (CUTOFF_SCENARIOS_CSV, SCORE_DECILES_CSV, CUTOFF_JSON, out):
        log(f"[écrit] {p.relative_to(PROJECT_ROOT).as_posix()}")


# ---------------------------------------------------------------------------
# Rapport de performance (aucun chiffre saisi à la main)
# ---------------------------------------------------------------------------
def write_report() -> Path:
    from evaluate_models import (CALIBRATION_CSV, EVAL_JSON, FAIRNESS_CSV, FINAL_COMPARISON_CSV, PSI_CSV,
                                 PSI_MODERATE, PSI_SEVERE, REFUSAL_CSV)
    from train_scorecard import _f, _n

    def pct(x: float, d: int = 1) -> str:
        return _f(100 * x, d) + " %"

    def money(x: float) -> str:
        return _f(x / 1e6, 1) + " M"

    ev = json.loads(EVAL_JSON.read_text(encoding="utf-8"))
    st = json.loads(CUTOFF_JSON.read_text(encoding="utf-8"))
    ch = json.loads((TABLES_DIR / "challenger_metrics.json").read_text(encoding="utf-8"))
    comp = pd.read_csv(FINAL_COMPARISON_CSV)
    cal = pd.read_csv(CALIBRATION_CSV)
    psi = pd.read_csv(PSI_CSV)
    fair = pd.read_csv(FAIRNESS_CSV)
    reasons = pd.read_csv(REFUSAL_CSV)
    scen = pd.read_csv(CUTOFF_SCENARIOS_CSV)
    t = ev["test_metrics"]
    ci = ev["bootstrap"]
    reco = st["recommended"]
    names = {"scorecard": "Grille de score", "lgbm": "LightGBM", "lgbm_no_ext": "LightGBM sans EXT_SOURCE"}

    if ev["dry_run"]:
        opening = ("> **RÉPÉTITION (--dry-run)** : le test n'a PAS été ouvert ; la validation tient lieu de test. "
                   "Chiffres provisoires, à régénérer après l'ouverture du test.")
    else:
        o = ev["test_opening"]
        opening = (f"> **Test scellé (D15)** : lu uniquement par `scripts/evaluate_models.py`, chaque lecture journalisée "
                   f"dans `models/test_access_log.csv` (dernière : {o['timestamp_utc']}, {_n(o['n_rows'])} demandes, "
                   f"empreinte SHA-256 {'conforme' if o['fingerprint_match'] else 'NON conforme'} à `split_meta`). "
                   "Aucun modèle, seuil ni calibrage n'a été ajusté sur le test ; le pipeline étant déterministe, "
                   "chaque exécution redonne les mêmes résultats.")
    L = [
        "# Rapport de performance des modèles — Phase 4 (4b et 4c)",
        "",
        "> Généré par `scripts/build_cutoff_strategy.py` (fonction `write_report`) à partir de "
        "`output/tables/evaluation_metrics.json`, `final_comparison.csv`, `calibration_test.csv`, `psi_table.csv`, "
        "`fairness_table.csv`, `refusal_reasons.csv`, `cutoff_scenarios.csv`, `cutoff_strategy.json` et "
        "`challenger_metrics.json`. Aucun chiffre n'est saisi à la main.",
        "",
        opening,
        "",
        "## 1. Comparaison finale (train / validation / test)",
        "",
        "| Modèle | Échantillon | Effectif | AUC | Gini | KS | Brier |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in comp.itertuples():
        L.append(f"| {names[r.model]} | {r.split} | {_n(int(r.n))} | {_f(r.auc)} | {_f(r.gini)} | {_f(r.ks)} | {_f(r.brier)} |")
    L += [
        "",
        f"Intervalles de confiance à 95 % sur le test (bootstrap, {ci['n_resamples']} rééchantillonnages, "
        f"graine {ci['seed']}, percentiles) :",
        "",
        "| Indicateur | Estimation | IC 95 % |",
        "|---|---:|---:|",
    ]
    for key, lab in (("scorecard_auc", "AUC grille"), ("scorecard_gini", "Gini grille"),
                     ("lgbm_auc", "AUC LightGBM"), ("lgbm_gini", "Gini LightGBM"),
                     ("auc_diff_lgbm_minus_scorecard", "Écart d'AUC LightGBM − grille (apparié)")):
        c = ci[key]
        L.append(f"| {lab} | {_f(c['estimate'])} | [{_f(c['low'])} ; {_f(c['high'])}] |")
    d = ci["auc_diff_lgbm_minus_scorecard"]
    signif = d["low"] > 0 or d["high"] < 0
    L += [
        "",
        f"L'écart d'AUC {'est' if signif else "n'est pas"} significatif au seuil de 5 % "
        f"(l'intervalle {'exclut' if signif else 'contient'} 0). "
        f"Écart de généralisation valid → test : grille {_f(t['scorecard']['auc'] - ev['valid_metrics']['scorecard']['auc'])}, "
        f"LightGBM {_f(t['lgbm']['auc'] - ev['valid_metrics']['lgbm']['auc'])} (AUC).",
        "",
        "## 2. Calibration (test)",
        "",
        "| Modèle | PD moyenne | Taux observé | Brier | Écart absolu moyen par décile | Écart max | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for k in ("scorecard", "lgbm"):
        c = ev["calibration"][k]
        L.append(f"| {names[k]} | {pct(c['mean_pd'], 2)} | {pct(c['default_rate'], 2)} | {_f(c['brier'])} | "
                 f"{_f(100 * c['mean_abs_decile_gap'], 2)} pt | {_f(100 * c['max_abs_decile_gap'], 2)} pt | "
                 f"{'mal calibré' if c['miscalibrated'] else 'calibré'} |")
    cr = ev["calibration"]["criterion"]
    L += [
        "",
        f"Critère : un modèle est jugé mal calibré si l'écart absolu moyen entre PD prédite et taux observé par décile "
        f"dépasse {_f(100 * cr['mean_abs_decile_gap_max'], 1)} pt ou si l'écart max dépasse "
        f"{_f(100 * cr['max_abs_decile_gap_max'], 1)} pt. À titre de contrôle, une régression isotone ajustée sur la "
        "validation (jamais sur le test) donne un Brier de test de "
        + " ; ".join(f"{_f(ev['calibration'][k]['isotonic_valid_brier_test'])} ({names[k]})" for k in ("scorecard", "lgbm"))
        + ".",
        "",
        "Détail par décile de PD : `output/tables/calibration_test.csv`.",
        "",
        "## 3. Stabilité (PSI train → test)",
        "",
    ]
    ps = psi[psi["level"].eq("score")].iloc[0]
    cs = psi[psi["level"].eq("variable")].sort_values("psi", ascending=False)

    def flag(x: float) -> str:
        return "instable" if x > PSI_SEVERE else ("à surveiller" if x > PSI_MODERATE else "stable")

    L += [
        f"- **Score de la grille** (10 tranches = déciles du train) : PSI {_f(ps['psi'])} → {flag(ps['psi'])} "
        f"(train → validation : {_f(ev['psi']['score_train_valid'])}).",
        f"- **Stabilité caractéristique** (classes WoE des {len(cs)} variables retenues) : PSI max "
        f"{_f(cs['psi'].max())} (`{cs.iloc[0]['name']}`) ; {int((cs['psi'] > PSI_MODERATE).sum())} variable(s) > "
        f"{_f(PSI_MODERATE, 2)}, {int((cs['psi'] > PSI_SEVERE).sum())} > {_f(PSI_SEVERE, 2)}.",
        "",
        "Seuils usuels : < 0,10 stable ; 0,10 – 0,25 à surveiller ; > 0,25 instable. Train et test sont issus "
        "d'un même tirage aléatoire (pas de dimension temporelle) : le PSI contrôle ici la cohérence du découpage, "
        "pas la dérive dans le temps.",
        "",
        "## 4. Équité — audit par `CODE_GENDER` (variable exclue du modèle)",
        "",
        f"Seuil appliqué : scénario recommandé (`{reco}`, score ≥ {st['cutoffs'][reco]['cutoff']}). "
        f"Groupe `XNA` ignoré ({ev['fairness']['xna_count_test']} demande(s) au test, "
        f"{ev['fairness']['xna_count_all']} sur l'ensemble des échantillons).",
        "",
        "| Groupe | Effectif | Taux de défaut | Score moyen | AUC grille | AUC LightGBM | Acceptation | Acceptation des bons | Défaut des acceptés |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in fair.itertuples():
        L.append(f"| {r.group} | {_n(int(r.n))} | {pct(r.default_rate, 2)} | {_f(r.mean_score, 1)} | {_f(r.auc_scorecard)} | "
                 f"{_f(r.auc_lgbm)} | {pct(r.approval_rate)} | {pct(r.approval_rate_goods)} | {pct(r.bad_rate_accepted, 2)} |")
    fa = ev["fairness"]
    L += [
        "",
        f"Ratio d'acceptation M / F : {_f(1 / fa['approval_ratio_f_over_m'], 3)} (règle des 4/5 : ≥ 0,80 → "
        f"{'respectée' if 1 / fa['approval_ratio_f_over_m'] >= 0.8 else 'NON respectée'}) ; parmi les bons clients seulement "
        f"(égalité des chances) : {_f(1 / fa['approval_ratio_goods_f_over_m'], 3)}. Écart d'AUC de la grille F − M : "
        f"{_f(fa['auc_gap_f_minus_m_scorecard'])}. Le genre n'entre pas dans le modèle, mais des variables corrélées "
        "(profession, secteur d'emploi) peuvent le refléter. L'écart d'acceptation suit en partie l'écart de taux de défaut "
        "entre groupes, mais il persiste parmi les bons clients : les hommes solvables sont plus souvent refusés. "
        "Point de vigilance, à soumettre à une revue de conformité.",
        "",
        "## 5. Ablation des scores externes (`EXT_SOURCE_*`)",
        "",
        f"- LightGBM sans les {len(ch['ablation_ext_source']['removed_features'])} variables `EXT_SOURCE` : "
        f"AUC validation {_f(ch['ablation_ext_source']['valid']['auc'])} (Δ {_f(ch['ablation_ext_source']['delta_valid_auc'])}), "
        f"AUC test {_f(t['lgbm_no_ext']['auc'])} (Δ vs LightGBM complet {_f(t['lgbm_no_ext']['auc'] - t['lgbm']['auc'])}).",
        f"- La grille de score n'est **pas** exempte de ces variables : {ev['scorecard_ext_vars_count']} de ses "
        f"{ev['scorecard_n_vars']} variables en dérivent ({', '.join('`' + v + '`' for v in ev['scorecard_ext_vars'])}). "
        "Aucune ablation de la grille n'a été réalisée (il faudrait refaire la sélection et la régression).",
        "",
        "## 6. Motifs de refus (grille)",
        "",
        "Pour chaque demande, les trois variables où l'écart entre les points obtenus et le maximum de points de la variable "
        f"est le plus grand. Distribution du premier motif parmi les demandes refusées au test (scénario `{reco}`) :",
        "",
        "| Variable | 1er motif (refusés) | Part | Dans le top 3 (refusés) |",
        "|---|---:|---:|---:|",
    ]
    for r in reasons.head(8).itertuples():
        L.append(f"| `{r.variable}` | {_n(int(r.n_reason1_refused))} | {pct(r.pct_reason1_refused)} | {pct(r.pct_top3_refused)} |")
    top = reasons.iloc[0]
    L += [
        "",
        f"Le premier motif est presque toujours `{top['variable']}` : son maximum de points "
        f"({int(top['max_points'])}) est {'le plus élevé' if top['max_points'] >= reasons['max_points'].max() else 'parmi les plus élevés'} "
        "de la grille, donc son manque de points domine mécaniquement. Les 2e et 3e motifs sont plus "
        "informatifs ; un score externe n'est de plus pas un motif explicable au client tel quel.",
        "",
        "## 7. Stratégie de seuils (choisie sur la validation, évaluée sur le test)",
        "",
        f"Zones : accepter si score ≥ seuil + {st['review_half_width_points']} ; revoir entre seuil − "
        f"{st['review_half_width_points']} et seuil + {st['review_half_width_points']} ; refuser en dessous. "
        f"Perte attendue = PD × LGD × EAD (EAD = `AMT_CREDIT`, LGD {pct(st['lgd_base'], 0)}).",
        "",
        "| Scénario | Seuil | Acceptation (test) | Défaut des acceptés | Bons refusés | Perte attendue acceptée | Perte évitée | Part évitée | Zone de revue | Défaut tranche marginale | Marge d'équilibre |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    tb = scen[(scen["split"] == "test") & (scen["lgd"] == st["lgd_base"])]
    for r in tb.itertuples():
        L.append(f"| {SCENARIO_LABELS[r.scenario]}{' **(recommandé)**' if r.recommended else ''} | {r.cutoff} | "
                 f"{pct(r.approval_rate)} | {pct(r.bad_rate_accepted, 2)} | {_n(int(r.good_refused_n))} ({pct(r.good_refused_pct)}) | "
                 f"{money(r.el_accepted)} | {money(r.el_avoided)} | {pct(r.el_avoided_pct)} | {pct(r.zone_review_pct)} | "
                 f"{'—' if pd.isna(r.marginal_bad_rate) else pct(r.marginal_bad_rate, 2)} | "
                 f"{'—' if pd.isna(r.breakeven_margin) else pct(r.breakeven_margin, 1)} |")
    aa = st["approve_all_test"]
    order = list(st["cutoffs"])
    nxt = order[order.index(reco) + 1] if order.index(reco) + 1 < len(order) else None
    if nxt is None:
        next_step = "C'est le scénario le plus large étudié."
    else:
        bm = tb.set_index("scenario").loc[nxt, "breakeven_margin"]
        next_step = (f"Point de bascule : si la marge nette d'un bon crédit dépasse {pct(bm, 1)} du montant prêté "
                     f"(tranche {SCENARIO_LABELS[nxt]} au test), élargir au scénario {SCENARIO_LABELS[nxt]} devient rentable ; "
                     "cette marge n'est pas connue dans les données.")
    L += [
        "",
        f"Sans seuil (tout accepter) : taux de défaut {pct(aa['bad_rate_accepted'], 2)}, perte attendue {money(aa['el_all'])}. "
        "Montants en unités monétaires du jeu de données. Tranche marginale : clients acceptés en plus par rapport au "
        "scénario plus prudent ; marge d'équilibre = marge nette (en % du montant prêté) qu'un bon crédit doit rapporter "
        "pour que l'acceptation de cette tranche compense sa perte attendue (LGD · Σ PD·EAD / Σ (1 − PD)·EAD).",
        "",
        "Sensibilité à la LGD (test, scénario recommandé) : "
        + " ; ".join(f"LGD {pct(r.lgd, 0)} → perte attendue acceptée {money(r.el_accepted)}, évitée {money(r.el_avoided)}"
                     for r in scen[(scen['split'] == 'test') & (scen['scenario'] == reco)].itertuples())
        + ". La part évitée ne dépend pas de la LGD (constante).",
        "",
        f"**Recommandation : scénario {SCENARIO_LABELS[reco]}.** Règle fixée avant lecture du test : maximiser, sur la validation, "
        "« part de la perte attendue évitée − part des bons clients refusés » ("
        + " ; ".join(f"{SCENARIO_LABELS[k]} {_f(v)}" for k, v in st["recommendation_criterion_valid"].items())
        + f"). Sur le test : acceptation {pct(st['recommended_test']['approval_rate'])}, défaut des acceptés "
        f"{pct(st['recommended_test']['bad_rate_accepted'], 2)} contre {pct(aa['bad_rate_accepted'], 2)} sans seuil, "
        f"{pct(st['recommended_test']['el_avoided_pct'])} de la perte attendue évitée pour "
        f"{pct(st['recommended_test']['good_refused_pct'])} de bons clients refusés. {next_step}",
        "",
        "## 8. Limites",
        "",
        f"- **Sur-apprentissage de LightGBM** : AUC train {_f(ch['metrics']['train']['auc'])} contre validation "
        f"{_f(ch['metrics']['valid']['auc'])} et test {_f(t['lgbm']['auc'])}. La grille est stable "
        f"(train {_f(ev['train_metrics']['scorecard']['auc'])}, test {_f(t['scorecard']['auc'])}).",
        "- **Validation réutilisée** : early stopping et choix de variante de LightGBM, calibrage isotone de contrôle et "
        "choix des seuils ont tous été faits sur la validation ; seules les mesures sur le test sont sans biais.",
        f"- **LGD supposée** ({pct(st['lgd_base'], 0)}, sensibilité {', '.join(pct(x, 0) for x in st['lgd_sensitivity'])}) "
        "et EAD = montant du crédit à l'octroi (pas d'amortissement) : la perte attendue est un ordre de grandeur.",
        "- **Règle de recommandation sans données de marge** : elle pèse à égalité perte évitée et bons clients perdus.",
        "- **Biais de sélection** : Home Credit n'observe le défaut que des dossiers acceptés par le passé ; "
        "aucune inférence des refusés n'a été faite.",
        "- **Motifs de refus** dominés par le score externe `APP_EXT_SOURCE_MEAN` (amplitude de points la plus grande), "
        "peu exploitable comme motif communiqué au client.",
        f"- **Zone de revue** de ± {st['review_half_width_points']} points : {pct(st['recommended_test']['zone_review_pct'])} "
        "des demandes au test pour le scénario recommandé, charge de traitement manuel à valider.",
        "- **PSI** calculé sur un découpage aléatoire : il ne remplace pas un suivi de dérive dans le temps en production.",
        "",
    ]
    REPORT_MD.write_text("\n".join(L), encoding="utf-8")
    return REPORT_MD


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="régénère seulement docs/model_performance_report.md")
    args = ap.parse_args()
    if args.report:
        log(f"[écrit] {write_report().relative_to(PROJECT_ROOT).as_posix()}")
    else:
        run()


if __name__ == "__main__":
    main()
