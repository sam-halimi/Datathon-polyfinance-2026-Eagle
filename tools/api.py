"""Appels aux API externes : cache sur disque, clés jamais écrites, en-têtes exigés.

Sources retenues (CLAUDE.md, données) : yfinance, SEC EDGAR, Finnhub, CoinGecko, plus FRED et la
Banque du Canada déjà branchées dans `tools/ingestion.py`. Aucune autre.

- Chaque réponse est enregistrée dans `data/cache/<source>/` avec l'adresse appelée (sans clé), la
  date de l'appel et le statut. Une réponse en cache est relue au lieu de rappeler l'API.
- Une clé se lit dans une variable d'environnement (ou `.env`). En session cloud, le proxy réseau
  peut l'ajouter lui-même à l'en-tête : la variable est alors absente et on envoie un jeton factice,
  que le proxy remplace (même principe que Bedrock, `tools/bedrock.py`).
- Les clés passent par un en-tête, jamais par l'adresse : elles n'apparaissent donc ni dans le cache
  ni dans un message d'erreur (`masquer`).

Le cache est ignoré par git (`data/cache/`) : les conditions d'utilisation de certaines sources
n'autorisent pas la redistribution des réponses brutes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.env import RACINE, charger_env

CACHE = RACINE / "data" / "cache"
JETON_PROXY = "jeton-factice-remplace-par-le-proxy"
VARIABLES_PROXY = ("HTTPS_PROXY", "https_proxy")

SOURCES: dict[str, dict[str, Any]] = {
    "sec": {"hote": "data.sec.gov", "variable": "SEC_USER_AGENT", "entete": "User-Agent", "secret": False,
            "pause": 0.15},  # la SEC limite à 10 requêtes par seconde
    "finnhub": {"hote": "finnhub.io", "variable": "FINNHUB_API_KEY", "entete": "X-Finnhub-Token", "secret": True,
                "pause": 1.1},  # offre gratuite : 60 appels par minute
    "coingecko": {"hote": "api.coingecko.com", "variable": "COINGECKO_API_KEY", "entete": "x-cg-demo-api-key",
                  "secret": True, "pause": 2.1},  # clé démo : 30 appels par minute
}


class ErreurApi(RuntimeError):
    """Échec d'un appel : statut HTTP ou réseau, message sans aucune clé."""


def masquer(texte: str) -> str:
    """Retire toute valeur de clé connue d'un message."""
    for s in SOURCES.values():
        if s["secret"]:
            valeur = os.environ.get(s["variable"], "")
            if valeur and valeur != JETON_PROXY:
                texte = texte.replace(valeur, "***")
    return texte


def proxy_present() -> bool:
    return any(os.environ.get(v, "").strip() for v in VARIABLES_PROXY)


def valeur_entete(source: str) -> tuple[str, str]:
    """(valeur de l'en-tête, mode) : mode « variable » ou « proxy ».

    Lève ErreurApi si la variable manque et qu'aucun proxy ne peut la fournir. Le User-Agent de la
    SEC n'est pas un secret mais une adresse de contact : le proxy ne le fournit pas.
    """
    charger_env()
    s = SOURCES[source]
    valeur = os.environ.get(s["variable"], "").strip()
    if valeur:
        return valeur, "variable"
    if s["secret"] and proxy_present():
        return JETON_PROXY, "proxy"
    raise ErreurApi(f"{s['variable']} absente" + (
        " (et aucun proxy réseau pour fournir la clé)" if s["secret"] else
        " : la SEC exige un en-tête User-Agent avec un nom et une adresse de contact"))


def _chemin_cache(source: str, url: str, params: dict[str, Any] | None) -> Path:
    cle = json.dumps({"url": url, "params": params or {}}, sort_keys=True)
    return CACHE / source / f"{hashlib.sha256(cle.encode()).hexdigest()[:24]}.json"


def lire_cache(source: str, url: str, params: dict[str, Any] | None = None,
               max_age_heures: float | None = None) -> dict[str, Any] | None:
    chemin = _chemin_cache(source, url, params)
    if not chemin.is_file():
        return None
    entree = json.loads(chemin.read_text(encoding="utf-8"))
    if max_age_heures is not None:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(entree["appele_le"])
        if age.total_seconds() > max_age_heures * 3600:
            return None
    return entree


def get_json(source: str, url: str, params: dict[str, Any] | None = None,
             max_age_heures: float | None = None, session: Any = None) -> dict[str, Any]:
    """GET JSON avec cache. Renvoie {"donnees", "url", "params", "appele_le", "depuis_cache"}.

    `max_age_heures` : None = le cache ne périme jamais (dépôts SEC) ; sinon rappel au-delà.
    `session` : objet avec `.get(url, params=, headers=, timeout=)`, remplaçable dans les tests.
    """
    en_cache = lire_cache(source, url, params, max_age_heures)
    if en_cache is not None:
        return {**en_cache, "depuis_cache": True}
    import requests

    valeur, _ = valeur_entete(source)
    entetes = {SOURCES[source]["entete"]: valeur, "Accept": "application/json"}
    if source == "sec":
        entetes["Accept-Encoding"] = "gzip, deflate"
    http = session or requests
    try:
        r = http.get(url, params=params, headers=entetes, timeout=30)
    except Exception as e:  # noqa: BLE001
        raise ErreurApi(masquer(f"{SOURCES[source]['hote']} : {type(e).__name__} : {e}")) from None
    time.sleep(SOURCES[source]["pause"] if session is None else 0)
    if r.status_code != 200:
        raise ErreurApi(masquer(f"{SOURCES[source]['hote']} a répondu {r.status_code} : {r.text[:200]}"))
    entree = {"url": url, "params": params or {}, "appele_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "statut": r.status_code, "donnees": r.json()}
    chemin = _chemin_cache(source, url, params)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(entree, ensure_ascii=False), encoding="utf-8")
    return {**entree, "depuis_cache": False}
