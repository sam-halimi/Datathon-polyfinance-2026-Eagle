"""Conversion en CAD et alignement des calendriers.

Trois calendriers coexistent : TSX, marchés américains, crypto 7 jours sur 7.
Le taux USD/CAD de la Banque du Canada n'existe que les jours ouvrables
canadiens : on reporte le dernier taux publié (jours fériés canadiens,
week-ends pour les cryptos). Jamais de taux futur.
"""

from __future__ import annotations

import pandas as pd

from tools.donnees import devise, taux_change

METHODES_ALIGNEMENT = ("communs", "report")


def taux_usdcad(dates: pd.Index) -> pd.Series:
    """Taux USD/CAD applicable à chaque date : dernier taux publié à cette date ou avant.

    NaN pour une date antérieure au premier taux disponible.
    """
    fx = taux_change()["usdcad"]
    dates = pd.DatetimeIndex(dates)
    return fx.reindex(fx.index.union(dates)).ffill().reindex(dates)


def convertir_cad(prix: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Convertit en CAD des prix en devise de cotation.

    `prix` : sortie de `charger_prix` (colonnes = symboles), ou une Series nommée
    par son symbole. Les colonnes en CAD restent inchangées, les colonnes en USD
    sont multipliées par le taux USD/CAD du jour (dernier taux reporté si la
    Banque du Canada n'a pas publié ce jour-là). Les cases vides restent vides.
    """
    if isinstance(prix, pd.Series):
        if prix.name is None:
            raise ValueError("La Series doit être nommée par son symbole.")
        return convertir_cad(prix.to_frame())[prix.name]

    taux = taux_usdcad(prix.index)
    sortie = prix.copy()
    for symbole in prix.columns:
        d = devise(symbole)
        if d == "USD":
            sortie[symbole] = prix[symbole] * taux.values
        elif d != "CAD":
            raise ValueError(f"Devise non prise en charge pour {symbole} : {d}")
    jours_reportes = prix.index.difference(taux_change().index)
    sortie.attrs = {
        **prix.attrs,
        "devise": "CAD",
        "conversion": {
            "source": "fx_usdcad_daily.csv (Banque du Canada, FXUSDCAD)",
            "regle": "prix USD × taux USD/CAD du jour, dernier taux reporté sinon",
            "jours_taux_reporte": int(len(jours_reportes)),
        },
    }
    return sortie


def aligner_calendriers(prix: pd.DataFrame, methode: str = "communs") -> pd.DataFrame:
    """Met plusieurs actifs sur un même calendrier.

    - `communs` (défaut) : garde seulement les dates où tous les actifs ont un
      prix. Aucune valeur inventée ; on perd les jours fériés propres à un marché
      et les week-ends crypto.
    - `report` : union des dates, à partir de la première date où tous les actifs
      ont un prix, avec report du dernier prix connu. Jamais de report vers le
      passé. Limite : un actif reporté affiche un rendement nul ce jour-là, ce qui
      sous-estime un peu sa volatilité.

    Le nombre de dates retirées ou reportées est noté dans `attrs["alignement"]`.
    """
    if methode not in METHODES_ALIGNEMENT:
        raise ValueError(f"methode doit être l'une de {METHODES_ALIGNEMENT}")
    if prix.empty:
        return prix.copy()

    if methode == "communs":
        aligne = prix.dropna(how="any")
        info = {"dates_retirees": int(len(prix) - len(aligne)), "valeurs_reportees": 0}
    else:
        depart = prix.apply(pd.Series.first_valid_index).max()
        base = prix.loc[depart:]
        aligne = base.ffill()
        info = {
            "dates_retirees": int(len(prix) - len(base)),
            "valeurs_reportees": int(base.isna().sum().sum()),
        }
    aligne = aligne.copy()
    aligne.attrs = {**prix.attrs, "alignement": {"methode": methode, **info}}
    return aligne
