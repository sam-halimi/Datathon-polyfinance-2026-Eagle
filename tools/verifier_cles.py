"""Vérifie les clés du fichier `.env` en une commande : `python -m tools.verifier_cles`

1. Clés : lues dans `.env` ou dans les variables d'environnement (seuls les noms s'affichent).
2. FRED : une vraie requête à l'API officielle, avec les dates de publication.
3. Bedrock : un agent Strands avec un seul outil (la volatilité) répond à une question.
4. yfinance, SEC EDGAR, Finnhub, CoinGecko : un seul appel réel chacun (`tools/api.py`).
   SEC : en-tête User-Agent lu dans SEC_USER_AGENT. Finnhub et CoinGecko : FINNHUB_API_KEY et
   COINGECKO_API_KEY, ou le proxy réseau d'une session cloud qui ajoute la clé lui-même.

Bedrock s'authentifie par un jeton ou par le proxy réseau d'une session cloud : le mécanisme est
partagé avec les agents dans `tools/bedrock.py`. Ici, le jeton factice n'est posé que le temps de
l'appel (`jeton_temporaire`).

Chaque étape affiche OK ou ÉCHEC avec l'erreur exacte. Aucune clé n'est affichée.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

from tools.bedrock import JETON_FACTICE, VARIABLES_PROXY  # noqa: F401  (réexportés : tests, scripts)
from tools.bedrock import aide_proxy, jeton_temporaire, mode_bedrock, modele_bedrock
from tools.env import RACINE, charger_env

CLES = ("FRED_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")
SECRETS = CLES + ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
SYMBOLE_TEST = "NVDA"


def masquer(texte: str) -> str:
    """Retire d'un message toute valeur de clé qui s'y serait glissée."""
    for nom in SECRETS:
        valeur = os.environ.get(nom, "")
        if valeur:
            texte = texte.replace(valeur, "***")
    return texte


def verifier_env() -> tuple[bool, str]:
    """Les clés viennent du fichier `.env` (machine à soi) ou des variables de l'environnement cloud."""
    fichier = (RACINE / ".env").is_file()
    if fichier:
        charger_env()
    attendues = CLES if mode_bedrock() == "jeton" or mode_bedrock() is None else ("FRED_API_KEY",)
    manquantes = [nom for nom in attendues if not os.environ.get(nom, "").strip()]
    if manquantes and not fichier:
        return False, (f"clé(s) absente(s) : {', '.join(manquantes)}. Session cloud : les ajouter aux variables "
                       "de l'environnement cloud. Machine à soi : cp .env.example .env, puis coller les clés")
    if manquantes:
        return False, f"clé(s) vide(s) ou absente(s) dans .env : {', '.join(manquantes)}"
    origine = "fichier .env" if fichier else "variables d'environnement"
    message = f"clés lues ({origine}) : " + ", ".join(attendues)
    if mode_bedrock() == "proxy":
        message += " ; Bedrock : pas de jeton local, authentification par le proxy réseau"
    elif mode_bedrock() == "identifiants":
        message += " ; Bedrock : identifiants AWS (AWS_ACCESS_KEY_ID), signature SigV4"
    return True, message


def verifier_fred() -> tuple[bool, str]:
    if not os.environ.get("FRED_API_KEY", "").strip():
        return False, "FRED_API_KEY absente"
    from tools.ingestion import lire_fred, nettoyer

    fin = date.today()
    try:
        brut = lire_fred("DGS10", (fin - timedelta(days=21)).isoformat(), fin.isoformat())
        df, _ = nettoyer(brut)
    except Exception as e:
        return False, masquer(f"{type(e).__name__} : {e}")
    if df.empty:
        return False, "FRED a répondu sans aucune observation valide pour DGS10"
    reelles = "date_publication" in df.columns and df["date_publication"].notna().any()
    return True, (f"{len(df)} observations de DGS10, dernière le {df['date'].max().date()}, "
                  f"dates de publication réelles : {'oui' if reelles else 'non (le délai du catalogue servira)'}")


def verifier_bedrock() -> tuple[bool, str]:
    mode = mode_bedrock()
    if mode is None:
        return False, ("AWS_BEARER_TOKEN_BEDROCK absente, pas d'identifiants AWS et aucun proxy réseau pour authentifier à sa place")
    try:
        from strands import Agent, tool
    except ImportError:
        return False, "strands-agents n'est pas installé : pip install strands-agents"
    from tools.mesures import volatilite

    @tool
    def volatilite_actif(symbole: str) -> str:
        """Volatilité annualisée d'un actif du jeu de données, avec sa référence de calcul.

        `valeur` est une fraction : 0.25 veut dire 25 %.
        """
        return json.dumps(volatilite(symbole), ensure_ascii=False)

    attendu = volatilite(SYMBOLE_TEST)["valeur"] * 100
    reglages = {"tools": [volatilite_actif]}
    if modele_bedrock():
        reglages["model"] = modele_bedrock()
    auth = {"jeton": "jeton AWS_BEARER_TOKEN_BEDROCK", "identifiants": "identifiants AWS, signature SigV4",
            "proxy": "proxy réseau, sans jeton local"}[mode]
    try:
        with jeton_temporaire():
            reponse = str(Agent(**reglages)(
                f"Quelle est la volatilité annualisée de {SYMBOLE_TEST} ? Utilise l'outil. "
                "Réponds en une phrase, en pourcentage avec une décimale, et donne la période."))
    except Exception as e:
        message = masquer(f"{type(e).__name__} : {e}")
        if mode == "proxy":
            message += f" ({aide_proxy()})"
        return False, message
    print()  # la réponse de l'agent s'affiche au fil de l'eau, on revient à la ligne
    chiffre = f"{attendu:.1f}"
    if chiffre in reponse or chiffre.replace(".", ",") in reponse:
        return True, (f"l'agent a appelé l'outil et répondu {chiffre.replace('.', ',')} %, "
                      f"le chiffre calculé par tools/ (authentification : {auth})")
    return False, masquer(f"l'agent a répondu, mais sans le chiffre attendu ({chiffre} %). Réponse : {reponse[:300]}")


def verifier_yfinance() -> tuple[bool, str]:
    """yfinance, sans clé : cinq jours de SPY."""
    try:
        import yfinance as yf
    except ImportError:
        return False, "yfinance n'est pas installé : pip install -r tools/requirements.txt"
    try:
        df = yf.download("SPY", period="5d", interval="1d", auto_adjust=False, progress=False)
    except Exception as e:
        return False, f"{type(e).__name__} : {e}"
    if df is None or df.empty:
        return False, "yfinance n'a renvoyé aucune ligne pour SPY"
    return True, f"{len(df)} jours de SPY, dernier le {df.index.max().date()}, colonnes {sorted({c[0] for c in df.columns})}"


def _appel(source: str, url: str, params: dict | None, resume) -> tuple[bool, str]:
    from tools.api import ErreurApi, get_json, valeur_entete

    try:
        _, mode = valeur_entete(source)
        rep = get_json(source, url, params, max_age_heures=0)
    except ErreurApi as e:
        return False, masquer(str(e))
    except Exception as e:  # noqa: BLE001
        return False, masquer(f"{type(e).__name__} : {e}")
    origine = {"variable": "clé lue dans l'environnement", "proxy": "clé ajoutée par le proxy réseau"}[mode]
    if source == "sec":
        origine = "User-Agent lu dans SEC_USER_AGENT"
    return True, f"{resume(rep['donnees'])} ({origine})"


def verifier_sec() -> tuple[bool, str]:
    return _appel("sec", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json", None,
                  lambda d: f"faits XBRL de {d['entityName']} : {len(d['facts'].get('us-gaap', {}))} concepts us-gaap")


def verifier_finnhub() -> tuple[bool, str]:
    return _appel("finnhub", "https://finnhub.io/api/v1/stock/profile2", {"symbol": "AAPL"},
                  lambda d: f"fiche de AAPL : {d.get('name')}, {d.get('exchange')}" if d.get("name")
                  else f"réponse vide pour AAPL : {d}")


def verifier_coingecko() -> tuple[bool, str]:
    return _appel("coingecko", "https://api.coingecko.com/api/v3/simple/price",
                  {"ids": "bitcoin", "vs_currencies": "usd"},
                  lambda d: f"prix du Bitcoin reçu ({'bitcoin' in d and 'usd' in d['bitcoin']})")


def main() -> int:
    etapes = [("Clés", verifier_env), ("FRED", verifier_fred), ("Bedrock", verifier_bedrock),
              ("yfinance", verifier_yfinance), ("SEC EDGAR", verifier_sec), ("Finnhub", verifier_finnhub),
              ("CoinGecko", verifier_coingecko)]
    tout_bon = True
    for nom, verifier in etapes:
        ok, message = verifier()
        tout_bon = tout_bon and ok
        print(f"[{'OK' if ok else 'ÉCHEC'}] {nom} : {message}")
    print("\nTout est bon : les sessions peuvent partir." if tout_bon
          else "\nÀ corriger avant de lancer les sessions. Pour Bedrock, montrer l'erreur exacte à l'équipe AWS sur place.")
    return 0 if tout_bon else 1


if __name__ == "__main__":
    sys.exit(main())
