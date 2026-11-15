"""correlations, stats_portefeuille et parts_du_risque, sur les vrais CSV.

Exemples de docs/contexte.md (analyses/exemples_explications.py).
"""

import numpy as np
import pytest

from tools.donnees import SymboleInconnu
from tools.mesures import pire_baisse, rendement_annualise, volatilite
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille

EXEMPLE = {"SPY": 0.6, "AGG": 0.3, "BTC-USD": 0.1}


# --- correlations --------------------------------------------------------------

def test_correlations_du_contexte_spy_agg_btc():
    c = correlations(["SPY", "AGG", "BTC-USD"])["valeur"]
    assert round(c["AGG"]["SPY"], 2) == 0.22
    assert round(c["BTC-USD"]["SPY"], 2) == 0.42
    assert round(c["BTC-USD"]["AGG"], 2) == 0.09
    assert c["SPY"]["SPY"] == pytest.approx(1)
    assert c["SPY"]["AGG"] == c["AGG"]["SPY"]


def test_correlations_du_contexte_avec_qqq():
    res = correlations(["MSFT", "NVDA", "QQQ", "SPY"])
    c = res["valeur"]
    assert round(c["NVDA"]["QQQ"], 2) == 0.78
    assert round(c["MSFT"]["QQQ"], 2) == 0.71
    assert round(c["SPY"]["QQQ"], 2) == 0.95
    paires = res["details"]["paires"]
    assert (paires[0]["a"], paires[0]["b"]) == ("QQQ", "SPY")
    assert all(p["forte"] == (p["correlation"] > 0.7) for p in paires)
    assert len(paires) == 6


def test_correlations_jours_communs_et_reference():
    res = correlations(["SPY", "BTC-USD"])
    # Les week-ends crypto sont retirés : on garde les 1 255 jours de bourse américains.
    assert res["periode"]["observations"] == 1255
    assert res["details"]["rendements_quotidiens"] == 1254
    assert res["details"]["alignement"]["dates_retirees"] == 1827 - 1255
    assert res["outil"] == "correlations"
    assert res["parametres"]["symboles"] == ["SPY", "BTC-USD"]


def test_correlations_parametres_invalides():
    with pytest.raises(ValueError):
        correlations(["SPY"])
    with pytest.raises(SymboleInconnu):
        correlations(["SPY", "ZZZZ"])


# --- stats_portefeuille --------------------------------------------------------

def test_volatilite_du_contexte():
    s = stats_portefeuille(EXEMPLE)
    assert round(s["valeur"]["volatilite"] * 100, 1) == 13.9
    assert s["details"]["jours_par_an"] == 252
    # Diversification : moins risqué que la moyenne pondérée des volatilités.
    assert s["details"]["effet_diversification"] > 0


def test_un_seul_actif_retrouve_les_mesures_de_l_actif():
    for symbole in ["SPY", "BTC-USD", "RY.TO"]:
        s = stats_portefeuille({symbole: 1})
        assert s["valeur"]["volatilite"] == pytest.approx(volatilite(symbole)["valeur"])
        assert s["valeur"]["rendement_annualise"] == pytest.approx(
            rendement_annualise(symbole)["valeur"])
        assert s["valeur"]["pire_baisse"] == pytest.approx(pire_baisse(symbole)["valeur"])
        assert s["periode"] == volatilite(symbole)["periode"]


def test_volatilite_egale_ecart_type_des_rendements_du_portefeuille():
    from tools.calendriers import aligner_calendriers
    from tools.donnees import charger_prix
    from tools.mesures import rendements

    r = rendements(aligner_calendriers(charger_prix(list(EXEMPLE)))).dropna()
    rp = r.to_numpy() @ np.array(list(EXEMPLE.values()))
    assert stats_portefeuille(EXEMPLE)["valeur"]["volatilite"] == pytest.approx(
        rp.std(ddof=1) * np.sqrt(252))


def test_cryptos_seules_sur_365_jours():
    s = stats_portefeuille({"BTC-USD": 0.5, "ETH-USD": 0.5})
    assert s["details"]["jours_par_an"] == 365
    assert s["periode"]["observations"] == 1827


def test_devise_cad():
    s = stats_portefeuille(EXEMPLE, devise="CAD")
    assert "fx_usdcad_daily.csv" in s["sources"]
    assert s["valeur"]["volatilite"] != stats_portefeuille(EXEMPLE)["valeur"]["volatilite"]
    # Un portefeuille 100 % canadien ne change pas.
    ca = {"XIU.TO": 0.5, "XBB.TO": 0.5}
    assert stats_portefeuille(ca, devise="CAD")["valeur"] == stats_portefeuille(ca)["valeur"]


def test_poids_invalides():
    with pytest.raises(ValueError):
        stats_portefeuille({"SPY": 0.6, "AGG": 0.3})
    with pytest.raises(ValueError):
        stats_portefeuille({"SPY": 1.2, "AGG": -0.2})
    with pytest.raises(ValueError):
        stats_portefeuille({})
    with pytest.raises(SymboleInconnu):
        stats_portefeuille({"SPY": 0.5, "ZZZZ": 0.5})


# --- parts_du_risque -----------------------------------------------------------

def test_parts_du_risque_du_contexte():
    p = parts_du_risque(EXEMPLE)
    v = p["valeur"]
    assert round(v["BTC-USD"] * 100, 1) == 25.7
    assert round(v["SPY"] * 100, 1) == 69.9
    assert round(v["AGG"] * 100, 1) == 4.4
    assert sum(v.values()) == pytest.approx(1)
    d = p["details"]
    assert round(d["volatilite_portefeuille"] * 100, 1) == 13.9
    assert sum(d["contributions_a_la_volatilite"].values()) == pytest.approx(
        d["volatilite_portefeuille"])
    assert d["du_plus_risque_au_moins_risque"] == ["SPY", "BTC-USD", "AGG"]
    assert d["rapport_risque_sur_capital"]["BTC-USD"] == pytest.approx(v["BTC-USD"] / 0.1)


def test_parts_du_risque_reference_d_appel():
    p = parts_du_risque(EXEMPLE, debut="2023-01-01")
    assert p["outil"] == "parts_du_risque"
    assert p["parametres"]["poids"] == EXEMPLE
    assert p["periode"]["debut"] >= "2023-01-01"
