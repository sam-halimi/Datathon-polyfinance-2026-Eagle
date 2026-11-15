"""Authentification Bedrock partagée par `verifier_cles` et par les agents de `agents/`.

Trois modes, dans cet ordre de priorité :
- iam : identifiants AWS de l'environnement cloud (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN` s'ils sont temporaires, région dans `AWS_DEFAULT_REGION`). boto3 signe lui-même
  les requêtes (SigV4). Tout `AWS_BEARER_TOKEN_BEDROCK` est alors retiré de l'environnement du
  processus, sinon boto3 le préférerait. Un secret réseau du proxy sur bedrock-runtime remplacerait
  la signature : il ne doit pas exister dans ce mode (le message d'erreur le rappelle).
- jeton : `AWS_BEARER_TOKEN_BEDROCK` est dans `.env` ou dans l'environnement ;
- proxy : session cloud sans jeton local, dont le proxy réseau (`HTTPS_PROXY`) ajoute lui-même
  l'en-tête `Authorization: Bearer` aux requêtes vers `bedrock-runtime.<région>.amazonaws.com`.
  boto3 refuse de partir sans identifiants : on lui donne un jeton factice, que le proxy
  remplace par le vrai.

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
VARIABLES_IAM = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
VARIABLES_PROXY = ("HTTPS_PROXY", "https_proxy")
JETON_FACTICE = "jeton-factice-remplace-par-le-proxy"


def mode_bedrock() -> str | None:
    """« iam » si les identifiants AWS de l'environnement sont présents (prioritaires), « jeton » si un
    vrai `AWS_BEARER_TOKEN_BEDROCK` est présent, « proxy » si un proxy réseau peut authentifier à notre
    place (le jeton factice compte comme proxy), None sinon."""
    if all(os.environ.get(nom, "").strip() for nom in VARIABLES_IAM):
        return "iam"
    jeton = os.environ.get(VARIABLE_JETON, "").strip()
    if jeton and jeton != JETON_FACTICE:
        return "jeton"
    if jeton == JETON_FACTICE or any(os.environ.get(nom, "").strip() for nom in VARIABLES_PROXY):
        return "proxy"
    return None


def region_bedrock() -> str | None:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or None


def modele_bedrock() -> str | None:
    """Identifiant du modèle réglé par `BEDROCK_MODEL_ID`, sinon None (défaut de Strands)."""
    return os.environ.get("BEDROCK_MODEL_ID", "").strip() or None


def aide_iam() -> str:
    """Rappel affiché quand un appel échoue en mode iam."""
    return ("identifiants AWS de l'environnement cloud (signature SigV4). « Authentication failed: Please make "
            "sure your API Key is valid » veut dire qu'un secret réseau du proxy remplace encore la signature : "
            f"supprimer le secret réseau de bedrock-runtime.{region_bedrock() or '<région>'}.amazonaws.com "
            "dans les réglages de l'environnement cloud")


def aide_proxy() -> str:
    """Rappel affiché quand un appel échoue en mode proxy."""
    return (f"authentification par le proxy : son secret réseau doit viser "
            f"bedrock-runtime.{region_bedrock() or 'non définie'}.amazonaws.com, région lue dans AWS_REGION")


def preparer_bedrock() -> str:
    """À appeler au démarrage de tout agent. Charge `.env`, puis prépare le mode pour toute la durée
    du processus : en mode iam, retire tout jeton Bedrock (boto3 signe avec les identifiants AWS) ;
    en mode proxy, pose le jeton factice. Renvoie le mode (« iam », « jeton » ou « proxy »).

    Lève RuntimeError si aucune authentification n'est disponible.
    """
    charger_env()
    mode = mode_bedrock()
    if mode is None:
        raise RuntimeError("Aucune authentification Bedrock : ni identifiants AWS (AWS_ACCESS_KEY_ID, "
                           f"AWS_SECRET_ACCESS_KEY), ni {VARIABLE_JETON}, ni proxy réseau. Session cloud : variables "
                           "de l'environnement cloud. Machine à soi : .env (voir .env.example)")
    if mode == "iam":
        os.environ.pop(VARIABLE_JETON, None)
    elif mode == "proxy":
        os.environ[VARIABLE_JETON] = JETON_FACTICE
    return mode


@contextmanager
def jeton_temporaire() -> Iterator[str | None]:
    """Comme `preparer_bedrock`, mais remet l'environnement dans son état d'origine en sortant.

    Un vrai jeton n'est jamais remplacé, sauf en mode iam où il est retiré le temps de l'appel.
    Sans aucune authentification, ne fait rien et donne None.
    """
    mode = mode_bedrock()
    avant = os.environ.get(VARIABLE_JETON)
    if mode == "iam":
        os.environ.pop(VARIABLE_JETON, None)
    elif mode == "proxy":
        os.environ[VARIABLE_JETON] = JETON_FACTICE
    try:
        yield mode
    finally:
        if avant is None:
            os.environ.pop(VARIABLE_JETON, None)
        else:
            os.environ[VARIABLE_JETON] = avant
