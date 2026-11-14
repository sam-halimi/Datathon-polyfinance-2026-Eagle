"""Mesures historiques d'un actif : rendements, volatilité, pire baisse.

Toutes les mesures portent sur `adj_close` (dividendes inclus). Elles décrivent
le passé de la fenêtre étudiée et ne prédisent rien. Chaque fonction publique
qui produit un chiffre renvoie un dictionnaire `trace.resultat`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.calendriers import convertir_cad
from tools.donnees import FICHIER_FX, FICHIER_PRIX, charger_prix, jours_par_an
from tools.donnees import devise as devise_cotation
from tools.trace import periode_de, resultat

DEVISES = ("cotation", "CAD")


def rendements(prix: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Rendements simples quotidiens, p_t / p_{t-1} - 1.

    Chaque actif est calculé sur son propre calendrier : un jour sans cotation
    n'est pas un rendement nul, il est sauté (le rendement suivant couvre les
    deux jours). La première date de chaque actif n'a pas de rendement (NaN).
    Pour comparer plusieurs actifs jour par jour, aligner les prix d'abord
    avec `aligner_calendriers`.
    """
    if isinstance(prix, pd.Series):
        return prix.dropna().pct_change().reindex(prix.index)
    return prix.apply(lambda s: s.dropna().pct_change().reindex(s.index))


def _prix_actif(symbole: str, debut: str | None, fin: str | None, devise_calcul: str) -> pd.Series:
    if devise_calcul not in DEVISES:
        raise ValueError(f"devise doit être l'une de {DEVISES}")
    s = charger_prix(symbole, debut, fin)[symbole].dropna()
    if len(s) < 2:
        raise ValueError(f"Pas assez de prix pour {symbole} entre {debut} et {fin}.")
    if devise_calcul == "CAD":
        s = convertir_cad(s)
    return s


def _contexte(symbole: str, debut: str | None, fin: str | None, devise_calcul: str) -> dict[str, Any]:
    parametres = {"symbole": symbole, "debut": debut, "fin": fin, "devise": devise_calcul}
    sources = [FICHIER_PRIX + " (adj_close)"]
    if devise_calcul == "CAD" and devise_cotation(symbole) == "USD":
        sources.append(FICHIER_FX)
    return {"parametres": parametres, "sources": sources}


def _devise_affichee(symbole: str, devise_calcul: str) -> str:
    return "CAD" if devise_calcul == "CAD" else devise_cotation(symbole)


def volatilite_annualisee(r: pd.Series, jours: int) -> float:
    """Écart-type des rendements quotidiens (ddof = 1) × √jours."""
    return float(r.dropna().std() * np.sqrt(jours))


def pire_baisse_serie(prix: pd.Series) -> dict[str, Any]:
    """Plus forte baisse d'un sommet au creux suivant, avec ses dates."""
    prix = prix.dropna()
    sommet_courant = prix.cummax()
    baisse = prix / sommet_courant - 1
    date_creux = baisse.idxmin()
    date_pic = prix.loc[:date_creux].idxmax()
    niveau_pic = prix.loc[date_pic]
    apres = prix.loc[date_creux:]
    retour = apres[apres >= niveau_pic]
    return {
        "valeur": float(baisse.min()),
        "date_pic": date_pic.date().isoformat(),
        "date_creux": date_creux.date().isoformat(),
        "date_retour": retour.index[0].date().isoformat() if len(retour) else None,
    }


def rendement_annualise(
    symbole: str, debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Rendement annualisé historique (taux composé) sur la fenêtre.

    (prix_fin / prix_debut) ^ (1 / années) - 1, années = jours civils / 365,25.
    Décrit le passé de la fenêtre, ne prédit rien.
    """
    s = _prix_actif(symbole, debut, fin, devise)
    annees = (s.index[-1] - s.index[0]).days / 365.25
    total = s.iloc[-1] / s.iloc[0] - 1
    valeur = (1 + total) ** (1 / annees) - 1
    return resultat(
        outil="rendement_annualise",
        periode=periode_de(s.index),
        valeur=float(valeur),
        unite=f"fraction par an, en {_devise_affichee(symbole, devise)}",
        formule="(prix_fin / prix_debut) ^ (1 / années) - 1, années = jours civils / 365,25",
        details={
            "rendement_total": float(total),
            "annees": annees,
            "prix_debut": float(s.iloc[0]),
            "prix_fin": float(s.iloc[-1]),
            "avertissement": "Rendement passé sur cette fenêtre ; ne prédit rien.",
        },
        **_contexte(symbole, debut, fin, devise),
    )


def volatilite(
    symbole: str, debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Volatilité annualisée : écart-type des rendements quotidiens × √252 (√365 en crypto)."""
    s = _prix_actif(symbole, debut, fin, devise)
    r = rendements(s).dropna()
    jours = jours_par_an(symbole)
    return resultat(
        outil="volatilite",
        periode=periode_de(s.index),
        valeur=volatilite_annualisee(r, jours),
        unite=f"fraction annualisée, en {_devise_affichee(symbole, devise)}",
        formule=f"écart-type des rendements quotidiens × √{jours}",
        details={
            "jours_par_an": jours,
            "rendements_quotidiens": int(len(r)),
            "plus_grand_mouvement_1_jour": float(r.abs().max()),
        },
        **_contexte(symbole, debut, fin, devise),
    )


def pire_baisse(
    symbole: str, debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Pire baisse (drawdown maximal) : min(prix / plus haut antérieur - 1), avec dates."""
    s = _prix_actif(symbole, debut, fin, devise)
    pb = pire_baisse_serie(s)
    return resultat(
        outil="pire_baisse",
        periode=periode_de(s.index),
        valeur=pb.pop("valeur"),
        unite=f"fraction, en {_devise_affichee(symbole, devise)}",
        formule="min sur la fenêtre de (prix / plus haut atteint jusque-là - 1)",
        details={**pb, "retour_au_sommet": pb["date_retour"] is not None},
        **_contexte(symbole, debut, fin, devise),
    )
