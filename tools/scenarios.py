"""Éventail de scénarios et fiche d'un actif face à un profil.

Rien ici n'est une prévision. L'éventail rejoue au hasard les mois réellement observés
pour montrer l'étendue de ce qui aurait pu arriver si l'avenir ressemblait à la fenêtre de
données. L'avenir peut sortir de cet éventail.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd

from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE, tolerance_normalisee
from tools.mesures import gain_de_rattrapage, pire_baisse, volatilite
from tools.portefeuille import _covariance, _periode, _sources, _unite_devise
from tools.trace import resultat

CENTILES = (10, 25, 50, 75, 90)
HORIZON_MAX = 30
CLASSES = {"equity": "action", "etf_equity": "FNB d'actions", "etf_bond": "FNB obligataire",
           "etf_commodity": "FNB lié à l'or", "crypto": "cryptoactif"}


def eventail_scenarios(poids: dict[str, float], horizon_annees: int, capital: float = 10_000.0,
                       devise: str = "CAD", tirages: int = 2000, graine: int = 2026) -> dict[str, Any]:
    """Étendue des valeurs possibles d'un portefeuille simulé, année par année.

    Méthode : les rendements mensuels observés du portefeuille (poids constants) sont
    tirés au hasard avec remise, `tirages` fois, sur `horizon_annees`. `valeur` donne,
    pour chaque année, les centiles 10, 25, 50, 75 et 90 de la valeur atteinte.
    Même graine, mêmes chiffres : le résultat se reproduit.
    """
    horizon = int(horizon_annees)
    if not 1 <= horizon <= HORIZON_MAX:
        raise ValueError(f"horizon_annees doit être entre 1 et {HORIZON_MAX} (reçu : {horizon_annees})")
    if capital <= 0:
        raise ValueError("capital doit être positif")
    symboles, w, r, _cov, _jours, alignement = _covariance(poids, None, None, devise)
    quotidiens = pd.Series(r.to_numpy() @ w, index=r.index)
    mensuels = (1 + quotidiens).groupby([quotidiens.index.year, quotidiens.index.month]).prod() - 1
    alea = np.random.default_rng(graine)
    tires = alea.choice(mensuels.to_numpy(), size=(tirages, horizon * 12), replace=True)
    chemins = capital * np.cumprod(1 + tires, axis=1)
    fins_d_annee = chemins[:, 11::12]
    bandes = {f"p{c}": [float(capital)] + [float(v) for v in np.percentile(fins_d_annee, c, axis=0)]
              for c in CENTILES}
    finale = chemins[:, -1]
    return resultat(
        outil="eventail_scenarios",
        parametres={"poids": dict(poids), "horizon_annees": horizon, "capital": float(capital),
                    "devise": devise, "tirages": tirages, "graine": graine},
        periode=_periode(r, alignement),
        valeur={"annees": list(range(horizon + 1)), **bandes},
        unite=f"valeur du portefeuille simulé ({_unite_devise(devise)}), capital de départ {capital:g}",
        formule=("rendements mensuels observés du portefeuille, tirés au hasard avec remise ; "
                 "valeur = capital × ∏(1 + rendement mensuel tiré) ; centiles 10, 25, 50, 75, 90 par année"),
        sources=_sources(symboles, devise),
        details={
            "mois_observes": int(len(mensuels)),
            "tirages": tirages,
            "graine": graine,
            "part_des_scenarios_sous_le_capital": float((finale < capital).mean()),
            "pire_mois_observe": float(mensuels.min()),
            "meilleur_mois_observe": float(mensuels.max()),
            "hypotheses": [
                "Poids constants, sans frais, sans impôts, sans inflation.",
                "Les mois futurs ressemblent aux mois observés et sont indépendants entre eux.",
                "L'éventail hérite du rendement moyen de la fenêtre observée, qui ne se répétera pas forcément.",
            ],
            "avertissement": (
                f"Ce n'est pas une prévision. L'éventail repose sur {len(mensuels)} mois observés "
                "seulement : l'avenir peut en sortir, vers le haut comme vers le bas."),
        },
    )


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


def trouver_symbole(demande: str) -> str | None:
    """Retrouve un symbole de la table sourcée à partir d'un symbole ou d'un nom (« tesla », « TSLA »)."""
    table = univers(etendu=True)
    brut = demande.strip()
    for symbole in table.index:
        if brut.upper() in (symbole.upper(), symbole.upper().removesuffix(".TO"), symbole.upper().removesuffix("-USD")):
            return symbole
    cle = _sans_accents(brut)
    if len(cle) < 3:
        return None
    for symbole, nom in table["name"].items():
        if cle in _sans_accents(nom):
            return symbole
    return None


def fiche_actif(symbole: str, tolerance: str, horizon_annees: int) -> dict[str, Any]:
    """Un actif confronté à un profil : mesures passées, limites du profil, verdict calculé.

    Le verdict vient de règles, pas d'un modèle. Statuts : « compatible », « à plafonner »
    (possible seulement en petite position), « hors profil ».
    """
    trouve = trouver_symbole(symbole)
    if trouve is None:
        return {"statut": "inconnu", "symbole": symbole,
                "titre": f"« {symbole} » n'est pas dans la table des actifs",
                "raisons": ["Seuls les actifs de data/assets_universe.csv et de data/univers_etendu.csv sont mesurés. Aucun chiffre n'est donné sans donnée."]}
    ligne = univers(etendu=True).loc[trouve]
    niveau, note = tolerance_normalisee(tolerance)
    seuils = SEUILS_PAR_TOLERANCE[niveau]
    vol, pb = volatilite(trouve), pire_baisse(trouve)
    gain = gain_de_rattrapage(pb)
    classe = ligne["asset_class"]
    plafond_crypto = 0.0 if int(horizon_annees) < 5 else seuils["crypto"]

    def pct(x: float, decimales: int = 1) -> str:
        return f"{x * 100:.{decimales}f} %".replace(".", ",")

    raisons, statut = [], "compatible"
    if vol["valeur"] > seuils["volatilite"]:
        raisons.append(f"Volatilité de {pct(vol['valeur'])} par an sur la fenêtre, pour un seuil de "
                       f"{pct(seuils['volatilite'], 0)} pour un portefeuille de tolérance « {niveau} ».")
    if pb["valeur"] < seuils["pire_baisse"]:
        raisons.append(f"Pire baisse de {pct(pb['valeur'])} (du {pb['details']['date_pic']} au "
                       f"{pb['details']['date_creux']}), pour un plancher de {pct(seuils['pire_baisse'], 0)}. "
                       f"Après une telle baisse, il faut un gain de {pct(gain['valeur'], 0)} pour revenir.")
    if classe == "crypto":
        if plafond_crypto == 0:
            statut = "hors profil"
            raisons.insert(0, "Aucun cryptoactif pour ce profil"
                           + (" : horizon de moins de 5 ans." if int(horizon_annees) < 5 else f" : tolérance « {niveau} »."))
        else:
            statut = "à plafonner"
            raisons.insert(0, f"Cryptoactifs plafonnés à {pct(plafond_crypto, 0)} du capital pour ce profil.")
    elif classe == "equity" and raisons:
        statut = "à plafonner"
        raisons.append(f"Possible seulement en petite position : {pct(seuils['titre'], 0)} du capital au plus par titre.")
    elif raisons:
        statut = "à plafonner"
        raisons.append("À doser : seul, cet actif dépasse les seuils du profil. Le portefeuille entier doit les respecter.")
    if not raisons:
        raisons.append(f"Volatilité de {pct(vol['valeur'])} et pire baisse de {pct(pb['valeur'])} sur la fenêtre : "
                       f"dans les seuils d'un portefeuille de tolérance « {niveau} ».")
    if classe == "equity" and statut == "compatible":
        raisons.append(f"Plafond par titre du profil : {pct(seuils['titre'], 0)} du capital.")
    titres = {"compatible": f"{ligne['name']} est compatible avec ce profil",
              "à plafonner": f"{ligne['name']} ne convient pas en grosse position pour ce profil",
              "hors profil": f"{ligne['name']} ne convient pas à ce profil"}
    return {
        "statut": statut, "symbole": trouve, "nom": ligne["name"], "classe": CLASSES.get(classe, classe),
        "secteur": ligne["sector"], "tolerance": niveau, "horizon_annees": int(horizon_annees),
        "titre": titres[statut], "raisons": raisons,
        "plafond_par_titre": seuils["titre"] if classe == "equity" else None,
        "plafond_crypto": plafond_crypto if classe == "crypto" else None,
        "chiffres": {"volatilite": vol, "pire_baisse": pb, "gain_de_rattrapage": gain},
        "notes": [n for n in (note, "Mesures passées sur la fenêtre de données. Elles ne prédisent rien.",
                              "Simulation uniquement.") if n],
    }
