"""Petit serveur local pour l'interface Eagle : `python -m agents.serveur` (port 8000).

    GET  /sante
    GET  /actif?symbole=tesla&tolerance=faible&horizon=3   fiche d'un actif face à un profil
    POST /scenarios  {"poids": {...}, "horizon_annees": 8, "capital": 50000}
    POST /analyse    {"profil": {...}, "demande": "...", "prenom": "..."}   pipeline complet sur Bedrock
    GET  /demonstration/robert                              sortie enregistrée d'un persona

Option anglaise : `langue=en` (paramètre d'adresse en GET, champ du corps en POST) renvoie les
mêmes données avec leurs textes traduits par agents/traduction.py. Sans ce paramètre : français.

/analyse lance le vrai pipeline (environ une minute) pour n'importe quel profil au format de
`python -m agents.profil`. Il lui faut les clés (`.env`, voir `python -m tools.verifier_cles`).
Les autres routes ne demandent aucune clé. Simulation uniquement.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agents import comptes
from agents.resistance import est_passagere
from agents.traduction import langue_demandee, traduire_sortie
from tools.scenarios import eventail_scenarios, fiche_actif

RACINE = Path(__file__).resolve().parents[1]
SORTIES = RACINE / "agents" / "sorties"


class Refus(Exception):
    """Requête mal formée : renvoyée en 400 avec un message lisible."""


def scenarios_du_portefeuille(sortie: dict[str, Any]) -> dict[str, Any] | None:
    """Éventail du portefeuille retenu par la gouvernance (à défaut le premier), à l'horizon et au capital du profil."""
    portefeuilles = sortie.get("portefeuilles") or []
    if not portefeuilles:
        return None
    profil = sortie.get("profil", {})
    retenu_id = (sortie.get("gouvernance") or {}).get("portefeuille_retenu")
    retenu = next((p for p in portefeuilles if p.get("id") == retenu_id), portefeuilles[0])
    poids = {ligne["symbole"]: ligne["poids"] for ligne in retenu["lignes"]}
    return eventail_scenarios(poids, int(profil.get("horizon_annees", 10)),
                              float(profil.get("capital_fictif", 10_000)), profil.get("devise", "CAD"))


def scenarios_par_portefeuille(sortie: dict[str, Any]) -> dict[str, Any]:
    """Un éventail par portefeuille proposé : la personne peut demander à voir une autre proposition."""
    profil = sortie.get("profil", {})
    resultat = {}
    for p in sortie.get("portefeuilles") or []:
        poids = {ligne["symbole"]: ligne["poids"] for ligne in p["lignes"]}
        resultat[p["id"]] = eventail_scenarios(poids, int(profil.get("horizon_annees", 10)),
                                               float(profil.get("capital_fictif", 10_000)), profil.get("devise", "CAD"))
    return resultat


def analyser(corps: dict[str, Any]) -> dict[str, Any]:
    """Lance le pipeline pour un profil quelconque et ajoute l'éventail de scénarios."""
    from pydantic import ValidationError

    from agents.profil import Profil

    demande = str(corps.get("demande") or "").strip()
    if not demande:
        raise Refus("Champ « demande » manquant : la phrase de l'utilisateur, par exemple « Je veux 40 % sur Tesla ».")
    try:
        profil = Profil(**(corps.get("profil") or {}))
    except ValidationError as e:
        raise Refus(f"Profil invalide : {e.errors(include_url=False)}") from e
    from agents.pipeline import Session  # importé ici : il lui faut strands-agents et les clés

    sortie = Session(profil, demande, corps.get("prenom") or None).executer()
    sortie["scenarios"] = scenarios_du_portefeuille(sortie)
    sortie["scenarios_par_portefeuille"] = scenarios_par_portefeuille(sortie)
    # Option anglaise : les textes sont traduits après coup, les chiffres ne passent pas par le modèle.
    return traduire_sortie(sortie, langue_demandee(corps.get("langue")))


def demonstration(nom: str, langue: str = "fr") -> dict[str, Any]:
    chemin = SORTIES / f"{nom}.json"
    if nom not in ("robert", "amira", "mateo") or not chemin.exists():
        raise Refus("Persona inconnu. Choix : robert, amira, mateo.")
    # En anglais : la version déjà traduite (python -m agents.traduction), sinon traduction à la volée.
    deja = SORTIES / "en" / f"{nom}.json"
    sortie = json.loads((deja if langue == "en" and deja.exists() else chemin).read_text(encoding="utf-8"))
    sortie.setdefault("scenarios", scenarios_du_portefeuille(sortie))
    sortie.setdefault("scenarios_par_portefeuille", scenarios_par_portefeuille(sortie))
    return traduire_sortie(sortie, langue) if sortie.get("langue") != langue else sortie


PANNE_PASSAGERE = ("Le modèle de langage est momentanément indisponible (Amazon Bedrock). Plusieurs reprises et un "
                   "modèle de secours ont été essayés. Votre profil est conservé : relancez dans un instant.")


def phrase_d_echec(erreur: Exception, ou_est_le_detail: str) -> tuple[int, str]:
    """Code HTTP et phrase pour un échec du pipeline : 503 si la panne est passagère, 500 sinon."""
    if est_passagere(erreur):
        return 503, PANNE_PASSAGERE
    return 500, f"{type(erreur).__name__} : le pipeline a échoué. Détail {ou_est_le_detail}."


def repondre(methode: str, chemin: str, requete: dict[str, list[str]], corps: dict[str, Any],
             entetes: dict[str, str] | None = None) -> dict[str, Any]:
    """Aiguillage, séparé du serveur pour être testé sans réseau.

    `entetes` : en-têtes de la requête, lus pour le jeton de compte (agents/comptes.py)."""
    if methode == "GET" and chemin == "/sante":
        return {"ok": True, "service": "Eagle", "simulation": True, "comptes": comptes.actifs()}
    if chemin.startswith("/compte"):
        if not comptes.actifs():
            raise Refus("Les comptes ne sont pas activés sur ce serveur : aucune connexion n'est nécessaire.")
        if methode == "POST" and chemin == "/compte/creer":
            return comptes.creer(corps)
        if methode == "POST" and chemin == "/compte/connexion":
            return comptes.connecter(corps)
        if methode == "GET" and chemin == "/compte":
            return {"identifiant": comptes.identifier(entetes)}
    comptes.exiger(methode, chemin, entetes)
    langue = langue_demandee((requete.get("langue") or [corps.get("langue")])[0])
    if methode == "GET" and chemin == "/actif":
        symbole = (requete.get("symbole") or [""])[0]
        if not symbole:
            raise Refus("Paramètre « symbole » manquant.")
        try:
            return traduire_sortie(fiche_actif(symbole, (requete.get("tolerance") or ["modéré"])[0],
                                               int((requete.get("horizon") or ["10"])[0])), langue)
        except ValueError as e:
            raise Refus(str(e)) from e
    if methode == "GET" and chemin.startswith("/demonstration/"):
        return demonstration(chemin.rsplit("/", 1)[1], langue)
    if methode == "POST" and chemin == "/scenarios":
        try:
            eventail = eventail_scenarios(corps["poids"], int(corps["horizon_annees"]),
                                          float(corps.get("capital", 10_000)), corps.get("devise", "CAD"))
            return traduire_sortie({"scenarios": eventail}, langue)["scenarios"]
        except (KeyError, ValueError, TypeError) as e:
            raise Refus(f"Requête invalide : {e}") from e
    if methode == "POST" and chemin == "/analyse":
        return analyser(corps)
    raise Refus(f"Route inconnue : {methode} {chemin}")


class Gestionnaire(BaseHTTPRequestHandler):
    def _envoyer(self, code: int, contenu: dict[str, Any]) -> None:
        donnees = json.dumps(contenu, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(donnees)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(donnees)

    def _traiter(self, methode: str) -> None:
        url = urlparse(self.path)
        try:
            corps: dict[str, Any] = {}
            if methode == "POST":
                longueur = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(longueur) or b"{}")
            self._envoyer(200, repondre(methode, url.path.rstrip("/") or "/", parse_qs(url.query), corps,
                                        dict(self.headers.items())))
        except comptes.RefusCompte as e:
            self._envoyer(e.code, {"erreur": str(e)})
        except Refus as e:
            self._envoyer(400, {"erreur": str(e)})
        except json.JSONDecodeError:
            self._envoyer(400, {"erreur": "Le corps de la requête n'est pas du JSON valide."})
        except Exception as e:  # le pipeline a échoué : message court, détail dans le terminal
            traceback.print_exc()
            code, phrase = phrase_d_echec(e, "dans le terminal du serveur")
            self._envoyer(code, {"erreur": phrase})

    def do_GET(self) -> None:  # noqa: N802
        self._traiter("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._traiter("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._envoyer(200, {})


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    serveur = ThreadingHTTPServer(("127.0.0.1", port), Gestionnaire)
    print(f"Eagle : serveur local sur http://localhost:{port} (Ctrl+C pour arrêter). Simulation uniquement.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
