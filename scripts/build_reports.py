"""Phase 5 — Documents de restitution générés à partir des sorties chiffrées.

Usage (depuis la racine du projet, après scripts/build_cutoff_strategy.py) :
    .venv\\Scripts\\python.exe scripts/build_reports.py            # les deux documents
    .venv\\Scripts\\python.exe scripts/build_reports.py --note     # note au comité seulement
    .venv\\Scripts\\python.exe scripts/build_reports.py --card     # fiche modèle seulement

Écrit :
- docs/note_comite_credit.md : note d'une page « Recommandations au comité de crédit » ;
- docs/model_card.md        : fiche du modèle (usage prévu, données, variables, métriques, équité,
                              limites, suivi, versions).

Aucun chiffre n'est saisi à la main : tout provient de output/tables/ (Phases 3 et 4) et des
métadonnées des modèles. Les seuils de suivi (PSI 0,10 / 0,25, règle des 4/5, critère de calibration)
sont ceux déjà appliqués en Phase 4 (evaluation_metrics.json).
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import date
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DOCS_DIR, TABLES_DIR  # noqa: E402

NOTE_MD = DOCS_DIR / "note_comite_credit.md"
CARD_MD = DOCS_DIR / "model_card.md"

SCENARIO_LABELS = {"prudent": "Prudent", "equilibre": "Équilibré", "croissance": "Croissance"}
FOUR_FIFTHS = 0.80

# Libellés courts des 17 variables de la grille (formules : docs/feature_catalog.md)
VAR_LABELS = {
    "APP_EXT_SOURCE_MEAN": "Moyenne des scores externes EXT_SOURCE_1/2/3 renseignés",
    "EXT_SOURCE_3": "Score externe n° 3 (opaque)",
    "EXT_SOURCE_1": "Score externe n° 1 (opaque)",
    "APP_EMPLOYED_YEARS": "Ancienneté dans l'emploi actuel (années)",
    "BUR_YEARS_SINCE_LAST_CREDIT": "Années depuis le dernier crédit déclaré au bureau",
    "INS_MAX_DAYS_LATE_12M": "Retard maximal de paiement d'échéance sur 12 mois (jours)",
    "CC_MAX_UTILIZATION_12M": "Utilisation maximale de la carte de crédit sur 12 mois (solde / plafond)",
    "OCCUPATION_TYPE": "Profession déclarée",
    "APP_CREDIT_GOODS_RATIO": "Montant du crédit / prix du bien financé",
    "PREV_MEAN_CREDIT_APPLICATION_RATIO": "Demandes antérieures : montant accordé / montant demandé (moyenne)",
    "ORGANIZATION_TYPE": "Secteur de l'employeur",
    "PREV_SHARE_REFUSED": "Part des demandes antérieures refusées",
    "INS_SHARE_LATE": "Part des échéances payées en retard",
    "PREV_SHARE_APPROVED": "Part des demandes antérieures approuvées",
    "BUR_DEBT_CREDIT_RATIO": "Bureau : encours / montant des crédits actifs",
    "CC_MEAN_UTILIZATION": "Utilisation moyenne de la carte de crédit (solde / plafond)",
    "REGION_RATING_CLIENT_W_CITY": "Notation de la région de résidence (ville incluse), 1 à 3",
}
SOURCE_LABELS = {"application": "demande", "bureau": "bureau de crédit", "previous_application": "demandes antérieures",
                 "installments_payments": "échéances", "credit_card_balance": "carte de crédit"}
LIBS = ["pandas", "numpy", "pyarrow", "duckdb", "optbinning", "scikit-learn", "statsmodels", "lightgbm",
        "shap", "matplotlib"]


# ---------------------------------------------------------------------------
# Formatage français (identique à train_scorecard._f / _n, sans importer optbinning)
# ---------------------------------------------------------------------------
def _f(x: float, d: int = 4) -> str:
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _n(x: int) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def pct(x: float, d: int = 1) -> str:
    return _f(100 * x, d) + " %"


def pts(x: float, d: int = 1) -> str:
    return _f(100 * x, d) + " pt"


def money(x: float) -> str:
    return _f(x / 1e6, 1) + " M"


# ---------------------------------------------------------------------------
# Lecture des sorties
# ---------------------------------------------------------------------------
def load_inputs() -> dict:
    def j(name: str) -> dict:
        return json.loads((TABLES_DIR / name).read_text(encoding="utf-8"))

    d = {
        "ev": j("evaluation_metrics.json"), "st": j("cutoff_strategy.json"), "sm": j("scorecard_metrics.json"),
        "ch": j("challenger_metrics.json"),
        "comp": pd.read_csv(TABLES_DIR / "final_comparison.csv"),
        "scen": pd.read_csv(TABLES_DIR / "cutoff_scenarios.csv"),
        "fair": pd.read_csv(TABLES_DIR / "fairness_table.csv").set_index("group"),
        "psi": pd.read_csv(TABLES_DIR / "psi_table.csv"),
        "reasons": pd.read_csv(TABLES_DIR / "refusal_reasons.csv").set_index("variable"),
        "iv": pd.read_csv(TABLES_DIR / "iv_table.csv").set_index("variable"),
        "sc": pd.read_csv(TABLES_DIR / "scorecard_table.csv"),
        "shap": pd.read_csv(TABLES_DIR / "shap_importance.csv"),
        "cal": pd.read_csv(TABLES_DIR / "calibration_test.csv"),
    }
    if d["ev"]["dry_run"]:
        raise RuntimeError("Sorties de répétition (--dry-run) : relancer evaluate_models.py avant les documents.")
    return d


def key_numbers(d: dict) -> dict:
    """Chiffres partagés par la note et la fiche (tous lus dans les sorties)."""
    ev, st = d["ev"], d["st"]
    comp = d["comp"].set_index(["model", "split"])
    scen = d["scen"]
    lgd = st["lgd_base"]
    test = scen[scen["split"].eq("test")]
    base = test[np.isclose(test["lgd"], lgd)].set_index("scenario")
    reco = st["recommended"]
    fair = d["fair"]
    goods_ratio = fair.loc["M", "approval_rate_goods"] / fair.loc["F", "approval_rate_goods"]
    return {
        "reco": reco, "lgd": lgd, "base": base, "rt": st["recommended_test"], "all": st["approve_all_test"],
        "lgd_sens": test[test["scenario"].eq(reco)].set_index("lgd"),
        "auc": {(m, s): comp.loc[(m, s), "auc"] for m in ("scorecard", "lgbm", "lgbm_no_ext") for s in ("train", "valid", "test")},
        "gini": {(m, s): comp.loc[(m, s), "gini"] for m in ("scorecard", "lgbm", "lgbm_no_ext") for s in ("train", "valid", "test")},
        "ks": {(m, s): comp.loc[(m, s), "ks"] for m in ("scorecard", "lgbm", "lgbm_no_ext") for s in ("train", "valid", "test")},
        "brier": {(m, s): comp.loc[(m, s), "brier"] for m in ("scorecard", "lgbm", "lgbm_no_ext") for s in ("train", "valid", "test")},
        "boot": ev["bootstrap"],
        "ratio_mf": fair.loc["M", "approval_rate"] / fair.loc["F", "approval_rate"],
        "ratio_mf_goods": goods_ratio,
        "ext_reason1": d["reasons"].loc["APP_EXT_SOURCE_MEAN", "pct_reason1_refused"],
        "ext_vars": ev["scorecard_ext_vars"], "n_vars": ev["scorecard_n_vars"],
        "ablation_delta_test": comp.loc[("lgbm_no_ext", "test"), "auc"] - comp.loc[("lgbm", "test"), "auc"],
        "psi": ev["psi"], "cal": ev["calibration"], "n": ev["n"],
        "review_n": st["recommended_test"]["zone_review_pct"] * st["n_test"],
        "default_rate": ev["test_metrics"]["scorecard"]["default_rate"],
    }


# ---------------------------------------------------------------------------
# Note au comité de crédit (une page)
# ---------------------------------------------------------------------------
def write_note(d: dict) -> Path:
    k = key_numbers(d)
    ev, st = d["ev"], d["st"]
    reco, base, rt, al = k["reco"], k["base"], k["rt"], k["all"]
    b = k["boot"]
    c = st["cutoffs"]
    hw = st["review_half_width_points"]
    nxt = "equilibre" if reco == "prudent" else None
    s35, s55 = k["lgd_sens"].loc[min(st["lgd_sensitivity"])], k["lgd_sens"].loc[max(st["lgd_sensitivity"])]
    lgd_lo, lgd_hi = min(st["lgd_sensitivity"]), max(st["lgd_sensitivity"])
    thr = ev["psi"]["thresholds"]

    rows = []
    for key in st["cutoffs"]:
        r = base.loc[key]
        name = f"**{SCENARIO_LABELS[key]} (recommandé)**" if key == reco else SCENARIO_LABELS[key]
        rows.append(f"| {name} | {c[key]['cutoff']} | {pct(r['approval_rate'])} | {pct(r['bad_rate_accepted'], 2)} | "
                    f"{pct(r['good_refused_pct'])} | {money(r['el_avoided'])} ({pct(r['el_avoided_pct'])}) | "
                    f"{pct(r['zone_review_pct'])} |")

    L = [
        "# Recommandations au comité de crédit",
        "",
        f"> Grille de score d'octroi, données publiques Home Credit (Kaggle). Généré par `scripts/build_reports.py` "
        f"depuis `output/tables/`. Mesures sur le test scellé ({_n(st['n_test'])} demandes, lu uniquement par l'évaluation finale, sans aucun réglage dessus). "
        "Montants en unités du jeu de données.",
        "",
        "**Décision demandée.** (1) Adopter la grille de score "
        f"({k['n_vars']} variables, {d['sm']['score_range']['min']} à {d['sm']['score_range']['max']} points) comme "
        f"modèle de décision ; (2) retenir le scénario **{SCENARIO_LABELS[reco]}** (seuil {c[reco]['cutoff']}, revue "
        f"manuelle de {c[reco]['cutoff'] - hw} à {c[reco]['cutoff'] + hw - 1}) ; (3) conditionner la mise en "
        "production aux réserves ci-dessous.",
        "",
        f"**Scénario recommandé (test, LGD {pct(k['lgd'], 0)}).** Acceptation **{pct(rt['approval_rate'])}**, "
        f"défaut des acceptés **{pct(rt['bad_rate_accepted'], 2)}** contre {pct(al['bad_rate_accepted'], 2)} sans "
        f"seuil, **{pct(rt['el_avoided_pct'])}** de la perte attendue évitée ({money(rt['el_avoided'])} sur "
        f"{money(al['el_all'])}), pour {pct(rt['good_refused_pct'])} de bons clients refusés.",
        "",
        "| Scénario | Seuil | Acceptation | Défaut des acceptés | Bons refusés | Perte évitée | Zone de revue |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *rows,
        "",
    ]
    if nxt is not None:
        L += [
            "Règle fixée avant le test : maximiser « part de perte évitée − part de bons refusés » sur la validation. "
            f"Le scénario {SCENARIO_LABELS[nxt]} devient rentable si la marge nette d'un bon crédit dépasse "
            f"**{pct(base.loc[nxt, 'breakeven_margin'])} du montant prêté** (donnée à fournir par la banque).",
            "",
        ]
    L += [
        "**Choix du modèle.** La **grille** : lisible, motifs de refus, calibrée (écart moyen par décile "
        f"{pts(k['cal']['scorecard']['mean_abs_decile_gap'], 2)}), stable (AUC train "
        f"{_f(k['auc'][('scorecard', 'train')])}, test {_f(k['auc'][('scorecard', 'test')])}). **LightGBM** reste "
        f"challenger : AUC test {_f(k['auc'][('lgbm', 'test')])}, écart "
        f"+{_f(b['auc_diff_lgbm_minus_scorecard']['estimate'])} (IC 95 % [{_f(b['auc_diff_lgbm_minus_scorecard']['low'])} ; "
        f"{_f(b['auc_diff_lgbm_minus_scorecard']['high'])}]), mais moins explicable et sur-appris (AUC train "
        f"{_f(k['auc'][('lgbm', 'train')])}).",
        "",
        "**Risques et conditions.**",
        "",
        f"- **Équité** : ratio d'acceptation H/F {_f(k['ratio_mf'], 3)} (règle des 4/5 "
        f"{'respectée de peu' if k['ratio_mf'] >= FOUR_FIFTHS else 'NON respectée'}), {_f(k['ratio_mf_goods'], 3)} "
        "parmi les bons clients ; revue de conformité requise.",
        f"- **Zone de revue** : {pct(rt['zone_review_pct'])} des demandes (≈ {_n(k['review_n'])} dossiers au test) ; "
        "capacité des analystes à valider.",
        f"- **Scores externes** : {len(k['ext_vars'])} variables sur {k['n_vars']} dérivent de `EXT_SOURCE`, premier "
        f"motif de {pct(k['ext_reason1'])} des refus ; source locale équivalente à identifier.",
        f"- **LGD supposée** : de {pct(lgd_lo, 0)} à {pct(lgd_hi, 0)}, perte attendue acceptée de "
        f"{money(s35['el_accepted'])} à {money(s55['el_accepted'])}.",
        "- **Transposabilité** : données Home Credit ≠ portefeuille camerounais ; PD et seuils à **recalibrer sur "
        "l'historique de la banque**.",
        "",
        "**Prochaines étapes.** (1) Rejouer la grille sur l'historique interne et recalibrer ; (2) pilote en double "
        f"run ; (3) suivi mensuel : PSI (alerte > {_f(thr['moderate'], 2)}), défaut des acceptés (référence "
        f"{pct(rt['bad_rate_accepted'], 2)}), calibration, Gini (alerte sous {_f(b['scorecard_gini']['low'], 3)}), "
        f"ratio H/F (alerte sous {_f(FOUR_FIFTHS, 2)}) ; (4) revue annuelle face au challenger.",
        "",
    ]
    NOTE_MD.write_text("\n".join(L), encoding="utf-8")
    return NOTE_MD


# ---------------------------------------------------------------------------
# Fiche modèle
# ---------------------------------------------------------------------------
def catalog_sources() -> dict[str, str]:
    """Source de chaque variable, lue dans docs/feature_catalog.md (colonne « Source »)."""
    out = {}
    path = DOCS_DIR / "feature_catalog.md"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) > 3 and parts[1].startswith("`") and parts[1].endswith("`"):
            out.setdefault(parts[1].strip("`"), parts[2])
    return out


def lib_versions() -> list[tuple[str, str]]:
    out = [("python", platform.python_version())]
    for lib in LIBS:
        try:
            out.append((lib, metadata.version(lib)))
        except metadata.PackageNotFoundError:
            out.append((lib, "non installé"))
    return out


def write_card(d: dict) -> Path:
    k = key_numbers(d)
    ev, st, sm, ch = d["ev"], d["st"], d["sm"], d["ch"]
    sc, iv, shap = d["sc"], d["iv"], d["shap"]
    reco, rt = k["reco"], k["rt"]
    b = k["boot"]
    s = sm["scaling"]
    src = catalog_sources()
    fair = d["fair"]
    psi_var = d["psi"][d["psi"]["level"].eq("variable")]
    names = {"scorecard": "Grille de score", "lgbm": "LightGBM (challenger)", "lgbm_no_ext": "LightGBM sans EXT_SOURCE"}
    hw = st["review_half_width_points"]
    n_total = sum(k["n"].values())
    crit = ev["calibration"]["criterion"]

    var_rows = []
    pts_rng = sc.groupby("variable")["points"].agg(["min", "max"])
    for v in sm["variables"]:
        source = SOURCE_LABELS.get(src.get(v, ""), src.get(v, "—"))
        var_rows.append(f"| `{v}` | {VAR_LABELS.get(v, '—')} | {source} | {_f(iv.loc[v, 'iv'])} | "
                        f"{_f(sm['coefficients'][v])} | {int(pts_rng.loc[v, 'min'])} – {int(pts_rng.loc[v, 'max'])} |")

    perf_rows = []
    for m in ("scorecard", "lgbm", "lgbm_no_ext"):
        for sp in ("train", "valid", "test"):
            perf_rows.append(f"| {names[m]} | {sp} | {_n(k['n'][sp])} | {_f(k['auc'][(m, sp)])} | "
                             f"{_f(k['gini'][(m, sp)])} | {_f(k['ks'][(m, sp)])} | {_f(k['brier'][(m, sp)])} |")

    fair_rows = [f"| {g} | {_n(r['n'])} | {pct(r['default_rate'], 2)} | {_f(r['auc_scorecard'])} | "
                 f"{pct(r['approval_rate'])} | {pct(r['approval_rate_goods'])} | {pct(r['bad_rate_accepted'], 2)} |"
                 for g, r in fair.iterrows()]

    top_shap = shap.sort_values("rank").head(5)
    shap_txt = ", ".join(f"`{r.feature}` ({_f(r.share_pct, 1)} %)" for r in top_shap.itertuples())
    cal = k["cal"]
    thr = ev["psi"]["thresholds"]
    vers = lib_versions()
    train_vers = sm.get("versions", {}) | {"lightgbm": ch.get("lightgbm_version", "—")}

    L = [
        "# Fiche modèle — grille de score d'octroi (credit-risk-scorecard)",
        "",
        f"> Générée par `scripts/build_reports.py` (fonction `write_card`) le {date.today().isoformat()} à partir de "
        "`output/tables/` et des métadonnées des modèles. Aucun chiffre saisi à la main.",
        "",
        "## 1. Détails du modèle",
        "",
        f"- **Modèle de production proposé** : grille de score (scorecard) version {sm['version']}, régression "
        f"logistique non pondérée sur classes WoE (optbinning + statsmodels), {sm['n_vars']} variables.",
        f"- **Mise à l'échelle** : {s['base_score']} points pour des odds {s['base_odds']}:1 (bons:mauvais), PDO = "
        f"{s['pdo']} ; points entiers par classe ; score élevé = risque faible ; plage théorique "
        f"{sm['score_range']['min']} – {sm['score_range']['max']} points.",
        f"- **Challenger** : LightGBM {ch.get('lightgbm_version', '')} (variante {ch['chosen_variant']}, {ch['best_iteration']} arbres, "
        f"{ch['n_features']} variables) ; non proposé en production.",
        f"- **Règle de décision** : scénario {SCENARIO_LABELS[reco]}, seuil {st['cutoffs'][reco]['cutoff']} ; "
        f"accepter si score ≥ {st['cutoffs'][reco]['cutoff'] + hw}, revue manuelle de "
        f"{st['cutoffs'][reco]['cutoff'] - hw} à {st['cutoffs'][reco]['cutoff'] + hw - 1}, refuser en dessous.",
        "- **Sorties** : score entier, PD du logit, décision (accepter / revoir / refuser), trois motifs de refus "
        "(variables au plus grand manque de points).",
        "",
        "## 2. Usage prévu",
        "",
        "- **Prévu** : aide à la décision d'octroi de crédits à la consommation (prêts cash et renouvelables) pour "
        "des particuliers ; classement des demandes par risque, fixation d'un seuil, motivation des refus.",
        "- **Utilisateurs** : analystes crédit, comité de crédit, équipe risque/modèles.",
        "- **Hors champ** : décision entièrement automatisée sans revue humaine de la zone grise ; crédit aux "
        "entreprises ou microfinance de groupe ; tarification au risque ; utilisation directe sur un portefeuille "
        "camerounais **sans recalibrage** ; toute décision fondée sur le genre.",
        "",
        "## 3. Données",
        "",
        f"- **Source** : Home Credit Default Risk (Kaggle), table `application_train` et historiques (bureau, "
        f"demandes antérieures, échéances, POS, carte de crédit) agrégés par demande ({_n(n_total)} demandes).",
        f"- **Cible** : `TARGET` = 1 si difficultés de paiement ; taux de défaut {pct(k['default_rate'], 2)}.",
        f"- **Découpage stratifié** (graine 42) : train {_n(k['n']['train'])}, validation {_n(k['n']['valid'])}, "
        f"test {_n(k['n']['test'])} ; test scellé, lu uniquement par `scripts/evaluate_models.py` (aucune sélection ni "
        f"réglage dessus), chaque lecture journalisée dans `models/test_access_log.csv` ; dernière lecture le "
        f"{ev['test_opening']['timestamp_utc']} "
        f"(empreinte SHA-256 {'conforme' if ev['test_opening']['fingerprint_match'] else 'NON conforme'}).",
        "- **Biais de sélection** : seuls les dossiers accordés par le passé ont une cible observée ; pas d'inférence "
        "des refusés.",
        "",
        "## 4. Variables de la grille",
        "",
        f"Sélection : {sm['funnel']['candidates']} candidates → {sm['funnel']['iv_ge_0_02']} avec IV ≥ "
        f"{_f(sm['params']['iv_min'], 2)} → {sm['funnel']['after_corr']} après corrélation → "
        f"{sm['funnel']['after_cap20']} après plafond → {sm['funnel']['final']} après p-valeur et signe. "
        "Variable exclue par construction : `CODE_GENDER` (utilisée seulement pour l'audit d'équité).",
        "",
        "| Variable | Description | Source | IV | Coefficient | Points (min – max) |",
        "|---|---|---|---:|---:|---:|",
        *var_rows,
        "",
        "## 5. Performance",
        "",
        "| Modèle | Échantillon | Effectif | AUC | Gini | KS | Brier |",
        "|---|---|---:|---:|---:|---:|---:|",
        *perf_rows,
        "",
        f"IC 95 % sur le test (bootstrap apparié, {b.get('n_resamples', '—')} rééchantillonnages) : AUC grille "
        f"[{_f(b['scorecard_auc']['low'])} ; {_f(b['scorecard_auc']['high'])}], AUC LightGBM "
        f"[{_f(b['lgbm_auc']['low'])} ; {_f(b['lgbm_auc']['high'])}], écart LightGBM − grille "
        f"{_f(b['auc_diff_lgbm_minus_scorecard']['estimate'])} [{_f(b['auc_diff_lgbm_minus_scorecard']['low'])} ; "
        f"{_f(b['auc_diff_lgbm_minus_scorecard']['high'])}].",
        "",
        f"**Calibration (test)** : PD moyenne {pct(cal['scorecard']['mean_pd'], 2)} pour {pct(cal['scorecard']['default_rate'], 2)} "
        f"observés ; écart moyen par décile {pts(cal['scorecard']['mean_abs_decile_gap'], 2)}, max "
        f"{pts(cal['scorecard']['max_abs_decile_gap'], 2)} (critère : ≤ {pts(crit['mean_abs_decile_gap_max'], 0)} et ≤ "
        f"{pts(crit['max_abs_decile_gap_max'], 0)}) → {'mal calibrée' if cal['scorecard']['miscalibrated'] else 'calibrée'}.",
        "",
        f"**Effet du seuil recommandé (test, LGD {pct(k['lgd'], 0)})** : acceptation {pct(rt['approval_rate'])}, "
        f"défaut des acceptés {pct(rt['bad_rate_accepted'], 2)} (contre {pct(k['all']['bad_rate_accepted'], 2)} sans "
        f"seuil), perte attendue évitée {pct(rt['el_avoided_pct'])}, bons clients refusés {pct(rt['good_refused_pct'])}, "
        f"zone de revue {pct(rt['zone_review_pct'])}.",
        "",
        f"**Explicabilité du challenger** (SHAP, {ch['shap']['sample_size']} demandes) : {shap_txt}.",
        "",
        "## 6. Équité (test, scénario recommandé)",
        "",
        "| Genre | Effectif | Taux de défaut | AUC grille | Acceptation | Acceptation des bons | Défaut des acceptés |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *fair_rows,
        "",
        f"Ratio d'acceptation H/F {_f(k['ratio_mf'], 3)} (règle des 4/5 : ≥ {_f(FOUR_FIFTHS, 2)}) ; parmi les bons "
        f"clients {_f(k['ratio_mf_goods'], 3)}. Le genre n'entre pas dans le modèle, mais des variables corrélées "
        "(profession, secteur d'emploi) peuvent le refléter : revue de conformité requise.",
        "",
        "## 7. Limites",
        "",
        f"- Dépendance aux scores externes opaques : {len(k['ext_vars'])} variables sur {k['n_vars']} "
        f"({', '.join(f'`{v}`' for v in k['ext_vars'])}) ; premier motif de {pct(k['ext_reason1'])} des refus ; "
        f"ablation LightGBM : {_f(k['ablation_delta_test'])} d'AUC au test.",
        f"- LGD supposée ({pct(k['lgd'], 0)}, sensibilité {', '.join(pct(x, 0) for x in st['lgd_sensitivity'])}) et "
        "EAD = montant à l'octroi : la perte attendue est un ordre de grandeur.",
        "- Règle de choix du seuil sans données de marge ; zone de revue de ± "
        f"{hw} points à dimensionner.",
        "- Données Home Credit (autre pays, autre période, autres produits) : PD et seuils non transposables tels "
        "quels à un portefeuille camerounais ; recalibrage obligatoire.",
        "- Découpage aléatoire sans dimension temporelle : le PSI mesuré contrôle le découpage, pas la dérive.",
        f"- LightGBM sur-appris (AUC train {_f(k['auc'][('lgbm', 'train')])} contre test {_f(k['auc'][('lgbm', 'test')])}).",
        "",
        "## 8. Suivi en production",
        "",
        f"- **PSI mensuel** du score et des {k['n_vars']} variables (référence : score {_f(k['psi']['score_train_test'], 4)}, "
        f"variable max {_f(k['psi']['max_variable'], 4)} `{k['psi']['max_variable_name']}`) ; < {_f(thr['moderate'], 2)} "
        f"stable, {_f(thr['moderate'], 2)} – {_f(thr['severe'], 2)} à surveiller, > {_f(thr['severe'], 2)} instable "
        f"(action). Au test : {int((psi_var['psi'] > thr['moderate']).sum())} variable(s) au-delà de {_f(thr['moderate'], 2)}.",
        f"- **Défaut des acceptés** par génération (référence {pct(rt['bad_rate_accepted'], 2)}) et **calibration** par "
        f"décile (alerte : écart moyen > {pts(crit['mean_abs_decile_gap_max'], 0)} ou max > {pts(crit['max_abs_decile_gap_max'], 0)}).",
        f"- **Discrimination** sur les générations arrivées à maturité : alerte si Gini < {_f(b['scorecard_gini']['low'], 3)} "
        "(borne basse de l'IC du test).",
        f"- **Équité** : ratio d'acceptation H/F (alerte < {_f(FOUR_FIFTHS, 2)}). **Charge** : part de la zone de revue "
        f"(référence {pct(rt['zone_review_pct'])}).",
        "- **Revue annuelle** : recalibrage, comparaison au challenger, mise à jour des seuils.",
        "",
        "## 9. Versions",
        "",
        "Environnement de génération de cette fiche :",
        "",
        "| Bibliothèque | Version |",
        "|---|---|",
        *[f"| {lib} | {v} |" for lib, v in vers],
        "",
        "Versions enregistrées à l'entraînement : "
        + " ; ".join(f"{lib} {v}" for lib, v in train_vers.items()) + ".",
        "",
    ]
    CARD_MD.write_text("\n".join(L), encoding="utf-8")
    return CARD_MD


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--note", action="store_true", help="note au comité seulement")
    p.add_argument("--card", action="store_true", help="fiche modèle seulement")
    a = p.parse_args()
    d = load_inputs()
    both = not (a.note or a.card)
    if a.note or both:
        print(f"Écrit : {write_note(d)}")
    if a.card or both:
        print(f"Écrit : {write_card(d)}")


if __name__ == "__main__":
    main()
