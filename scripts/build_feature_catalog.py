"""Phase 2 — Catalogue des variables de la table modèle : génère docs/feature_catalog.md.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/build_feature_catalog.py

CATALOG déclare, pour CHAQUE colonne de model_table_train / model_table_test :
source, formule, sens attendu vis-à-vis du risque et statut. Le sens est une hypothèse
a priori (↑ = le risque augmente avec la variable, ↓ = il diminue) : il sera confronté
aux WoE en Phase 3, sur le train seul.
Le script ajoute, lus dans la base : taux de manquants, min, max (model_table_train,
aucune statistique sur TARGET). Il échoue si une colonne n'a pas d'entrée ou si une
entrée ne correspond à aucune colonne. Le fichier produit ne contient pas de date : il
est identique octet pour octet tant que la base ne change pas. Relancer le script
réécrit le fichier entier.

Aussi importé par les notebooks de la Phase 3 (CATALOG, CAND) pour sélectionner les
variables candidates (D16).
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_PATH, DOCS_DIR, PROJECT_ROOT  # noqa: E402

VERSION = "0.3.1"
OUT = DOCS_DIR / "feature_catalog.md"

UP, DOWN, UNK = "↑", "↓", "indéterminé"
CAND = "candidate"
EXCL_GENDER = "exclue du modèle — audit d'équité"
EXCL_DAYS = "exclue du modèle — doublon de APP_*_YEARS (D3)"
ID, TGT = "identifiant", "cible"

# ---------------------------------------------------------------------------
# Colonnes brutes d'application_train / application_test (nom d'origine conservé)
# Formule commune : colonne brute, description dans docs/data_dictionary.md.
# ---------------------------------------------------------------------------
RAW_SENSE: dict[str, str] = {
    "NAME_CONTRACT_TYPE": UNK, "FLAG_OWN_CAR": UNK, "FLAG_OWN_REALTY": UNK,
    "CNT_CHILDREN": UP, "AMT_INCOME_TOTAL": DOWN, "AMT_CREDIT": UNK, "AMT_ANNUITY": UNK,
    "AMT_GOODS_PRICE": UNK, "NAME_TYPE_SUITE": UNK, "NAME_INCOME_TYPE": UNK,
    "NAME_EDUCATION_TYPE": UNK, "NAME_FAMILY_STATUS": UNK, "NAME_HOUSING_TYPE": UNK,
    "REGION_POPULATION_RELATIVE": DOWN, "OWN_CAR_AGE": UP,
    "FLAG_MOBIL": UNK, "FLAG_EMP_PHONE": UNK, "FLAG_WORK_PHONE": UNK, "FLAG_CONT_MOBILE": UNK,
    "FLAG_PHONE": UNK, "FLAG_EMAIL": UNK, "OCCUPATION_TYPE": UNK, "CNT_FAM_MEMBERS": UNK,
    "REGION_RATING_CLIENT": UP, "REGION_RATING_CLIENT_W_CITY": UP,
    "WEEKDAY_APPR_PROCESS_START": UNK, "HOUR_APPR_PROCESS_START": UNK,
    "REG_REGION_NOT_LIVE_REGION": UP, "REG_REGION_NOT_WORK_REGION": UP,
    "LIVE_REGION_NOT_WORK_REGION": UP, "REG_CITY_NOT_LIVE_CITY": UP,
    "REG_CITY_NOT_WORK_CITY": UP, "LIVE_CITY_NOT_WORK_CITY": UP, "ORGANIZATION_TYPE": UNK,
    "EXT_SOURCE_1": DOWN, "EXT_SOURCE_2": DOWN, "EXT_SOURCE_3": DOWN,
    "FONDKAPREMONT_MODE": UNK, "HOUSETYPE_MODE": UNK, "TOTALAREA_MODE": UNK,
    "WALLSMATERIAL_MODE": UNK, "EMERGENCYSTATE_MODE": UNK,
    "OBS_30_CNT_SOCIAL_CIRCLE": UNK, "DEF_30_CNT_SOCIAL_CIRCLE": UP,
    "OBS_60_CNT_SOCIAL_CIRCLE": UNK, "DEF_60_CNT_SOCIAL_CIRCLE": UP,
    **{f"{m}_{s}": UNK
       for s in ("AVG", "MODE", "MEDI")
       for m in ("APARTMENTS", "BASEMENTAREA", "YEARS_BEGINEXPLUATATION", "YEARS_BUILD",
                 "COMMONAREA", "ELEVATORS", "ENTRANCES", "FLOORSMAX", "FLOORSMIN", "LANDAREA",
                 "LIVINGAPARTMENTS", "LIVINGAREA", "NONLIVINGAPARTMENTS", "NONLIVINGAREA")},
    **{f"FLAG_DOCUMENT_{i}": UNK for i in range(2, 22)},
    **{f"AMT_REQ_CREDIT_BUREAU_{p}": UP for p in ("HOUR", "DAY", "WEEK", "MON", "QRT", "YEAR")},
}
RAW_FORMULA = "Colonne brute (description : docs/data_dictionary.md)"

# Entrée = (source, formule, sens attendu, statut)
CATALOG: dict[str, tuple[str, str, str, str]] = {
    "SK_ID_CURR": ("application", "Identifiant de la demande", "—", ID),
    "TARGET": ("application_train", "1 = difficultés de paiement, 0 = sinon ; train uniquement (D9)", "—", TGT),
    **{c: ("application", RAW_FORMULA, s, CAND) for c, s in RAW_SENSE.items()},
    "CODE_GENDER": ("application", "Colonne brute, dont 4 lignes 'XNA' dans le train (D4)", "—", EXCL_GENDER),
    "DAYS_BIRTH": ("application", "Colonne brute, jours avant la demande (négatif)", UP, EXCL_DAYS),
    "DAYS_EMPLOYED": ("application", "Colonne brute ; 365243 → NULL (D1)", UP, EXCL_DAYS),
    "DAYS_REGISTRATION": ("application", "Colonne brute, jours avant la demande (négatif)", UP, EXCL_DAYS),
    "DAYS_ID_PUBLISH": ("application", "Colonne brute, jours avant la demande (négatif)", UP, EXCL_DAYS),
    "DAYS_LAST_PHONE_CHANGE": ("application", "Colonne brute, jours avant la demande (négatif)", UP, EXCL_DAYS),
    # --- APP_ : variables créées sur la demande (database/01)
    "APP_FLAG_DAYS_EMPLOYED_ANOM": ("application", "1 si DAYS_EMPLOYED = 365243 dans la source, sinon 0 (D1)", DOWN, CAND),
    "APP_AGE_YEARS": ("application", "-DAYS_BIRTH / 365.25", DOWN, CAND),
    "APP_EMPLOYED_YEARS": ("application", "-DAYS_EMPLOYED / 365.25 (NULL si sentinelle)", DOWN, CAND),
    "APP_REGISTRATION_YEARS": ("application", "-DAYS_REGISTRATION / 365.25", DOWN, CAND),
    "APP_ID_PUBLISH_YEARS": ("application", "-DAYS_ID_PUBLISH / 365.25", DOWN, CAND),
    "APP_PHONE_CHANGE_YEARS": ("application", "-DAYS_LAST_PHONE_CHANGE / 365.25", DOWN, CAND),
    "APP_CREDIT_INCOME_RATIO": ("application", "AMT_CREDIT / AMT_INCOME_TOTAL", UP, CAND),
    "APP_ANNUITY_INCOME_RATIO": ("application", "AMT_ANNUITY / AMT_INCOME_TOTAL", UP, CAND),
    "APP_CREDIT_GOODS_RATIO": ("application", "AMT_CREDIT / AMT_GOODS_PRICE", UP, CAND),
    "APP_CREDIT_TERM_MONTHS": ("application", "AMT_CREDIT / AMT_ANNUITY (durée implicite)", UNK, CAND),
    "APP_INCOME_PER_PERSON": ("application", "AMT_INCOME_TOTAL / CNT_FAM_MEMBERS", DOWN, CAND),
    "APP_EMPLOYED_AGE_RATIO": ("application", "DAYS_EMPLOYED / DAYS_BIRTH (part de la vie en emploi)", DOWN, CAND),
    "APP_EXT_SOURCE_MEAN": ("application", "Moyenne des EXT_SOURCE_1/2/3 renseignés ; NULL si aucun", DOWN, CAND),
    "APP_EXT_SOURCE_NB_MISSING": ("application", "Nombre de EXT_SOURCE_1/2/3 manquants (0 à 3)", UP, CAND),
    # --- HAS_ : présence d'historique (database/10, D7)
    "HAS_BUR_HISTORY": ("bureau", "1 si au moins un crédit dans bureau", UNK, CAND),
    "HAS_BB_HISTORY": ("bureau_balance via bureau", "1 si au moins un mois de bureau_balance rattaché", UNK, CAND),
    "HAS_PREV_HISTORY": ("previous_application", "1 si au moins une demande antérieure", UNK, CAND),
    "HAS_INS_HISTORY": ("installments_payments", "1 si au moins une échéance", UNK, CAND),
    "HAS_POS_HISTORY": ("pos_cash_balance", "1 si au moins un mois de prêt POS / cash", UNK, CAND),
    "HAS_CC_HISTORY": ("credit_card_balance", "1 si au moins un mois de carte", UNK, CAND),
    # --- BUR_ : bureau (database/02)
    "BUR_NB_CREDITS": ("bureau", "Nombre de crédits déclarés ; 0 sans historique", UNK, CAND),
    "BUR_NB_ACTIVE": ("bureau", "Nombre de crédits CREDIT_ACTIVE = 'Active' ; 0 sans historique", UP, CAND),
    "BUR_NB_CLOSED": ("bureau", "Nombre de crédits CREDIT_ACTIVE = 'Closed' ; 0 sans historique", DOWN, CAND),
    "BUR_NB_SOLD_OR_BAD_DEBT": ("bureau", "Nombre de crédits CREDIT_ACTIVE IN ('Sold', 'Bad debt') ; 0 sans historique", UP, CAND),
    "BUR_SUM_CREDIT": ("bureau", "Somme de AMT_CREDIT_SUM des crédits actifs (0 si aucun actif ; NULL si montants tous inconnus)", UNK, CAND),
    "BUR_SUM_DEBT": ("bureau", "Somme de AMT_CREDIT_SUM_DEBT des crédits actifs (0 si aucun actif ; NULL si montants tous inconnus)", UP, CAND),
    "BUR_DEBT_CREDIT_RATIO": ("bureau", "BUR_SUM_DEBT / BUR_SUM_CREDIT (crédits actifs)", UP, CAND),
    "BUR_MAX_DAY_OVERDUE": ("bureau", "MAX(CREDIT_DAY_OVERDUE)", UP, CAND),
    "BUR_SUM_OVERDUE": ("bureau", "SUM(AMT_CREDIT_SUM_OVERDUE)", UP, CAND),
    "BUR_NB_PROLONG": ("bureau", "SUM(CNT_CREDIT_PROLONG) ; 0 sans historique", UP, CAND),
    "BUR_YEARS_SINCE_LAST_CREDIT": ("bureau", "-MAX(DAYS_CREDIT) / 365.25", DOWN, CAND),
    # --- BB_ : bureau_balance agrégé par crédit puis par client (database/02, D5, D11)
    "BB_NB_MONTHS": ("bureau_balance via bureau", "Nombre de mois observés, tous statuts ; 0 sans historique", DOWN, CAND),
    "BB_MEAN_SHARE_MONTHS_LATE": ("bureau_balance via bureau", "Moyenne par crédit de (mois '1'..'5') / (mois '0'..'5')", UP, CAND),
    "BB_MAX_SHARE_MONTHS_LATE": ("bureau_balance via bureau", "Max par crédit de (mois '1'..'5') / (mois '0'..'5')", UP, CAND),
    "BB_MAX_STATUS": ("bureau_balance via bureau", "Statut de retard maximal (0 à 5), C et X ignorés", UP, CAND),
    "BB_NB_MONTHS_12M": ("bureau_balance via bureau", "BB_NB_MONTHS sur MONTHS_BALANCE >= -11 (mois courant = 0)", DOWN, CAND),
    "BB_MEAN_SHARE_MONTHS_LATE_12M": ("bureau_balance via bureau", "BB_MEAN_SHARE_MONTHS_LATE sur MONTHS_BALANCE >= -11", UP, CAND),
    "BB_MAX_SHARE_MONTHS_LATE_12M": ("bureau_balance via bureau", "BB_MAX_SHARE_MONTHS_LATE sur MONTHS_BALANCE >= -11", UP, CAND),
    "BB_MAX_STATUS_12M": ("bureau_balance via bureau", "BB_MAX_STATUS sur MONTHS_BALANCE >= -11", UP, CAND),
    # --- PREV_ : demandes antérieures, sentinelles → NULL avant agrégation (database/03, D2)
    "PREV_NB_APPLICATIONS": ("previous_application", "Nombre de demandes ; 0 sans historique", UP, CAND),
    "PREV_SHARE_APPROVED": ("previous_application", "Part NAME_CONTRACT_STATUS = 'Approved'", DOWN, CAND),
    "PREV_SHARE_REFUSED": ("previous_application", "Part NAME_CONTRACT_STATUS = 'Refused'", UP, CAND),
    "PREV_MEAN_AMT_APPLICATION": ("previous_application", "AVG(AMT_APPLICATION)", UNK, CAND),
    "PREV_MEAN_AMT_CREDIT": ("previous_application", "AVG(AMT_CREDIT)", UNK, CAND),
    "PREV_MEAN_CREDIT_APPLICATION_RATIO": ("previous_application", "AVG(AMT_CREDIT / AMT_APPLICATION) : accordé / demandé", DOWN, CAND),
    "PREV_MEAN_CNT_PAYMENT": ("previous_application", "AVG(CNT_PAYMENT) : durée moyenne en échéances", UNK, CAND),
    "PREV_YEARS_SINCE_LAST_APPLICATION": ("previous_application", "-MAX(DAYS_DECISION) / 365.25", DOWN, CAND),
    "PREV_NB_APPLICATIONS_12M": ("previous_application", "Nombre de demandes avec DAYS_DECISION >= -365 ; 0 sans historique", UP, CAND),
    "PREV_SHARE_APPROVED_12M": ("previous_application", "PREV_SHARE_APPROVED sur DAYS_DECISION >= -365", DOWN, CAND),
    "PREV_SHARE_REFUSED_12M": ("previous_application", "PREV_SHARE_REFUSED sur DAYS_DECISION >= -365", UP, CAND),
    "PREV_MEAN_AMT_APPLICATION_12M": ("previous_application", "PREV_MEAN_AMT_APPLICATION sur DAYS_DECISION >= -365", UNK, CAND),
    "PREV_MEAN_AMT_CREDIT_12M": ("previous_application", "PREV_MEAN_AMT_CREDIT sur DAYS_DECISION >= -365", UNK, CAND),
    "PREV_MEAN_CREDIT_APPLICATION_RATIO_12M": ("previous_application", "PREV_MEAN_CREDIT_APPLICATION_RATIO sur DAYS_DECISION >= -365", DOWN, CAND),
    "PREV_MEAN_CNT_PAYMENT_12M": ("previous_application", "PREV_MEAN_CNT_PAYMENT sur DAYS_DECISION >= -365", UNK, CAND),
    # --- INS_ : échéances regroupées au grain échéance
    #     (SK_ID_PREV, NUM_INSTALMENT_VERSION, NUM_INSTALMENT_NUMBER) avant agrégation (database/04)
    "INS_NB_INSTALMENTS": ("installments_payments", "Nombre d'échéances (paiements fractionnés regroupés) ; 0 sans historique", DOWN, CAND),
    "INS_MEAN_DAYS_LATE": ("installments_payments", "Moyenne par échéance de max(dernier paiement - échéance, 0)", UP, CAND),
    "INS_MAX_DAYS_LATE": ("installments_payments", "Maximum par échéance du retard en jours", UP, CAND),
    "INS_SHARE_LATE": ("installments_payments", "Part des échéances dont le dernier paiement est en retard", UP, CAND),
    "INS_MEAN_PAYMENT_RATIO": ("installments_payments", "Moyenne par échéance de SUM(AMT_PAYMENT) / AMT_INSTALMENT", DOWN, CAND),
    "INS_SHARE_UNDERPAID": ("installments_payments", "Part des échéances avec total payé < dû - 0,01", UP, CAND),
    "INS_NB_INSTALMENTS_12M": ("installments_payments", "INS_NB_INSTALMENTS sur échéance >= -365", DOWN, CAND),
    "INS_MEAN_DAYS_LATE_12M": ("installments_payments", "INS_MEAN_DAYS_LATE sur échéance >= -365", UP, CAND),
    "INS_MAX_DAYS_LATE_12M": ("installments_payments", "INS_MAX_DAYS_LATE sur échéance >= -365", UP, CAND),
    "INS_SHARE_LATE_12M": ("installments_payments", "INS_SHARE_LATE sur échéance >= -365", UP, CAND),
    "INS_MEAN_PAYMENT_RATIO_12M": ("installments_payments", "INS_MEAN_PAYMENT_RATIO sur échéance >= -365", DOWN, CAND),
    "INS_SHARE_UNDERPAID_12M": ("installments_payments", "INS_SHARE_UNDERPAID sur échéance >= -365", UP, CAND),
    # --- POS_ : prêts POS / cash (database/05)
    "POS_NB_MONTHS": ("pos_cash_balance", "Nombre de mois observés ; 0 sans historique", DOWN, CAND),
    "POS_MAX_DPD": ("pos_cash_balance", "MAX(SK_DPD)", UP, CAND),
    "POS_MEAN_DPD_DEF": ("pos_cash_balance", "AVG(SK_DPD_DEF)", UP, CAND),
    "POS_SHARE_MONTHS_DPD": ("pos_cash_balance", "Part des mois avec SK_DPD > 0", UP, CAND),
    "POS_NB_MONTHS_12M": ("pos_cash_balance", "POS_NB_MONTHS sur MONTHS_BALANCE >= -12 (dernier mois = -1)", DOWN, CAND),
    "POS_MAX_DPD_12M": ("pos_cash_balance", "POS_MAX_DPD sur MONTHS_BALANCE >= -12", UP, CAND),
    "POS_MEAN_DPD_DEF_12M": ("pos_cash_balance", "POS_MEAN_DPD_DEF sur MONTHS_BALANCE >= -12", UP, CAND),
    "POS_SHARE_MONTHS_DPD_12M": ("pos_cash_balance", "POS_SHARE_MONTHS_DPD sur MONTHS_BALANCE >= -12", UP, CAND),
    # --- CC_ : cartes de crédit (database/06)
    "CC_NB_MONTHS": ("credit_card_balance", "Nombre de mois observés ; 0 sans historique", UNK, CAND),
    "CC_MEAN_UTILIZATION": ("credit_card_balance", "AVG(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL)", UP, CAND),
    "CC_MAX_UTILIZATION": ("credit_card_balance", "MAX(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL)", UP, CAND),
    "CC_MAX_DPD": ("credit_card_balance", "MAX(SK_DPD)", UP, CAND),
    "CC_SHARE_MONTHS_DPD": ("credit_card_balance", "Part des mois avec SK_DPD > 0", UP, CAND),
    "CC_MEAN_DRAWINGS": ("credit_card_balance", "AVG(AMT_DRAWINGS_CURRENT)", UNK, CAND),
    "CC_NB_MONTHS_12M": ("credit_card_balance", "CC_NB_MONTHS sur MONTHS_BALANCE >= -12 (dernier mois = -1)", UNK, CAND),
    "CC_MEAN_UTILIZATION_12M": ("credit_card_balance", "CC_MEAN_UTILIZATION sur MONTHS_BALANCE >= -12", UP, CAND),
    "CC_MAX_UTILIZATION_12M": ("credit_card_balance", "CC_MAX_UTILIZATION sur MONTHS_BALANCE >= -12", UP, CAND),
    "CC_MAX_DPD_12M": ("credit_card_balance", "CC_MAX_DPD sur MONTHS_BALANCE >= -12", UP, CAND),
    "CC_SHARE_MONTHS_DPD_12M": ("credit_card_balance", "CC_SHARE_MONTHS_DPD sur MONTHS_BALANCE >= -12", UP, CAND),
    "CC_MEAN_DRAWINGS_12M": ("credit_card_balance", "CC_MEAN_DRAWINGS sur MONTHS_BALANCE >= -12", UNK, CAND),
}

# Familles, dans l'ordre d'affichage : (titre, prédicat sur le nom)
FAMILIES: list[tuple[str, Callable[[str], bool]]] = [
    ("Identifiant et cible", lambda c: c in ("SK_ID_CURR", "TARGET")),
    ("Créées — demande (`APP_`, database/01)", lambda c: c.startswith("APP_")),
    ("Créées — présence d'historique (`HAS_`, database/10)", lambda c: c.startswith("HAS_")),
    ("Créées — bureau (`BUR_`, database/02)", lambda c: c.startswith("BUR_")),
    ("Créées — historique mensuel du bureau (`BB_`, database/02)", lambda c: c.startswith("BB_")),
    ("Créées — demandes antérieures (`PREV_`, database/03)", lambda c: c.startswith("PREV_")),
    ("Créées — échéances (`INS_`, database/04)", lambda c: c.startswith("INS_")),
    ("Créées — POS / cash (`POS_`, database/05)", lambda c: c.startswith("POS_")),
    ("Créées — cartes de crédit (`CC_`, database/06)", lambda c: c.startswith("CC_")),
    ("Brutes — application (nom d'origine)", lambda c: True),
]


def cell(v: object) -> str:
    return "" if v is None else str(v).replace("|", "\\|").replace("\n", " ").strip()


def num(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(int(v))
    x = float(v)
    if x.is_integer() and abs(x) < 1e15:
        return f"{int(x):,}".replace(",", " ")
    return f"{x:,.4f}".replace(",", " ").replace(".", ",")


def pct(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def check_catalog(train_cols: list[str], test_cols: list[str]) -> None:
    cols = set(train_cols) | set(test_cols)
    missing = sorted(cols - set(CATALOG))
    extra = sorted(set(CATALOG) - cols)
    if missing or extra:
        raise ValueError(f"Catalogue incohérent — colonnes sans entrée : {missing} ; entrées sans colonne : {extra}")


def column_stats(con: duckdb.DuckDBPyConnection, cols: list[tuple[str, str]]) -> dict[str, tuple[Any, ...]]:
    """(% manquants, min, max) par colonne de model_table_train ; min / max pour les colonnes numériques."""
    numeric = ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "HUGEINT", "SMALLINT", "TINYINT", "DECIMAL")
    parts: list[str] = []
    for c, t in cols:
        if c == "TARGET":
            continue
        parts.append(f"100.0 * COUNT(*) FILTER (WHERE {c} IS NULL) / COUNT(*)")
        if t.startswith(numeric):
            parts += [f"MIN({c})", f"MAX({c})"]
        else:
            parts += ["NULL", "NULL"]
    row = con.execute(f"SELECT {', '.join(parts)} FROM model_table_train").fetchone()
    names = [c for c, _ in cols if c != "TARGET"]
    return {n: row[3 * i: 3 * i + 3] for i, n in enumerate(names)}


def build() -> str:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        train = [(r[0], r[1]) for r in con.execute("DESCRIBE model_table_train").fetchall()]
        test_cols = [r[0] for r in con.execute("DESCRIBE model_table_test").fetchall()]
        n_train = con.execute("SELECT COUNT(*) FROM model_table_train").fetchone()[0]
        n_test = con.execute("SELECT COUNT(*) FROM model_table_test").fetchone()[0]
        train_cols = [c for c, _ in train]
        check_catalog(train_cols, test_cols)
        stats = column_stats(con, train)

    status_counts: dict[str, int] = {}
    for c in train_cols:
        status_counts[CATALOG[c][3]] = status_counts.get(CATALOG[c][3], 0) + 1

    out = [
        "# Catalogue des variables — table de modélisation",
        "",
        f"> Version {VERSION}. Généré par `scripts/build_feature_catalog.py` depuis `database/credit_risk.duckdb`. "
        "Source, formule, sens attendu et statut sont déclarés dans le script ; taux de manquants, min et max sont lus dans "
        f"`model_table_train` ({num(n_train)} lignes, {len(train_cols)} colonnes). `model_table_test` ({num(n_test)} lignes, "
        f"{len(test_cols)} colonnes) a les mêmes colonnes, sans `TARGET`.",
        "",
        "## Conventions",
        "",
        "- **Sens attendu** : hypothèse a priori sur le risque quand la variable augmente (↑ le risque augmente, ↓ il diminue). "
        "Il sera confronté aux WoE en Phase 3, sur le train seul. « — » pour l'identifiant, la cible et la variable exclue d'équité.",
        "- **Préfixes** : `APP_` demande, `BUR_` bureau, `BB_` bureau_balance (agrégé via bureau), `PREV_` demandes antérieures, "
        "`INS_` échéances, `POS_` POS / cash, `CC_` cartes, `HAS_` présence d'historique. Suffixe `_12M` : 12 derniers mois. "
        "Colonnes brutes : nom d'origine.",
        "- **Absence d'historique (D7)** : les comptages (`*_NB_*`) valent 0 et `HAS_<SOURCE>_HISTORY` = 0 ; "
        "les statistiques restent NULL.",
        "- **Ratios (D10)** : dénominateur nul ou NULL → NULL.",
        "- Min / max : colonnes numériques uniquement. Aucune statistique n'est calculée sur `TARGET` (D9).",
        "",
        "## Statuts",
        "",
        "| Statut | Colonnes |",
        "|---|---:|",
    ]
    out += [f"| {s} | {n} |" for s, n in sorted(status_counts.items(), key=lambda kv: -kv[1])]
    out += ["", ""]

    placed: set[str] = set()
    for title, pred in FAMILIES:
        members = [c for c in train_cols if c not in placed and pred(c)]
        if not members:
            continue
        placed.update(members)
        out += [
            f"## {title} ({len(members)})",
            "",
            "| Variable | Source | Formule | Sens attendu | Statut | % manquants | Min | Max |",
            "|---|---|---|:---:|---|---:|---:|---:|",
        ]
        for c in members:
            source, formula, sense, status = CATALOG[c]
            if c == "TARGET":
                miss, lo, hi = "—", "—", "—"
            else:
                m, lo_v, hi_v = stats[c]
                miss, lo, hi = pct(m), num(lo_v), num(hi_v)
            out.append(f"| `{c}` | {cell(source)} | {cell(formula)} | {sense} | {status} | {miss} | {lo} | {hi} |")
        out.append("")
    return "\n".join(out)


def main() -> None:
    try:
        text = build()
    except (ValueError, duckdb.Error) as exc:
        print(f"[ERREUR] {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(PROJECT_ROOT)} écrit ({len(CATALOG)} entrées, {text.count(chr(10))} lignes)")


if __name__ == "__main__":
    main()