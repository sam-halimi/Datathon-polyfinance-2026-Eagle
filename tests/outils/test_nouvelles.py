"""tools/nouvelles.py avec des réponses Finnhub simulées."""

import pytest

from tools import api, nouvelles


class Reponse:
    status_code = 200

    def __init__(self, d):
        self._d, self.text = d, ""

    def json(self):
        return self._d


class Session:
    def __init__(self, d):
        self.d, self.appels = d, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.appels.append(url)
        return Reponse(self.d)


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CACHE", tmp_path)
    monkeypatch.setattr(api, "charger_env", lambda: None)
    monkeypatch.setenv("FINNHUB_API_KEY", "factice")


def test_fiche_societe():
    r = nouvelles.fiche_societe("AAPL", session=Session({"name": "Apple Inc", "exchange": "NASDAQ", "ipo": "1980-12-12"}))
    assert r["valeur"] is True and r["details"]["exchange"] == "NASDAQ" and r["outil"] == "fiche_societe"


def test_nouvelles_triees_avec_source_et_lien():
    brut = [{"datetime": 1762905600, "headline": "A", "source": "Reuters", "url": "https://exemple.org/a"},
            {"datetime": 1763078400, "headline": "B", "source": "AP", "url": "https://exemple.org/b"}]
    r = nouvelles.nouvelles("AAPL", jours=7, fin="2026-11-15", session=Session(brut))
    assert r["valeur"] == 2 and r["details"]["articles"][0]["titre"] == "B"
    assert r["parametres"] == {"symbole": "AAPL", "debut": "2026-11-08", "fin": "2026-11-15"}


def test_jamais_de_cours_demandes_a_finnhub():
    import inspect

    assert "candle" not in inspect.getsource(nouvelles)


def test_actions_americaines_de_l_univers():
    s = nouvelles.actions_americaines()
    assert "AAPL" in s and "TTWO" in s and "RY.TO" not in s and "SPY" not in s
