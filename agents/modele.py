"""Création des agents Strands sur Bedrock.

Un seul point d'entrée, `creer_agent`, pour que chaque agent démarre de la même façon :
`.env` chargé, authentification Bedrock prête (jeton ou proxy réseau), modèle résistant aux
pannes passagères (`agents/resistance.py`, `BEDROCK_MODEL_ID` en tête de chaîne). Les agents n'obtiennent un chiffre qu'en appelant un outil de `tools/`.
"""

from __future__ import annotations

from typing import Any, Callable

from agents.resistance import construire_modele
from tools.bedrock import preparer_bedrock

_mode: str | None = None


def demarrer() -> str:
    """Prépare Bedrock une seule fois par processus. Renvoie le mode (« jeton » ou « proxy »)."""
    global _mode
    if _mode is None:
        _mode = preparer_bedrock()
    return _mode


def creer_agent(nom: str, consigne: str, outils: list[Callable[..., Any]] | None = None,
                silencieux: bool = True) -> Any:
    """Agent Strands nommé, avec sa consigne système et ses outils.

    `silencieux` coupe l'affichage au fil de l'eau (le pipeline renvoie du JSON, pas du texte).
    """
    demarrer()
    from strands import Agent

    # Modèle résistant aux pannes passagères de Bedrock (agents/resistance.py) : reprises,
    # puis modèle de secours. `BEDROCK_MODEL_ID` place un modèle en tête de la chaîne.
    reglages: dict[str, Any] = {"name": nom, "system_prompt": consigne, "tools": outils or [],
                                "model": construire_modele()}
    if silencieux:
        reglages["callback_handler"] = None
    return Agent(**reglages)
