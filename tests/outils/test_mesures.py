"""Les mesures doivent retrouver le tableau de docs/contexte.md.

Tableau produit par analyses/controle_donnees.py : adj_close, devise de
cotation, sans alignement ; volatilité sur 252 jours (365 pour les cryptos).
"""

import json

import numpy as np
import pandas as pd
import pytest

from tools.donnees import SymboleInconnu, charger_prix
from tools.mesures import (
    pire_baisse,
    pire_baisse_serie,
    rendement_annualise,
    rendements,
    volatilite,
)

# actif: (lignes, rendement annualisé %, volatilité %, pire baisse %)
TABLEAU_CONTEXTE = {
    "AAPL": (1255, 19.4, 28.2, -33.4),
    "AGG": (1255, -0.3, 6.2, -17.2),
    "AMZN": (1255, 8.7, 36.7, -55.7),
    "ATD.TO": (1255, 11.4, 24.1, -22.2),
    "BTC-USD": (1827, 2.1, 50.8, -75.9),
    "CNQ.TO": (1255, 28.7, 30.7, -33.1),
    "CNR.TO": (1255, 4.4, 19.9, -27.2),
    "CSU.TO": (1255, 10.0, 30.5, -56.4),
    "ENB.TO": (1255, 12.8, 16.1, -21.4),
    "ESGV": (1255, 10.0, 18.7, -28.8),
    "ETH-USD": (1827, -15.4, 68.5, -78.7),
    "FTS.TO": (1255, 12.7, 14.7, -24.0),
    "GLD": (1255, 15.3, 19.2, -28.4),
    "GOOGL": (1255, 15.2, 32.6, -44.3),
    "JNJ": (1255, 14.6, 18.1, -18.4),
    "JPM": (1255, 18.4, 24.4, -37.9),
    "MFC.TO": (1255, 26.0, 21.6, -21.0),
    "MSFT": (1255, 10.1, 28.5, -37.1),
    "NVDA": (1255, 40.6, 51.9, -66.3),
    "PG": (1255, 5.5, 18.5, -23.8),
    "QQQ": (1255, 12.4, 23.4, -35.1),
    "RY.TO": (1255, 21.0, 15.5, -21.2),
    "SHOP.TO": (1255, 0.0, 64.4, -83.5),
    "SPY": (1255, 11.6, 17.3, -24.5),
    "TD.TO": (1255, 18.5, 17.7, -26.1),
    "TLT": (1255, -8.3, 15.6, -43.7),
    "TSLA": (1255, 2.9, 59.6, -73.0),
    "XBB.TO": (1255, 0.7, 6.6, -15.5),
    "XIU.TO": (1255, 13.7, 13.1, -16.4),
    "XOM": (1255, 25.6, 26.7, -20.5),
    "ZST.TO": (1255, 3.4, 0.6, -0.4),
}


def en_pourcent_arrondi(x: float) -> float:
    # +0.0 pour éviter -0.0 (SHOP.TO)
    return round(x * 100, 1) + 0.0


def test_tableau_couvre_tout_l_univers():
    assert set(TABLEAU_CONTEXTE) == set(charger_prix().columns)


@pytest.mark.parametrize("symbole", sorted(TABLEAU_CONTEXTE))
def test_retrouve_le_tableau_du_contexte(symbole):
    lignes, rend, vol, pire = TABLEAU_CONTEXTE[symbole]
    v = volatilite(symbole)
    assert v["periode"]["observations"] == lignes
    assert en_pourcent_arrondi(rendement_annualise(symbole)["valeur"]) == rend
    assert en_pourcent_arrondi(v["valeur"]) == vol
    assert en_pourcent_arrondi(pire_baisse(symbole)["valeur"]) == pire


# --- rendements --------------------------------------------------------------

def test_rendement_quotidien_a_la_main():
    px = charger_prix("AAPL")["AAPL"]
    r = rendements(px)
    assert np.isnan(r.iloc[0])
    assert r.iloc[1] == pytest.approx(px.iloc[1] / px.iloc[0] - 1)


def test_rendements_sautent_les_jours_sans_cotation():
    px = charger_prix(["SPY", "BTC-USD"])
    r = rendements(px)
    # Un jour sans cotation reste vide : jamais de rendement nul inventé.
    assert r["SPY"].notna().sum() == 1254
    assert r["BTC-USD"].notna().sum() == 1826
    # Le lundi couvre le vendredi -> lundi.
    lundi, vendredi = pd.Timestamp("2022-01-10"), pd.Timestamp("2022-01-07")
    assert r.loc[lundi, "SPY"] == pytest.approx(px.loc[lundi, "SPY"] / px.loc[vendredi, "SPY"] - 1)


# --- pire baisse ---------------------------------------------------------------

def test_pire_baisse_serie_simple():
    s = pd.Series([100, 120, 90, 60, 80, 130, 110],
                  index=pd.date_range("2024-01-01", periods=7))
    pb = pire_baisse_serie(s)
    assert pb["valeur"] == pytest.approx(60 / 120 - 1)
    assert pb["date_pic"] == "2024-01-02"
    assert pb["date_creux"] == "2024-01-04"
    assert pb["date_retour"] == "2024-01-06"


def test_pire_baisse_tsla_dates_et_rattrapage():
    pb = pire_baisse("TSLA")
    px = charger_prix("TSLA")["TSLA"]
    d = pb["details"]
    assert px[d["date_creux"]] / px[d["date_pic"]] - 1 == pytest.approx(pb["valeur"])
    assert d["date_pic"] < d["date_creux"]


def test_pire_baisse_sans_retour_au_sommet():
    # TLT n'a pas retrouvé son sommet de décembre 2021 dans la fenêtre.
    d = pire_baisse("TLT")["details"]
    assert d["date_pic"] == "2021-12-03"
    assert d["date_creux"] == "2023-10-19"
    assert d["date_retour"] is None
    assert d["retour_au_sommet"] is False


# --- fenêtre et devise ---------------------------------------------------------

def test_fenetre_restreinte():
    v = volatilite("SPY", debut="2022-01-01", fin="2022-12-31")
    assert v["periode"]["debut"] == "2022-01-03"
    assert v["periode"]["fin"] == "2022-12-30"
    assert v["parametres"] == {"symbole": "SPY", "debut": "2022-01-01",
                               "fin": "2022-12-31", "devise": "cotation"}


def test_devise_cad_change_les_actifs_usd_seulement():
    assert volatilite("RY.TO", devise="CAD")["valeur"] == volatilite("RY.TO")["valeur"]
    spy_usd, spy_cad = volatilite("SPY"), volatilite("SPY", devise="CAD")
    assert spy_cad["valeur"] != spy_usd["valeur"]
    assert "fx_usdcad_daily.csv" in spy_cad["sources"]
    assert spy_cad["unite"].endswith("CAD")


def test_parametres_invalides():
    with pytest.raises(ValueError):
        volatilite("SPY", devise="EUR")
    with pytest.raises(ValueError):
        volatilite("SPY", debut="2030-01-01")
    with pytest.raises(SymboleInconnu):
        pire_baisse("ZZZZ")


# --- référence d'appel -----------------------------------------------------------

@pytest.mark.parametrize("outil", [volatilite, pire_baisse, rendement_annualise])
def test_reference_d_appel_complete_et_serialisable(outil):
    r = outil("NVDA")
    for cle in ("outil", "parametres", "periode", "valeur", "unite", "formule", "sources"):
        assert r[cle] not in (None, "", {}, [])
    assert r["outil"] == outil.__name__
    json.dumps(r)  # l'agent doit pouvoir le transmettre tel quel
