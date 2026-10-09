"""Publication — Manifestes d'intégrité des données brutes et des modèles (lecture seule).

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/build_manifest.py

Les données Kaggle et les modèles sérialisés ne sont pas versionnés (licence de la compétition,
taille). Ce script en publie l'empreinte pour qu'un tiers puisse vérifier qu'il travaille sur les
mêmes fichiers :
- data/raw/MANIFEST.json        : nom, taille (octets) et SHA-256 de chaque data/raw/*.csv ;
- models/MANIFEST_models.json   : nom, taille (octets) et SHA-256 de chaque fichier de models/
                                  (hors manifeste et .gitkeep).
Aucun fichier de données ou de modèle n'est modifié. Relancer le script réécrit les deux manifestes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MODELS_DIR = PROJECT_ROOT / "models"
RAW_MANIFEST = RAW_DIR / "MANIFEST.json"
MODELS_MANIFEST = MODELS_DIR / "MANIFEST_models.json"
SOURCE_URL = "https://www.kaggle.com/competitions/home-credit-default-risk/data"
CHUNK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def describe(files: list[Path]) -> dict[str, dict]:
    out = {}
    for p in sorted(files, key=lambda q: q.name.lower()):
        out[p.name] = {"filename": p.name, "bytes": p.stat().st_size, "sha256": sha256_of(p)}
        print(f"  {p.name:<40} {p.stat().st_size:>15,} o  {out[p.name]['sha256'][:12]}…")
    return out


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{path.relative_to(PROJECT_ROOT).as_posix()} écrit")


def main() -> int:
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    raw_files = [p for p in RAW_DIR.glob("*.csv") if p.is_file()]
    if not raw_files:
        print(f"[STOP] aucun CSV dans {RAW_DIR.relative_to(PROJECT_ROOT).as_posix()}/ : télécharger les données Kaggle.")
        return 1
    print(f"data/raw : {len(raw_files)} CSV")
    raw = describe(raw_files)
    raw["_created_utc"] = created
    raw["_source_url"] = SOURCE_URL
    raw["_acquisition"] = "téléchargement manuel depuis Kaggle (règles de la compétition acceptées) ; zip non conservés"
    write_json(RAW_MANIFEST, raw)

    excluded = {MODELS_MANIFEST.name, ".gitkeep"}
    model_files = [p for p in MODELS_DIR.iterdir() if p.is_file() and p.name not in excluded]
    if not model_files:
        print("[STOP] models/ est vide : lancer les scripts de modélisation avant de générer le manifeste.")
        return 1
    print(f"models : {len(model_files)} fichiers")
    models = describe(model_files)
    models["_created_utc"] = created
    write_json(MODELS_MANIFEST, models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
