"""Activités sensibles : tabac, armement, jeux d'argent, alcool.

Lit `data/activites_sensibles.csv` : une ligne par action (univers de départ, univers étendu, titres
des thèmes), une valeur « oui », « non » ou « inconnu » par activité, et une source par valeur (dépôt
annuel, page de la société, ou méthodologie d'exclusion de l'indice suivi par ESGV pour les titres
qu'il détient).

Regard à travers les FNB : `data/fnb_composition.csv`, comme `tools/esg.py`. Ce qui n'est pas dans la
table n'est jamais compté comme propre : c'est la part inconnue.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from tools.donnees import DATA, univers
from tools.esg import composition, fnb_connus
from tools.trace import resultat

FICHIER = "data/activites_sensibles.csv"
ACTIVITES = ("tabac", "armement", "jeux_argent", "alcool")
LIBELLES = {"tabac": "tabac", "armement": "armement", "jeux_argent": "jeux d'argent", "alcool": "alcool"}
# Le libellé précédé de « à » dans une phrase : « liée au tabac », « liée à l'armement ».
AVEC_A = {"tabac": "au tabac", "armement": "à l'armement", "jeux_argent": "aux jeux d'argent", "alcool": "à l'alcool"}


@lru_cache(maxsize=1)
def table_activites() -> pd.DataFrame:
    """La table, ou une table vide si le fichier manque : tout vaut alors « inconnu », jamais « non »."""
    chemin = DATA / "activites_sensibles.csv"
    if not chemin.is_file():
        return pd.DataFrame(columns=["ticker", *ACTIVITES]).set_index("ticker")
    return pd.read_csv(chemin, dtype=str, keep_default_na=False).set_index("ticker")


def _valeur(symbole: str, activite: str) -> str:
    t = table_activites()
    return t.at[symbole, activite] if symbole in t.index else "inconnu"


def fiche_activites(symbole: str) -> dict[str, Any]:
    """Valeurs et sources d'une action ; « information manquante » si elle n'est pas dans la table."""
    t = table_activites()
    if symbole not in t.index:
        return {"symbole": symbole, "statut": "information manquante", "fichier": FICHIER}
    r = t.loc[symbole]
    return {"symbole": symbole, "statut": "connu", "fichier": FICHIER,
            **{a: {"valeur": r[a], "source_url": r[f"{a}_source_url"], "source_date": r[f"{a}_source_date"],
                   "extrait": r[f"{a}_extrait"]} for a in ACTIVITES}}


def exposition_activite(poids: dict[str, float], activite: str) -> dict[str, Any]:
    """Part du capital exposée à une activité, en direct et à travers les FNB de data/fnb_composition.csv.

    `details.part_inconnue` : actions absentes de la table ou « inconnu », et part des FNB non jugée
    (titres hors table, ou FNB sans composition). Obligations, or et crypto ne sont pas des sociétés.
    """
    if activite not in ACTIVITES:
        raise ValueError(f"activité inconnue {activite!r}, choix : {ACTIVITES}")
    u = univers(etendu=True)
    comp, connus = composition(), set(fnb_connus())
    directe, via, inconnue, lignes = 0.0, 0.0, 0.0, {}
    for s, w in poids.items():
        classe = u.at[s, "asset_class"] if s in u.index else None
        if classe == "equity":
            v = _valeur(s, activite)
            lignes[s] = {"type": "action", "valeur": v, "poids": w}
            directe += w if v == "oui" else 0.0
            inconnue += w if v == "inconnu" else 0.0
        elif classe == "etf_equity":
            if s not in connus:
                inconnue += w
                lignes[s] = {"type": "FNB", "statut": "composition absente", "poids": w}
                continue
            c = comp[comp["fnb"] == s]
            statut = c["symbole_detenu"].map(lambda x: _valeur(x, activite))
            oui = float(c.loc[statut == "oui", "poids"].sum())
            jugee = float(c.loc[statut != "inconnu", "poids"].sum())
            via += w * oui
            inconnue += w * max(0.0, 1.0 - jugee)
            lignes[s] = {"type": "FNB", "exposition_du_fnb": oui, "part_jugee_du_fnb": jugee,
                         "titres_oui": sorted(c.loc[statut == "oui", "symbole_detenu"]), "poids": w,
                         "date_composition": c["date"].max()}
    return resultat(
        outil="exposition_activite", parametres={"poids": dict(poids), "activite": activite},
        periode={"debut": None, "fin": None, "observations": len(poids)},
        valeur=directe + via, unite="fraction du capital",
        formule="Σ poids des actions « oui » + Σ poids du FNB × part du FNB dans des actions « oui »",
        sources=[FICHIER, "data/fnb_composition.csv", "data/assets_universe.csv", "data/univers_etendu.csv"],
        details={"directe": directe, "a_travers_les_fnb": via, "part_inconnue": inconnue, "lignes": lignes,
                 "activite": LIBELLES[activite]})
