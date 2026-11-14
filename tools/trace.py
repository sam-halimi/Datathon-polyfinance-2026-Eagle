"""Référence d'appel attachée à chaque chiffre produit par tools/.

Règle du projet : aucun chiffre ne sort d'un modèle. Chaque mesure renvoyée par
un outil est un dictionnaire qui garde le nom de l'outil, ses paramètres, la
période réellement couverte par les données et la formule utilisée. L'agent
d'explication cite ce dictionnaire tel quel.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def periode_de(index: pd.Index) -> dict[str, Any]:
    """Période effectivement couverte par un index de dates."""
    if len(index) == 0:
        return {"debut": None, "fin": None, "observations": 0}
    return {
        "debut": pd.Timestamp(index.min()).date().isoformat(),
        "fin": pd.Timestamp(index.max()).date().isoformat(),
        "observations": int(len(index)),
    }


def resultat(
    outil: str,
    parametres: dict[str, Any],
    periode: dict[str, Any],
    valeur: Any,
    unite: str,
    formule: str,
    sources: list[str],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble une mesure et sa référence d'appel.

    `valeur` est brute (pas d'arrondi) : l'arrondi relève de l'affichage.
    """
    return {
        "outil": outil,
        "parametres": parametres,
        "periode": periode,
        "valeur": valeur,
        "unite": unite,
        "formule": formule,
        "sources": sources,
        "details": details or {},
    }
