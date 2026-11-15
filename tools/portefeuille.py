"""Mesures sur plusieurs actifs : corrélations, statistiques et parts du risque.

Méthode commune, celle des exemples de docs/contexte.md :

- prix `adj_close` alignés sur les jours où tous les actifs ont coté
  (`aligner_calendriers`, méthode `communs`) : aucun prix inventé ;
- rendements simples quotidiens sur ce calendrier commun ;
- annualisation sur 252 jours (365 si tous les actifs sont des cryptos) ;
- poids constants, c'est-à-dire un portefeuille simulé rééquilibré chaque jour
  (hypothèse affichée dans `details`).

Tout décrit le passé de la fenêtre et ne prédit rien.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.calendriers import aligner_calendriers, convertir_cad
from tools.donnees import FICHIER_FX, FICHIER_PRIX, charger_prix, classe_actif, devise, verifier_symboles
from tools.mesures import DEVISES, pire_baisse_serie, rendements
from tools.trace import periode_de, resultat

TOLERANCE_SOMME = 1e-6
SEUIL_FORTE_CORRELATION = 0.7


def _rendements_communs(
    symboles: list[str], debut: str | None, fin: str | None, devise_calcul: str
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rendements quotidiens sur le calendrier commun, et ce qu'il a fallu retirer."""
    if devise_calcul not in DEVISES:
        raise ValueError(f"devise doit être l'une de {DEVISES}")
    if len(set(symboles)) != len(symboles):
        raise ValueError("Un symbole apparaît deux fois.")
    verifier_symboles(symboles)
    prix = charger_prix(symboles, debut, fin)
    if devise_calcul == "CAD":
        prix = convertir_cad(prix)
    aligne = aligner_calendriers(prix, "communs")
    r = rendements(aligne).dropna(how="any")
    if len(r) < 2:
        raise ValueError(f"Pas assez de jours communs pour {symboles} entre {debut} et {fin}.")
    alignement = {"methode": "jours communs", "premier_prix": aligne.index[0].date().isoformat(),
                  **aligne.attrs["alignement"]}
    return r, alignement


def _periode(r: pd.DataFrame, alignement: dict[str, Any]) -> dict[str, Any]:
    """Période des prix communs (premier prix compris), comme pour un actif seul."""
    return periode_de(r.index.insert(0, pd.Timestamp(alignement["premier_prix"])))


def _sources(symboles: list[str], devise_calcul: str) -> list[str]:
    sources = [FICHIER_PRIX + " (adj_close)"]
    if devise_calcul == "CAD" and any(devise(s) == "USD" for s in symboles):
        sources.append(FICHIER_FX)
    return sources


def _jours_par_an(symboles: list[str]) -> int:
    """365 si tout le portefeuille cote 7 jours sur 7, sinon 252 (jours communs = jours de bourse)."""
    return 365 if all(classe_actif(s) == "crypto" for s in symboles) else 252


def _unite_devise(devise_calcul: str) -> str:
    return "en CAD" if devise_calcul == "CAD" else "en devise de cotation de chaque actif"


def _valider_poids(poids: dict[str, float]) -> tuple[list[str], np.ndarray]:
    if not poids:
        raise ValueError("Le portefeuille est vide.")
    symboles = list(poids)
    w = np.array([float(poids[s]) for s in symboles])
    if (w < 0).any():
        raise ValueError("Poids négatif : pas de vente à découvert dans un portefeuille simulé.")
    if abs(w.sum() - 1) > TOLERANCE_SOMME:
        raise ValueError(f"La somme des poids vaut {w.sum()}, elle doit valoir 1.")
    return symboles, w


def correlations(
    symboles: list[str], debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Matrice des corrélations des rendements quotidiens, sur les jours communs.

    `valeur` : {symbole: {symbole: corrélation}}. `details["paires"]` liste chaque
    paire, de la plus corrélée à la moins corrélée ; une corrélation au-dessus de
    0,7 est signalée comme forte (les deux actifs ont bougé ensemble).
    """
    symboles = list(symboles)
    if len(symboles) < 2:
        raise ValueError("Il faut au moins deux symboles.")
    r, alignement = _rendements_communs(symboles, debut, fin, devise)
    c = r.corr()
    paires = [
        {"a": a, "b": b, "correlation": float(c.at[a, b]),
         "forte": bool(c.at[a, b] > SEUIL_FORTE_CORRELATION)}
        for i, a in enumerate(symboles) for b in symboles[i + 1:]
    ]
    paires.sort(key=lambda p: p["correlation"], reverse=True)
    return resultat(
        outil="correlations",
        parametres={"symboles": symboles, "debut": debut, "fin": fin, "devise": devise},
        periode=_periode(r, alignement),
        valeur={a: {b: float(c.at[a, b]) for b in symboles} for a in symboles},
        unite="coefficient de corrélation de Pearson, entre -1 et 1",
        formule="corr(r_a, r_b) = cov(r_a, r_b) / (σ_a × σ_b), rendements quotidiens des jours communs",
        sources=_sources(symboles, devise),
        details={
            "paires": paires,
            "seuil_forte_correlation": SEUIL_FORTE_CORRELATION,
            "rendements_quotidiens": int(len(r)),
            "alignement": alignement,
        },
    )


def _covariance(poids: dict[str, float], debut, fin, devise_calcul):
    symboles, w = _valider_poids(poids)
    r, alignement = _rendements_communs(symboles, debut, fin, devise_calcul)
    jours = _jours_par_an(symboles)
    cov = r.cov().to_numpy() * jours
    return symboles, w, r, cov, jours, alignement


def stats_portefeuille(
    poids: dict[str, float], debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Volatilité, rendement annualisé et pire baisse d'un portefeuille simulé.

    `poids` : {symbole: fraction du capital}, positifs, somme égale à 1.
    `valeur` : {"volatilite", "rendement_annualise", "pire_baisse"}.
    `details` donne aussi l'effet de diversification : la volatilité qu'aurait
    le portefeuille si tous les actifs bougeaient ensemble (moyenne pondérée des
    volatilités), comparée à la volatilité observée.
    """
    symboles, w, r, cov, jours, alignement = _covariance(poids, debut, fin, devise)
    vol = float(np.sqrt(w @ cov @ w))
    rp = r.to_numpy() @ w
    # Valeur du portefeuille simulé, 1 à la date du premier prix commun.
    premier = pd.Timestamp(alignement["premier_prix"])
    valeur_portefeuille = pd.concat([
        pd.Series([1.0], index=[premier]),
        pd.Series(np.cumprod(1 + rp), index=r.index),
    ])
    annees = (r.index[-1] - premier).days / 365.25
    total = float(valeur_portefeuille.iloc[-1] - 1)
    pb = pire_baisse_serie(valeur_portefeuille)
    vols = np.sqrt(np.diag(cov))
    vol_sans_diversification = float(w @ vols)
    return resultat(
        outil="stats_portefeuille",
        parametres={"poids": dict(poids), "debut": debut, "fin": fin, "devise": devise},
        periode=_periode(r, alignement),
        valeur={
            "volatilite": vol,
            "rendement_annualise": float((1 + total) ** (1 / annees) - 1),
            "pire_baisse": pb["valeur"],
        },
        unite=f"fractions ({_unite_devise(devise)}) ; volatilité et rendement par an",
        formule=(
            f"volatilité = √(wᵀ Σ w), Σ = covariance des rendements quotidiens × {jours} ; "
            "rendement annualisé = (valeur finale) ^ (1 / années) - 1 ; "
            "pire baisse = min(valeur / plus haut atteint jusque-là - 1)"
        ),
        sources=_sources(symboles, devise),
        details={
            "jours_par_an": jours,
            "rendements_quotidiens": int(len(r)),
            "rendement_total": total,
            "annees": annees,
            "pire_baisse": {k: v for k, v in pb.items() if k != "valeur"},
            "volatilites_des_actifs": {s: float(v) for s, v in zip(symboles, vols)},
            "volatilite_sans_diversification": vol_sans_diversification,
            "effet_diversification": vol_sans_diversification - vol,
            "alignement": alignement,
            "hypothese": "Poids constants : portefeuille simulé rééquilibré chaque jour, sans frais.",
            "avertissement": "Chiffres passés sur cette fenêtre ; ne prédisent rien.",
        },
    )


def parts_du_risque(
    poids: dict[str, float], debut: str | None = None, fin: str | None = None, devise: str = "cotation"
) -> dict[str, Any]:
    """Part de chaque actif dans la variance du portefeuille simulé.

    part_i = w_i × (Σ w)_i / (wᵀ Σ w). Les parts somment à 1. Un actif peut peser
    peu dans le capital et beaucoup dans le risque (exemple du contexte :
    10 % de Bitcoin, 25,7 % du risque).
    """
    symboles, w, r, cov, jours, alignement = _covariance(poids, debut, fin, devise)
    variance = float(w @ cov @ w)
    contributions = w * (cov @ w)
    parts = contributions / variance
    vol = np.sqrt(variance)
    ordre = sorted(range(len(symboles)), key=lambda i: parts[i], reverse=True)
    return resultat(
        outil="parts_du_risque",
        parametres={"poids": dict(poids), "debut": debut, "fin": fin, "devise": devise},
        periode=_periode(r, alignement),
        valeur={s: float(p) for s, p in zip(symboles, parts)},
        unite="fraction de la variance du portefeuille (somme = 1)",
        formule="part_i = w_i × (Σ w)_i / (wᵀ Σ w), Σ = covariance annualisée des rendements quotidiens",
        sources=_sources(symboles, devise),
        details={
            "volatilite_portefeuille": float(vol),
            "contributions_a_la_volatilite": {
                s: float(c / vol) for s, c in zip(symboles, contributions)
            },
            "rapport_risque_sur_capital": {
                s: float(parts[i] / w[i]) if w[i] > 0 else None for i, s in enumerate(symboles)
            },
            "du_plus_risque_au_moins_risque": [symboles[i] for i in ordre],
            "jours_par_an": jours,
            "rendements_quotidiens": int(len(r)),
            "alignement": alignement,
            "hypothese": "Poids constants : portefeuille simulé rééquilibré chaque jour.",
        },
    )
