"""Création des agents Strands sur Bedrock.

Un seul point d'entrée, `creer_agent`, pour que chaque agent démarre de la même façon :
`.env` chargé, authentification Bedrock prête (jeton ou proxy réseau), modèle lu dans
`BEDROCK_MODEL_ID`. Les agents n'obtiennent un chiffre qu'en appelant un outil de `tools/`.
"""

from __future__ import annotations

from typing import Any, Callable

from tools.bedrock import modele_bedrock, preparer_bedrock

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

    reglages: dict[str, Any] = {"name": nom, "system_prompt": consigne, "tools": outils or []}
    if modele_bedrock():
        reglages["model"] = modele_bedrock()
    if silencieux:
        reglages["callback_handler"] = None
    return Agent(**reglages)
