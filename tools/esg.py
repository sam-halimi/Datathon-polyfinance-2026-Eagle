"""Données ESG et regard à travers les FNB.

Lit `data/esg_actions.csv` (20 actions, chaque valeur sourcée et datée) et
`data/fnb_composition.csv` (SPY, QQQ, XIU.TO complets, ESGV réduit à nos titres).
Voir `docs/donnees-esg-fnb.md`.

Ce que ces fonctions ne savent pas, elles le disent : un titre absent de la table ESG a le
statut « information manquante », et la part d'un FNB faite de titres hors table est
chiffrée (`part_inconnue`), jamais comptée comme propre.

Les fichiers se lisent avec `keep_default_na=False` : sinon le symbole « NA » (Banque
Nationale, dans XIU.TO) devient une valeur manquante.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from tools.trace import resultat

DATA = Path(__file__).resolve().parents[1] / "data"
FICHIER_ESG = "data/esg_actions.csv"
FICHIER_FNB = "data/fnb_composition.csv"
CRITERES = ("activite_fossile", "controverse")
INCONNU = "information manquante"


@lru_cache(maxsize=1)
def table_esg() -> pd.DataFrame:
    return pd.read_csv(DATA / "esg_actions.csv", dtype=str, keep_default_na=False).set_index("ticker")


@lru_cache(maxsize=1)
def composition() -> pd.DataFrame:
    f = pd.read_csv(DATA / "fnb_composition.csv", dtype=str, keep_default_na=False)
    f["poids"] = f["poids"].astype(float)
    return f


def fnb_connus() -> list[str]:
    return sorted(composition()["fnb"].unique())


def fiche_esg(symbole: str) -> dict[str, Any]:
    """Fiche ESG d'une action : valeurs, résumé, source et date de chaque valeur.

    Statut « information manquante » si le symbole n'est pas dans la table (FNB, crypto, autre).
    """
    t = table_esg()
    if symbole not in t.index:
        return {"symbole": symbole, "statut": INCONNU, "fichier": FICHIER_ESG,
                "message": f"{symbole} n'est pas dans {FICHIER_ESG} : aucun jugement ESG possible."}
    r = t.loc[symbole]
    return {
        "symbole": symbole, "statut": "connu", "fichier": FICHIER_ESG, "nom": r["nom"],
        "activite_fossile": r["activite_fossile"], "precision_fossile": r["precision_fossile"],
        "controverse": r["controverse"], "resume_controverse": r["resume_controverse"],
        "resume": r["resume"], "retenu_par_esgv": r["retenu_par_esgv"],
        "source_url": r["source_controverse_url"] or r["source_fossile_url"],
        "source_date": r["source_controverse_date"] or r["source_fossile_date"],
        "source_fossile_url": r["source_fossile_url"], "source_fossile_date": r["source_fossile_date"],
        "source_controverse_url": r["source_controverse_url"], "source_controverse_date": r["source_controverse_date"],
        "consulte_le": r["consulte_le"],
    }


def _signale(symbole: str, critere: str) -> str:
    """« oui », « non » ou « inconnu » pour un titre et un critère."""
    t = table_esg()
    if symbole not in t.index:
        return "inconnu"
    return t.at[symbole, critere]


def exposition_fnb(fnb: str, critere: str) -> dict[str, Any]:
    """Part d'un FNB détenue dans des titres signalés « oui » pour le critère.

    `valeur` : fraction de l'actif net du FNB dans les titres « oui » de la table ESG.
    `details.part_inconnue` : 1 - part couverte par la table ESG (titres hors table, liquidités,
    et pour une composition partielle comme ESGV, tout le reste du fonds).
    """
    if critere not in CRITERES:
        raise ValueError(f"critère inconnu {critere!r}, choix : {CRITERES}")
    c = composition()
    lignes = c[c["fnb"] == fnb]
    if lignes.empty:
        raise ValueError(f"{fnb} absent de {FICHIER_FNB} (connus : {fnb_connus()})")
    statut = lignes["symbole_detenu"].map(lambda s: _signale(s, critere))
    oui = lignes[statut == "oui"]
    couverte = float(lignes.loc[statut != "inconnu", "poids"].sum())
    total = float(lignes["poids"].sum())
    complet = total > 0.9
    return resultat(
        outil="exposition_fnb", parametres={"fnb": fnb, "critere": critere},
        periode={"debut": lignes["date"].min(), "fin": lignes["date"].max(), "observations": int(len(lignes))},
        valeur=float(oui["poids"].sum()),
        unite="fraction de l'actif net du FNB",
        formule="somme des poids des titres détenus dont le critère vaut « oui » dans la table ESG",
        sources=[FICHIER_FNB, FICHIER_ESG],
        details={
            "titres_signales": {s: float(w) for s, w in zip(oui["symbole_detenu"], oui["poids"])},
            "part_couverte_par_la_table": couverte,
            "part_inconnue": max(0.0, 1.0 - couverte),
            "composition_complete": complet,
            "date_composition": lignes["date"].max(),
            "avertissement": (
                "La table ESG ne couvre que les 20 actions de l'univers : le reste du FNB n'est pas jugé."
                if complet else
                "Composition partielle (titres de l'univers seulement) : la part du reste du FNB est inconnue."),
        })


def exposition_transparente(poids: dict[str, float], critere: str) -> dict[str, Any]:
    """Part du capital exposée au critère, en direct et à travers les FNB détenus.

    `valeur` : fraction du capital dans des titres « oui », directs ou via un FNB connu.
    `details.part_inconnue` : fraction du capital dont le statut n'est pas connu (FNB hors
    composition, part d'un FNB hors table ESG). Crypto, or et FNB obligataires ne sont pas
    des actions : ils ne comptent ni comme exposés ni comme inconnus.
    """
    from tools.donnees import univers

    u = univers()
    connus = set(fnb_connus())
    direct, via, inconnu, lignes = 0.0, 0.0, 0.0, {}
    for s, w in poids.items():
        classe = u.at[s, "asset_class"] if s in u.index else None
        if classe == "equity":
            v = _signale(s, critere)
            lignes[s] = {"type": "action", "statut": v, "poids": w}
            if v == "oui":
                direct += w
            elif v == "inconnu":
                inconnu += w
        elif classe == "etf_equity":
            if s in connus:
                e = exposition_fnb(s, critere)
                part_inc = e["details"]["part_inconnue"]
                via += w * e["valeur"]
                inconnu += w * part_inc
                lignes[s] = {"type": "FNB", "exposition_du_fnb": e["valeur"], "part_inconnue_du_fnb": part_inc,
                             "date_composition": e["details"]["date_composition"], "poids": w}
            else:
                inconnu += w
                lignes[s] = {"type": "FNB", "statut": "composition absente", "poids": w}
    return resultat(
        outil="exposition_transparente", parametres={"poids": dict(poids), "critere": critere},
        periode={"debut": None, "fin": None, "observations": len(poids)},
        valeur=direct + via,
        unite="fraction du capital",
        formule="Σ poids des actions « oui » + Σ poids du FNB × exposition_fnb(FNB)",
        sources=[FICHIER_ESG, FICHIER_FNB, "data/assets_universe.csv"],
        details={"directe": direct, "a_travers_les_fnb": via, "part_inconnue": inconnu, "lignes": lignes})


def exposition_titre(poids: dict[str, float], symbole: str) -> dict[str, Any]:
    """Exposition réelle du capital à un titre : en direct plus à travers les FNB détenus."""
    c = composition()
    direct = float(poids.get(symbole, 0.0))
    via = {}
    for fnb, w in poids.items():
        ligne = c[(c["fnb"] == fnb) & (c["symbole_detenu"] == symbole)]
        if not ligne.empty:
            via[fnb] = w * float(ligne["poids"].iloc[0])
    return resultat(
        outil="exposition_titre", parametres={"poids": dict(poids), "symbole": symbole},
        periode={"debut": None, "fin": None, "observations": len(poids)},
        valeur=direct + sum(via.values()), unite="fraction du capital",
        formule="poids direct + Σ poids du FNB × poids du titre dans le FNB",
        sources=[FICHIER_FNB],
        details={"directe": direct, "a_travers_les_fnb": via,
                 "fnb_sans_composition": sorted(s for s in poids if _est_fnb_actions(s) and s not in set(fnb_connus()))})


def _est_fnb_actions(symbole: str) -> bool:
    from tools.donnees import univers

    u = univers()
    return symbole in u.index and u.at[symbole, "asset_class"] == "etf_equity"
