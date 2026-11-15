"""gain_de_rattrapage et rendement_en_cad, sur les vrais CSV."""

import pytest

from tools.calendriers import taux_usdcad
from tools.donnees import charger_prix
from tools.mesures import gain_de_rattrapage, pire_baisse, rendement_annualise, rendement_en_cad


# --- gain_de_rattrapage --------------------------------------------------------

def test_exemple_du_contexte_tsla():
    # docs/contexte.md : après −73 % (TSLA), il faut +270 % pour revenir.
    g = gain_de_rattrapage(pire_baisse("TSLA"))
    assert round(g["valeur"] * 100) == 270
    assert g["details"]["origine"]["outil"] == "pire_baisse"
    assert g["details"]["origine"]["parametres"]["symbole"] == "TSLA"
    assert g["periode"]["observations"] == 1255


def test_formule_et_signe_ignore():
    assert gain_de_rattrapage(-0.5)["valeur"] == pytest.approx(1.0)
    assert gain_de_rattrapage(0.5)["valeur"] == pytest.approx(1.0)
    assert gain_de_rattrapage(0)["valeur"] == 0
    assert gain_de_rattrapage(-0.2)["valeur"] == pytest.approx(0.25)


def test_perte_totale_refusee():
    with pytest.raises(ValueError):
        gain_de_rattrapage(-1)


# --- rendement_en_cad ----------------------------------------------------------

def test_decomposition_spy():
    r = rendement_en_cad("SPY")
    d = r["details"]
    assert (1 + d["rendement_total_cad"]) == pytest.approx(
        (1 + d["rendement_total_cotation"]) * (1 + d["effet_change_total"]))
    # Le rendement en devise de cotation retrouve le tableau du contexte (11,6 %).
    assert round(d["rendement_annualise_cotation"] * 100, 1) == 11.6
    # Taux de la Banque du Canada aux dates de début et de fin.
    assert d["taux_usdcad_debut"] == pytest.approx(1.2565)
    px = charger_prix("SPY")["SPY"].dropna()
    assert d["taux_usdcad_fin"] == pytest.approx(taux_usdcad(px.index[[-1]]).iloc[0])
    assert "fx_usdcad_daily.csv" in r["sources"]


def test_coherent_avec_rendement_annualise_en_cad():
    for s in ["SPY", "BTC-USD", "XIU.TO"]:
        assert rendement_en_cad(s)["valeur"] == pytest.approx(
            rendement_annualise(s, devise="CAD")["valeur"])


def test_actif_canadien_sans_effet_de_change():
    d = rendement_en_cad("RY.TO")["details"]
    assert d["effet_change_total"] == 0
    assert d["taux_usdcad_debut"] is None
    assert round(d["rendement_annualise_cotation"] * 100, 1) == 21.0


def test_fenetre():
    r = rendement_en_cad("AAPL", debut="2023-01-01", fin="2023-12-31")
    assert r["periode"]["debut"] == "2023-01-03"
    assert r["periode"]["fin"] == "2023-12-29"
