"""Outils Strands donnés aux agents. Chacun appelle une fonction de tools/ et passe par le journal.

Un agent n'obtient un chiffre qu'ici. Les chiffres destinés à l'affichage sont enregistrés dans le
journal et l'agent reçoit leur clé (`{vol_tsla}`) : c'est cette clé qu'il écrit, jamais la valeur.
`tester_portefeuille` sert au constructeur à essayer des poids : ses chiffres ne s'affichent pas,
ceux du portefeuille retenu sont recalculés par le pipeline.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.journal import Journal
from tools.donnees import univers
from tools.mesures import gain_de_rattrapage, pire_baisse, volatilite
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille

MAX_SYMBOLES_PAR_APPEL = 12


def _json(objet: Any) -> str:
    return json.dumps(objet, ensure_ascii=False, default=str)


def table_univers() -> list[dict[str, str]]:
    """Univers sourcé (data/assets_universe.csv) : aucun symbole ne vient de la mémoire d'un modèle."""
    t = univers().reset_index()
    colonnes = [c for c in ("ticker", "name", "asset_class", "sector", "currency") if c in t.columns]
    return t[colonnes].rename(columns={"ticker": "symbole", "name": "nom", "asset_class": "classe",
                                       "sector": "secteur", "currency": "devise"}).to_dict("records")


def devise_calcul(profil: dict[str, Any]) -> str:
    return "CAD" if profil.get("devise", "CAD") == "CAD" else "cotation"


def mesurer(journal: Journal, agent: str, symbole: str, devise: str) -> dict[str, str]:
    """Volatilité, pire baisse et gain de rattrapage d'un actif, enregistrés dans le journal."""
    vol = journal.appeler(volatilite, agent, symbole=symbole, devise=devise)
    pb = journal.appeler(pire_baisse, agent, symbole=symbole, devise=devise)
    gain = journal.appeler(gain_de_rattrapage, agent, perte=pb)
    return {
        "volatilite": journal.enregistrer(f"vol_{symbole}", vol, f"Volatilité annualisée de {symbole}"),
        "pire_baisse": journal.enregistrer(f"baisse_{symbole}", pb, f"Pire baisse de {symbole} sur la fenêtre"),
        "gain_de_rattrapage": journal.enregistrer(
            f"rattrapage_{symbole}", gain, f"Gain nécessaire pour effacer la pire baisse de {symbole}"),
    }


def outils_marche(journal: Journal, profil: dict[str, Any], agent: str = "Marché et risque") -> list[Callable]:
    from strands import tool

    devise = devise_calcul(profil)

    @tool
    def univers_actifs() -> str:
        """Liste des actifs autorisés (symbole, nom, classe, secteur, devise). Seuls ces symboles existent."""
        return _json(table_univers())

    @tool
    def mesurer_actifs(symboles: list[str]) -> str:
        """Volatilité annualisée, pire baisse et gain de rattrapage de chaque actif, sur la fenêtre
        historique, dans la devise de l'investisseur. Renvoie pour chaque actif les clés des chiffres
        (à écrire entre accolades) et leur valeur arrondie, pour lecture seulement."""
        sortie = []
        for s in symboles[:MAX_SYMBOLES_PAR_APPEL]:
            try:
                cles = mesurer(journal, agent, s, devise)
                sortie.append({"symbole": s, "chiffres": journal.apercu(list(cles.values()))})
            except Exception as e:  # symbole inconnu, données insuffisantes
                sortie.append({"symbole": s, "erreur": f"{type(e).__name__} : {e}"})
        return _json(sortie)

    @tool
    def correlations_actifs(symboles: list[str]) -> str:
        """Corrélations des rendements quotidiens entre ces actifs (jours communs). Une corrélation
        proche de 1 veut dire que les actifs ont bougé ensemble : ils se protègent peu l'un l'autre."""
        symboles = symboles[:8]
        try:
            res = journal.appeler(correlations, agent, symboles=symboles, devise=devise)
        except Exception as e:
            return _json({"erreur": f"{type(e).__name__} : {e}"})
        cles = []
        for i, a in enumerate(symboles):
            for b in symboles[i + 1:]:
                cles.append(journal.enregistrer(f"corr_{a}_{b}", res, f"Corrélation entre {a} et {b}",
                                                chemin=("valeur", a, b)))
        return _json(journal.apercu(cles))

    return [univers_actifs, mesurer_actifs, correlations_actifs]


def outils_constructeur(journal: Journal, profil: dict[str, Any], agent: str = "Constructeur") -> list[Callable]:
    from strands import tool

    devise = devise_calcul(profil)

    @tool
    def univers_actifs() -> str:
        """Liste des actifs autorisés (symbole, nom, classe, secteur, devise). Seuls ces symboles existent."""
        return _json(table_univers())

    @tool
    def tester_portefeuille(poids: dict[str, float]) -> str:
        """Essaie des poids (fractions, somme égale à 1) : volatilité, pire baisse historique et part de
        chaque actif dans le risque. Pour décider seulement : ces chiffres ne s'affichent pas."""
        try:
            stats = journal.appeler(stats_portefeuille, agent, poids=poids, devise=devise)
            parts = journal.appeler(parts_du_risque, agent, poids=poids, devise=devise)
        except Exception as e:
            return _json({"erreur": f"{type(e).__name__} : {e}"})
        return _json({"volatilite": round(stats["valeur"]["volatilite"], 4),
                      "pire_baisse": round(stats["valeur"]["pire_baisse"], 4),
                      "parts_du_risque": {s: round(p, 4) for s, p in parts["valeur"].items()}})

    return [univers_actifs, tester_portefeuille]
