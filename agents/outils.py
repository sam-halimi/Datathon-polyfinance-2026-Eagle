"""Outils Strands donnés aux agents. Chacun appelle une fonction de `tools/` et passe par le registre.

Les outils renvoient du JSON avec, pour chaque chiffre, son repère `{id}` et une valeur arrondie
« pour raisonner ». Les agents écrivent le repère dans leurs textes, jamais la valeur.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from strands import tool

from agents.gouvernance import verifier_portefeuille
from agents.profil import Profil
from agents.registre import Registre
from tools.donnees import univers
from tools.mesures import gain_de_rattrapage, pire_baisse, volatilite
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille


def _json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False)


def _erreur(e: Exception) -> str:
    return _json({"erreur": f"{type(e).__name__} : {e}"})


def table_univers() -> list[dict[str, str]]:
    """Univers investissable (data/assets_universe.csv), sans aucun chiffre de marché."""
    u = univers().reset_index()
    return [{"symbole": r.ticker, "nom": r.name, "classe": r.asset_class, "secteur": r.sector,
             "devise": r.currency} for r in u.itertuples()]


def devise_calcul(profil: Profil) -> str:
    return "CAD" if profil.devise == "CAD" else "cotation"


def mesurer_actifs_brut(registre: Registre, symboles: list[str]) -> dict[str, Any]:
    sortie: dict[str, Any] = {}
    for s in symboles:
        try:
            reperes = registre.enregistrer(volatilite(s)) + registre.enregistrer(pire_baisse(s))
            sortie[s] = registre.resume(reperes)
        except Exception as e:  # symbole inconnu : on le dit, on n'invente rien
            sortie[s] = {"erreur": f"{type(e).__name__} : {e}"}
    return sortie


def rattrapage_brut(registre: Registre, symbole: str) -> list[str]:
    pb = pire_baisse(symbole)
    return registre.enregistrer(pb) + registre.enregistrer(gain_de_rattrapage(pb))


def outils_mesure(registre: Registre) -> list[Callable[..., Any]]:
    """Mesures par actif : volatilité, pire baisse, corrélations, gain de rattrapage."""

    @tool
    def mesurer_actifs(symboles: list[str]) -> str:
        """Volatilité annualisée et pire baisse historiques (2021-2026) de chaque actif, en devise de cotation.

        Renvoie, par symbole, les repères à citer tels quels, par exemple {vol_tsla}.
        """
        return _json(mesurer_actifs_brut(registre, symboles))

    @tool
    def correlations_actifs(symboles: list[str]) -> str:
        """Corrélations des rendements quotidiens entre 2 à 8 actifs, sur leurs jours communs.

        Une corrélation proche de 1 : les deux actifs ont bougé ensemble, ils se diversifient mal.
        """
        try:
            return _json(registre.resume(registre.enregistrer(correlations(symboles))))
        except Exception as e:
            return _erreur(e)

    @tool
    def rattrapage_apres_pire_baisse(symbole: str) -> str:
        """Pire baisse historique d'un actif et gain qu'il a fallu ensuite pour revenir au sommet : perte / (1 - perte)."""
        try:
            return _json(registre.resume(rattrapage_brut(registre, symbole)))
        except Exception as e:
            return _erreur(e)

    return [mesurer_actifs, correlations_actifs, rattrapage_apres_pire_baisse]


def outils_constructeur(registre: Registre, profil: Profil, contraintes_profil: dict[str, Any]) -> list[Callable[..., Any]]:
    """Mesure d'un portefeuille candidat et prévérification contre le profil."""
    devise = devise_calcul(profil)

    @tool
    def mesurer_portefeuille(poids_pourcent: dict[str, int]) -> str:
        """Volatilité, pire baisse et parts du risque d'un portefeuille simulé candidat.

        poids_pourcent : {symbole: pourcentage entier}, total 100. Exemple : {"XIU.TO": 40, "ZST.TO": 60}.
        """
        try:
            poids = {s: p / 100 for s, p in poids_pourcent.items() if p}
            nom = registre.nom_portefeuille(poids)
            reperes = registre.enregistrer(stats_portefeuille(poids, devise=devise), nom)
            reperes += registre.enregistrer(parts_du_risque(poids, devise=devise), nom)
            return _json(registre.resume(reperes))
        except Exception as e:
            return _erreur(e)

    @tool
    def verifier_proposition(poids_pourcent: dict[str, int], symboles_theme: list[str] | None = None) -> str:
        """Prévérifie un portefeuille simulé contre le profil, avec les contrôles de la gouvernance.

        Renvoie accepte (vrai ou faux) et le message de chaque contrôle non conforme. La gouvernance
        refera ces contrôles : un portefeuille rejeté revient au constructeur.
        """
        try:
            poids = {s: p / 100 for s, p in poids_pourcent.items() if p}
            theme = {"nom": "thème", "symboles": symboles_theme} if symboles_theme else None
            r = verifier_portefeuille(poids, theme, profil, contraintes_profil)
            return _json({"accepte": r["accepte"],
                          "non_conformes": [c["message"] for c in r["controles"] if c["statut"] == "non conforme"],
                          "a_signaler": [c["message"] for c in r["controles"]
                                         if c["statut"] in ("à signaler", "information manquante")]})
        except Exception as e:
            return _erreur(e)

    return [mesurer_portefeuille, verifier_proposition]
