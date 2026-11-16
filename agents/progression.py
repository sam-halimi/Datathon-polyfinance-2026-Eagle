"""Avancement d'une analyse en cours, pour l'écran d'attente du site.

Le pipeline met de une à trois minutes. Pendant ce temps, le site demande où il en est : quel
agent travaille, lesquels ont fini et ce qu'ils ont constaté. Rien n'est estimé : chaque état
vient du journal du pipeline (agents/journal.py), au moment où il change.

Où l'état est gardé :
- en mémoire, pour le serveur local (un seul processus) ;
- dans S3, sur Lambda (`EAGLE_PROGRESSION_SEAU`), parce que la requête d'analyse et les requêtes
  de suivi n'y tombent pas sur la même instance.

Écrire l'avancement ne doit jamais faire échouer une analyse : toute erreur d'écriture est ignorée.
L'identifiant de suivi est choisi par le site (un UUID) ; l'état ne contient que des noms d'agents
et leurs constats, ni profil ni chiffre de portefeuille.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

# Les agents, dans l'ordre où l'écran d'attente les montre (agents/pipeline.py : executer).
AGENTS = ("Orchestrateur", "ESG et qualité", "Marché et risque", "Macro et taux",
          "Constructeur", "Gouvernance", "Explication")
PREFIXE = "progression/"
_IDENTIFIANT = re.compile(r"[A-Za-z0-9-]{8,64}")
_MEMOIRE: dict[str, dict[str, Any]] = {}
_verrou = threading.Lock()
_s3: Any = None


def identifiant_valide(ident: Any) -> bool:
    return isinstance(ident, str) and bool(_IDENTIFIANT.fullmatch(ident))


def _seau() -> str | None:
    return os.environ.get("EAGLE_PROGRESSION_SEAU") or None


def _client_s3() -> Any:
    global _s3
    if _s3 is None:
        import boto3

        _s3 = boto3.client("s3")
    return _s3


def _ecrire(ident: str, etat: dict[str, Any]) -> None:
    with _verrou:
        _MEMOIRE[ident] = dict(etat)
        while len(_MEMOIRE) > 200:  # le serveur local ne garde que les dernières analyses
            _MEMOIRE.pop(next(iter(_MEMOIRE)))
    seau = _seau()
    if seau:
        _client_s3().put_object(Bucket=seau, Key=f"{PREFIXE}{ident}.json", ContentType="application/json",
                                Body=json.dumps(etat, ensure_ascii=False).encode("utf-8"))


def lire(ident: Any) -> dict[str, Any]:
    """État d'une analyse : `{"connu": False}` si l'identifiant est inconnu ou mal formé."""
    if not identifiant_valide(ident):
        return {"connu": False}
    etat: dict[str, Any] | None = None
    seau = _seau()
    try:
        if seau:
            objet = _client_s3().get_object(Bucket=seau, Key=f"{PREFIXE}{ident}.json")
            etat = json.loads(objet["Body"].read().decode("utf-8"))
        else:
            with _verrou:
                etat = dict(_MEMOIRE[ident]) if ident in _MEMOIRE else None
    except Exception:  # noqa: BLE001 - objet absent ou S3 injoignable : l'écran d'attente s'en passe
        etat = None
    if not etat:
        return {"connu": False}
    return {"connu": True, **etat, "ecoule": round(time.time() - etat.get("debut", time.time()), 1)}


class Suivi:
    """Reçoit les signaux du journal d'une analyse et tient son état à jour."""

    def __init__(self, ident: str) -> None:
        self.ident = ident
        self.etat: dict[str, Any] = {"phase": "analyse", "agent": None, "essai": 1, "faits": [],
                                     "agents": list(AGENTS), "debut": time.time()}
        self._publier()

    def _publier(self) -> None:
        try:
            _ecrire(self.ident, self.etat)
        except Exception:  # noqa: BLE001 - l'analyse continue sans suivi
            pass

    def recevoir(self, signal: str, *valeurs: str) -> None:
        """`("agent", nom)` : cet agent prend la main. `("etape", nom, constat)` : cet agent a fini."""
        if signal == "agent":
            nom = valeurs[0]
            if nom not in AGENTS or nom == self.etat["agent"]:
                return
            # Le constructeur qui reprend la main après la gouvernance : un nouvel essai.
            if nom == "Constructeur" and self.etat["agent"] == "Gouvernance":
                self.etat["essai"] += 1
            self.etat["agent"] = nom
        elif signal == "etape":
            self.etat["faits"] = [f for f in self.etat["faits"] if f["agent"] != valeurs[0]] + [
                {"agent": valeurs[0], "fait": valeurs[1]}]
        else:
            return
        self._publier()

    def phase(self, nom: str) -> None:
        """« analyse », « traduction », « terminee » ou « echec »."""
        self.etat["phase"] = nom
        if nom != "analyse":
            self.etat["agent"] = None
        self._publier()


def ouvrir(ident: Any) -> Suivi | None:
    """Un suivi pour cet identifiant, ou None s'il manque ou n'est pas valide (l'analyse se fait sans)."""
    return Suivi(ident) if identifiant_valide(ident) else None
