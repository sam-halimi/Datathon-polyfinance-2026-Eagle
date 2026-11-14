"""Vérifie les clés du fichier `.env` en une commande : `python -m tools.verifier_cles`

1. `.env` : le fichier existe et les deux clés sont lues (seuls les noms s'affichent).
2. FRED : une vraie requête à l'API officielle, avec les dates de publication.
3. Bedrock : un agent Strands avec un seul outil (la volatilité) répond à une question.

Chaque étape affiche OK ou ÉCHEC avec l'erreur exacte. Aucune clé n'est affichée.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

from tools.env import RACINE, charger_env

CLES = ("FRED_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")
SYMBOLE_TEST = "NVDA"


def masquer(texte: str) -> str:
    """Retire d'un message toute valeur de clé qui s'y serait glissée."""
    for nom in CLES:
        valeur = os.environ.get(nom, "")
        if valeur:
            texte = texte.replace(valeur, "***")
    return texte


def verifier_env() -> tuple[bool, str]:
    if not (RACINE / ".env").is_file():
        return False, "fichier .env absent à la racine du dépôt : cp .env.example .env, puis coller les clés"
    charger_env()
    manquantes = [nom for nom in CLES if not os.environ.get(nom, "").strip()]
    if manquantes:
        return False, f"clé(s) vide(s) ou absente(s) dans .env : {', '.join(manquantes)}"
    return True, "clés lues : " + ", ".join(CLES)


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
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip():
        return False, "AWS_BEARER_TOKEN_BEDROCK absente"
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
    if os.environ.get("BEDROCK_MODEL_ID", "").strip():
        reglages["model"] = os.environ["BEDROCK_MODEL_ID"].strip()
    try:
        reponse = str(Agent(**reglages)(
            f"Quelle est la volatilité annualisée de {SYMBOLE_TEST} ? Utilise l'outil. "
            "Réponds en une phrase, en pourcentage avec une décimale, et donne la période."))
    except Exception as e:
        return False, masquer(f"{type(e).__name__} : {e}")
    print()  # la réponse de l'agent s'affiche au fil de l'eau, on revient à la ligne
    chiffre = f"{attendu:.1f}"
    if chiffre in reponse or chiffre.replace(".", ",") in reponse:
        return True, f"l'agent a appelé l'outil et répondu {chiffre.replace('.', ',')} %, le chiffre calculé par tools/"
    return False, masquer(f"l'agent a répondu, mais sans le chiffre attendu ({chiffre} %). Réponse : {reponse[:300]}")


def main() -> int:
    etapes = [(".env", verifier_env), ("FRED", verifier_fred), ("Bedrock", verifier_bedrock)]
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
