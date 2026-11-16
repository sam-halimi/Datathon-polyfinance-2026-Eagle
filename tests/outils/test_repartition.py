"""tools/repartition.py : marché, FNB (vrais CSV) et ancienneté (fiches Finnhub simulées)."""

import pytest

from tools import api, repartition

POIDS = {"RY.TO": 0.2, "SPY": 0.3, "XBB.TO": 0.3, "RBLX": 0.1, "BTC-USD": 0.1}


def test_part_par_marche_colonne_market():
    assert repartition.part_par_marche(POIDS, "Canada")["valeur"] == pytest.approx(0.5)
    assert repartition.part_par_marche(POIDS, "États-Unis")["valeur"] == pytest.approx(0.4)  # la crypto n'est ni l'un ni l'autre
    with pytest.raises(ValueError):
        repartition.part_par_marche(POIDS, "Europe")


def test_part_fnb():
    assert repartition.part_fnb(POIDS)["valeur"] == pytest.approx(0.6)


class Reponse:
    status_code, text = 200, ""

    def __init__(self, d):
        self.d = d

    def json(self):
        return self.d


class Session:
    FICHES = {"RY": {"name": "Royal Bank of Canada", "exchange": "TORONTO STOCK EXCHANGE", "ipo": "1905-06-17"},
              "RBLX": {"name": "Roblox Corp", "exchange": "NEW YORK STOCK EXCHANGE, INC.", "ipo": "2021-03-10"},
              "CNR": {"name": "Core Natural Resources, Inc.", "exchange": "NEW YORK STOCK EXCHANGE, INC.",
                      "ipo": "2017-01-01"}}

    def get(self, url, params=None, headers=None, timeout=None):
        return Reponse(self.FICHES.get(params["symbol"], {}))


@pytest.fixture
def finnhub_simule(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CACHE", tmp_path)
    monkeypatch.setattr(api, "charger_env", lambda: None)
    monkeypatch.setenv("FINNHUB_API_KEY", "factice")
    return Session()


def test_anciennete_et_symbole_tsx_verifie_par_le_nom(finnhub_simule):
    r = repartition.anciennete_cotation("RY.TO", "2026-11-12", session=finnhub_simule)
    assert r["valeur"] == pytest.approx(121.4, abs=0.1) and r["details"]["symbole_interroge"] == "RY"
    cnr = repartition.anciennete_cotation("CNR.TO", "2026-11-12", session=finnhub_simule)
    assert cnr["valeur"] is None and "ne correspond pas" in cnr["details"]["raison"]  # CNR n'est pas le CN chez Finnhub


def test_part_societes_etablies(finnhub_simule):
    r = repartition.part_societes_etablies({"RY.TO": 0.2, "RBLX": 0.1, "CNR.TO": 0.1, "SPY": 0.6},
                                           date_reference="2026-11-12", session=finnhub_simule)
    assert r["details"]["part_recente"] == pytest.approx(0.1)  # RBLX, cotée depuis 2021
    assert r["details"]["part_inconnue"] == pytest.approx(0.1)  # CNR.TO, fiche refusée
    assert r["valeur"] == pytest.approx(0.2) and "SPY" not in r["details"]["lignes"]
