"""Authentification Bedrock partagée par `verifier_cles` et par les agents de `agents/`.

Trois modes, dans cet ordre :
- jeton : `AWS_BEARER_TOKEN_BEDROCK` est dans `.env` ou dans l'environnement ;
- identifiants : `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY` (et `AWS_SESSION_TOKEN` pour un rôle
  temporaire, comme le compte de l'atelier AWS) : boto3 signe lui-même les requêtes (SigV4) ;
- proxy : session cloud sans jeton local, dont le proxy réseau (`HTTPS_PROXY`) ajoute lui-même
  l'en-tête `Authorization: Bearer` aux requêtes vers `bedrock-runtime.<région>.amazonaws.com`.
  boto3 refuse de partir sans identifiants : on lui donne un jeton factice, que le proxy
  remplace par le vrai.

`BEDROCK_AUTH` (jeton, identifiants ou proxy) impose un mode. `BEDROCK_REGION` impose la région de
Bedrock (`AWS_REGION` et `AWS_DEFAULT_REGION`) : utile quand un secret réseau vise une autre région
et remplacerait la signature des identifiants.

Au démarrage d'un agent : `preparer_bedrock()`. Pour un appel isolé qui ne doit rien laisser
dans l'environnement (cas de `verifier_cles`) : `with jeton_temporaire(): ...`.
Aucune valeur de clé n'est affichée ni renvoyée.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from tools.env import charger_env

VARIABLE_JETON = "AWS_BEARER_TOKEN_BEDROCK"
VARIABLES_IDENTIFIANTS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
MODES = ("jeton", "identifiants", "proxy")
VARIABLES_PROXY = ("HTTPS_PROXY", "https_proxy")
JETON_FACTICE = "jeton-factice-remplace-par-le-proxy"


def mode_bedrock() -> str | None:
    """« jeton » si un vrai `AWS_BEARER_TOKEN_BEDROCK` est présent, sinon « identifiants » si des clés
    d'accès AWS le sont, sinon « proxy » si un proxy réseau peut authentifier à notre place (le jeton
    factice compte comme proxy), None sinon. `BEDROCK_AUTH` impose le mode."""
    impose = os.environ.get("BEDROCK_AUTH", "").strip().lower()
    if impose in MODES:
        return impose
    jeton = os.environ.get(VARIABLE_JETON, "").strip()
    if jeton and jeton != JETON_FACTICE:
        return "jeton"
    if all(os.environ.get(nom, "").strip() for nom in VARIABLES_IDENTIFIANTS):
        return "identifiants"
    if jeton == JETON_FACTICE or any(os.environ.get(nom, "").strip() for nom in VARIABLES_PROXY):
        return "proxy"
    return None


def appliquer_region() -> str | None:
    """Si `BEDROCK_REGION` est réglée, elle devient la région de boto3 et de Strands. Renvoie la région."""
    region = os.environ.get("BEDROCK_REGION", "").strip()
    if region:
        os.environ["AWS_REGION"] = os.environ["AWS_DEFAULT_REGION"] = region
    return region_bedrock()


def region_bedrock() -> str | None:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or None


def modele_bedrock() -> str | None:
    """Identifiant du modèle réglé par `BEDROCK_MODEL_ID`, sinon None (défaut de Strands)."""
    return os.environ.get("BEDROCK_MODEL_ID", "").strip() or None


def aide_proxy() -> str:
    """Rappel affiché quand un appel échoue en mode proxy."""
    return (f"authentification par le proxy : son secret réseau doit viser "
            f"bedrock-runtime.{region_bedrock() or 'non définie'}.amazonaws.com, région lue dans AWS_REGION")


def preparer_bedrock() -> str:
    """À appeler au démarrage de tout agent. Charge `.env`, puis, en mode proxy, pose le jeton
    factice pour toute la durée du processus. Renvoie le mode (« jeton » ou « proxy »).

    Lève RuntimeError si ni jeton, ni identifiants AWS, ni proxy ne sont disponibles.
    """
    charger_env()
    appliquer_region()
    mode = mode_bedrock()
    if mode is None:
        raise RuntimeError(f"{VARIABLE_JETON} absente, pas d'identifiants AWS et aucun proxy réseau pour authentifier. "
                           "Machine à soi : coller la clé dans .env. Session cloud : voir docs/consignes-de-depart.md")
    if mode == "proxy":
        os.environ[VARIABLE_JETON] = JETON_FACTICE
    elif mode == "identifiants" and os.environ.get(VARIABLE_JETON) == JETON_FACTICE:
        del os.environ[VARIABLE_JETON]  # sinon boto3 enverrait le jeton factice au lieu de signer
    return mode


@contextmanager
def jeton_temporaire() -> Iterator[str | None]:
    """Comme `preparer_bedrock`, mais remet l'environnement dans son état d'origine en sortant.

    Un vrai jeton n'est jamais remplacé. Sans jeton, identifiants ni proxy, ne fait rien et donne None.
    """
    noms = (VARIABLE_JETON, "AWS_REGION", "AWS_DEFAULT_REGION")
    avant = {nom: os.environ.get(nom) for nom in noms}
    appliquer_region()
    mode = mode_bedrock()
    if mode == "proxy":
        os.environ[VARIABLE_JETON] = JETON_FACTICE
    try:
        yield mode
    finally:
        for nom, valeur in avant.items():
            if valeur is None:
                os.environ.pop(nom, None)
            else:
                os.environ[nom] = valeur
