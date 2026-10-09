"""Phase 1 — Vérification des CSV téléchargés manuellement dans data/raw/.

Aucun téléchargement, aucun appel réseau, aucune suppression.

Usage (depuis la racine du projet) :
    .venv\\Scripts\\python.exe scripts/verify_raw_data.py

- Vérifie la présence des 9 CSV attendus (noms exacts, casse comprise) ;
  s'arrête avec un code 1 si l'un manque.
- Journalise nom et taille en Mo de chaque CSV.
- Liste les fichiers annexes (.zip, sample_submission.csv, ...) comme « non utilisés ».
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import EXPECTED_CSV, RAW_DIR  # noqa: E402

IGNORED = {".gitkeep"}


def size_mb(path: Path) -> float:
    return round(path.stat().st_size / 1024**2, 1)


def verify() -> list[tuple[str, float]]:
    """Retourne [(nom, taille Mo)] des 9 CSV ; lève FileNotFoundError si l'un manque."""
    if not RAW_DIR.is_dir():
        raise FileNotFoundError(f"Dossier introuvable : {RAW_DIR}")

    # Comparaison sensible à la casse (Windows ne l'est pas : on liste le dossier)
    present = {p.name: p for p in RAW_DIR.iterdir() if p.is_file()}
    missing = [f for f in EXPECTED_CSV if f not in present]
    if missing:
        near = {f: [n for n in present if n.lower() == f.lower()] for f in missing}
        detail = "; ".join(f"{f} (casse différente : {near[f]})" if near[f] else f for f in missing)
        raise FileNotFoundError(f"CSV manquant(s) dans data/raw/ : {detail}")

    rows = [(f, size_mb(present[f])) for f in EXPECTED_CSV]
    print(f"{'Fichier':<40} {'Taille (Mo)':>12}")
    for name, mb in rows:
        print(f"{name:<40} {mb:>12,.1f}")
    print(f"{'TOTAL (9 CSV)':<40} {sum(mb for _, mb in rows):>12,.1f}")

    extras = sorted(n for n in present if n not in EXPECTED_CSV and n not in IGNORED)
    print("\nFichiers annexes non utilisés :", ", ".join(extras) if extras else "aucun")
    if not any(n.lower().endswith(".zip") for n in extras):
        print("Archives .zip : aucune présente dans data/raw/.")
    return rows


def main() -> None:
    try:
        verify()
    except FileNotFoundError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        sys.exit(1)
    print("\n[OK] Les 9 CSV attendus sont présents.")


if __name__ == "__main__":
    main()
