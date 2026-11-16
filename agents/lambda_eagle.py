"""Point d'entrée AWS Lambda d'Eagle : les routes de `agents.serveur`, derrière une adresse de fonction.

Le même aiguillage (`serveur.repondre`) sert en local et sur AWS. Sur Lambda, Bedrock est appelé
avec le rôle IAM de la fonction (mode « identifiants » de `tools.bedrock`) : aucune clé dans le code.
Les en-têtes CORS sont posés par la configuration de l'adresse de fonction (deploiement/deployer.py).
"""

from __future__ import annotations

import base64
import json
import traceback
from typing import Any
from urllib.parse import parse_qs

from agents.comptes import RefusCompte
from agents.serveur import Refus, phrase_d_echec, repondre


def _reponse(code: int, contenu: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": code, "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps(contenu, ensure_ascii=False, default=str)}


def gestionnaire(evenement: dict[str, Any], contexte: Any = None) -> dict[str, Any]:
    """Événement d'une adresse de fonction Lambda (format 2.0) -> réponse HTTP."""
    http = evenement.get("requestContext", {}).get("http", {})
    methode = http.get("method", "GET").upper()
    if methode == "OPTIONS":
        return _reponse(200, {})
    chemin = (evenement.get("rawPath") or "/").rstrip("/") or "/"
    requete = parse_qs(evenement.get("rawQueryString") or "")
    try:
        corps: dict[str, Any] = {}
        if methode == "POST":
            brut = evenement.get("body") or "{}"
            if evenement.get("isBase64Encoded"):
                brut = base64.b64decode(brut).decode("utf-8")
            corps = json.loads(brut or "{}")
        return _reponse(200, repondre(methode, chemin, requete, corps, evenement.get("headers") or {}))
    except RefusCompte as e:
        return _reponse(e.code, {"erreur": str(e)})
    except Refus as e:
        return _reponse(400, {"erreur": str(e)})
    except json.JSONDecodeError:
        return _reponse(400, {"erreur": "Le corps de la requête n'est pas du JSON valide."})
    except Exception as e:  # le détail va dans CloudWatch, pas dans la réponse
        traceback.print_exc()
        code, phrase = phrase_d_echec(e, "dans les journaux CloudWatch")
        return _reponse(code, {"erreur": phrase})
