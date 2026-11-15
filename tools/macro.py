"""Séries macro et taux : lecture, sensibilité d'un actif aux taux, pente de la courbe.

Les séries viennent de `data/base/series.csv`, produit par `python -m tools.ingestion`.
Chaque observation a deux dates : `date` (le jour mesuré) et `date_disponible`
(le jour où elle était publiée). `connue_le` ne garde que ce qui était publié à
cette date : une donnée ne s'utilise jamais avant sa publication.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from tools.calendriers import convertir_cad
from tools.donnees import DATA, FICHIER_FX, FICHIER_PRIX, charger_prix, classe_actif, verifier_symboles
from tools.mesures import DEVISES
from tools.trace import periode_de, resultat

FICHIER_SERIES = "base/series.csv"
COURBES = {
    "États-Unis": ("DGS10", "DGS2"),
    "Canada": ("BD.CDN.10YR.DQ.YLD", "BD.CDN.2YR.DQ.YLD"),
}
ALIAS_PAYS = {
    "etats-unis": "États-Unis", "états-unis": "États-Unis", "us": "États-Unis",
    "usa": "États-Unis", "eu": "États-Unis", "canada": "Canada", "ca": "Canada",
}


class SerieInconnue(KeyError):
    """Série absente de data/base/series.csv."""


@lru_cache(maxsize=None)
def _lire_series() -> pd.DataFrame:
    return pd.read_csv(DATA / FICHIER_SERIES, parse_dates=["date", "date_disponible"])


def description_serie(series_id: str) -> dict[str, Any]:
    """Libellé, unité, fréquence et source d'une série."""
    s = _lire_series()
    lignes = s[s["series_id"] == series_id]
    if lignes.empty:
        raise SerieInconnue(
            f"Série {series_id!r} absente de {FICHIER_SERIES}. "
            f"Séries disponibles : {sorted(s['series_id'].unique())}. "
            "Une série s'ajoute par data/catalogue.csv puis python -m tools.ingestion."
        )
    l = lignes.iloc[0]
    return {"series_id": series_id, "libelle": l["libelle"], "unite": l["unite"],
            "frequence": l["frequence"], "source": l["source"]}


def serie_macro(
    series_id: str, debut: str | None = None, fin: str | None = None, connue_le: str | None = None
) -> pd.Series:
    """Valeurs d'une série indexées par leur date d'observation.

    `debut` et `fin` (inclusifs) portent sur la date d'observation. `connue_le`
    retire les observations qui n'étaient pas encore publiées ce jour-là.
    """
    description_serie(series_id)
    s = _lire_series()
    s = s[s["series_id"] == series_id]
    if connue_le is not None:
        s = s[s["date_disponible"] <= pd.Timestamp(connue_le)]
    if debut is not None:
        s = s[s["date"] >= pd.Timestamp(debut)]
    if fin is not None:
        s = s[s["date"] <= pd.Timestamp(fin)]
    serie = s.set_index("date")["value"].sort_index().astype(float)
    serie.name = series_id
    return serie


def _source_serie(series_id: str) -> str:
    return f"{FICHIER_SERIES} ({series_id}, {description_serie(series_id)['source']})"


def sensibilite_taux(
    symbole: str,
    serie_taux: str = "DGS10",
    debut: str | None = None,
    fin: str | None = None,
    devise: str = "cotation",
) -> dict[str, Any]:
    """Variation de prix d'un actif par point de variation d'un taux (régression).

    Régression linéaire, sur les jours où l'actif et le taux ont tous deux une
    valeur : rendement quotidien = a + b × variation du taux (en points de
    pourcentage). `valeur` = b. Pour un FNB obligataire, b ≈ -duration / 100 :
    TLT perd environ 14 % quand le 10 ans monte d'un point.

    C'est une relation observée sur la fenêtre, pas une prévision. Le taux est
    pris à sa date d'observation, comme le prix : on mesure deux mouvements du
    même jour.
    """
    if devise not in DEVISES:
        raise ValueError(f"devise doit être l'une de {DEVISES}")
    verifier_symboles([symbole])
    desc = description_serie(serie_taux)
    if desc["unite"] != "pourcentage" or desc["frequence"] != "quotidienne":
        raise ValueError(f"{serie_taux} n'est pas un taux quotidien en pourcentage : {desc}")
    prix = charger_prix(symbole, debut, fin)[symbole].dropna()
    if devise == "CAD":
        prix = convertir_cad(prix)
    taux = serie_macro(serie_taux, debut, fin)
    commun = pd.concat([prix.rename("prix"), taux.rename("taux")], axis=1, sort=True).dropna()
    df = pd.DataFrame({"r": commun["prix"].pct_change(), "dy": commun["taux"].diff()}).dropna()
    if len(df) < 20:
        raise ValueError(f"Pas assez de jours communs entre {symbole} et {serie_taux}.")
    b, a = np.polyfit(df["dy"], df["r"], 1)
    r2 = float(np.corrcoef(df["dy"], df["r"])[0, 1] ** 2)
    details: dict[str, Any] = {
        "r2": r2,
        "ordonnee": float(a),
        "jours": int(len(df)),
        "serie_taux": desc,
        "taux_debut": float(commun["taux"].iloc[0]),
        "taux_fin": float(commun["taux"].iloc[-1]),
        "taux_max": float(commun["taux"].max()),
        "date_taux_max": commun["taux"].idxmax().date().isoformat(),
        "methode": "jours où le prix et le taux existent tous les deux ; variations entre ces jours",
        "avertissement": "Relation observée sur la fenêtre ; ne prédit rien.",
    }
    if classe_actif(symbole) == "etf_bond":
        details["duration_implicite_annees"] = float(-b * 100)
    sources = [FICHIER_PRIX + " (adj_close)", _source_serie(serie_taux)]
    if devise == "CAD" and FICHIER_FX not in sources:
        sources.append(FICHIER_FX)
    return resultat(
        outil="sensibilite_taux",
        parametres={"symbole": symbole, "serie_taux": serie_taux, "debut": debut,
                    "fin": fin, "devise": devise},
        periode=periode_de(commun.index),
        valeur=float(b),
        unite="fraction de variation de prix par point de pourcentage de taux",
        formule="rendement quotidien = a + b × variation du taux (points) ; variation de prix ≈ -duration × variation du taux",
        sources=sources,
        details=details,
    )


def _pays(pays: str) -> str:
    if pays in COURBES:
        return pays
    nom = ALIAS_PAYS.get(pays.strip().lower())
    if nom is None:
        raise ValueError(f"Pays non pris en charge : {pays!r}. Choix : {list(COURBES)}")
    return nom


def pente_courbe(
    pays: str, debut: str | None = None, fin: str | None = None, connue_le: str | None = None
) -> dict[str, Any]:
    """Pente de la courbe des taux : taux 10 ans - taux 2 ans, en points.

    `valeur` = dernière pente de la fenêtre. Une pente négative (courbe
    inversée) veut dire que l'État paie plus cher pour 2 ans que pour 10 ans.
    `details` compte les jours de pente négative et date le minimum.
    Seuls les jours où les deux taux sont publiés comptent.
    """
    nom = _pays(pays)
    long_id, court_id = COURBES[nom]
    long_ = serie_macro(long_id, debut, fin, connue_le)
    court = serie_macro(court_id, debut, fin, connue_le)
    pente = (long_ - court).dropna()
    if pente.empty:
        raise ValueError(f"Aucun jour commun pour {long_id} et {court_id} sur la fenêtre.")
    negatifs = pente < 0
    # Plus longue suite de jours consécutifs (de publication) en pente négative.
    groupes = (negatifs != negatifs.shift()).cumsum()
    suites = negatifs.groupby(groupes).agg(["sum", "size"])
    plus_longue = int(suites.loc[suites["sum"] > 0, "size"].max()) if negatifs.any() else 0
    return resultat(
        outil="pente_courbe",
        parametres={"pays": nom, "debut": debut, "fin": fin, "connue_le": connue_le},
        periode=periode_de(pente.index),
        valeur=float(pente.iloc[-1]),
        unite="points de pourcentage",
        formule=f"pente = {long_id} (10 ans) - {court_id} (2 ans)",
        sources=[_source_serie(long_id), _source_serie(court_id)],
        details={
            "date_derniere": pente.index[-1].date().isoformat(),
            "taux_10_ans": float(long_.loc[pente.index[-1]]),
            "taux_2_ans": float(court.loc[pente.index[-1]]),
            "minimum": float(pente.min()),
            "date_minimum": pente.idxmin().date().isoformat(),
            "maximum": float(pente.max()),
            "date_maximum": pente.idxmax().date().isoformat(),
            "jours_negatifs": int(negatifs.sum()),
            "jours": int(len(pente)),
            "plus_longue_inversion_jours": plus_longue,
            "inversee_a_la_fin": bool(pente.iloc[-1] < 0),
        },
    )
