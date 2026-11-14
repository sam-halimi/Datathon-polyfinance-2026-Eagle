"""Clés et réglages locaux, lus dans le fichier `.env` à la racine du dépôt.

Le fichier `.env` n'est jamais poussé sur GitHub (voir `.gitignore`).
Une variable déjà définie dans le terminal garde la priorité sur le fichier.
"""

from __future__ import annotations

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def charger_env(chemin: Path | None = None) -> list[str]:
    """Charge les lignes `NOM=valeur` de `.env`. Renvoie les noms chargés, jamais les valeurs."""
    chemin = chemin or RACINE / ".env"
    if not chemin.is_file():
        return []
    charges = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, valeur = ligne.split("=", 1)
        nom = nom.strip().removeprefix("export ").strip()
        valeur = valeur.strip().strip('"').strip("'")
        if nom and valeur and nom not in os.environ:
            os.environ[nom] = valeur
            charges.append(nom)
    return charges
