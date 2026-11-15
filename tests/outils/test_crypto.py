"""tools/crypto.py avec une réponse CoinGecko simulée."""

import pytest

from tools import api, crypto

REPONSE = [{"id": "bitcoin", "current_price": 1.5, "market_cap": 10.0, "total_volume": 2.0,
            "last_updated": "2026-11-15T20:00:00.000Z"},
           {"id": "ethereum", "current_price": 0.5, "market_cap": 4.0, "total_volume": 1.0,
            "last_updated": "2026-11-15T20:00:00.000Z"}]


class Reponse:
    status_code, text = 200, ""

    def json(self):
        return REPONSE


class Session:
    def __init__(self):
        self.appels = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.appels += 1
        assert "days" not in (params or {})  # jamais d'historique demandé à CoinGecko
        return Reponse()


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CACHE", tmp_path)
    monkeypatch.setattr(api, "charger_env", lambda: None)
    monkeypatch.setenv("COINGECKO_API_KEY", "factice")


def test_trois_mesures_un_seul_appel_grace_au_cache():
    s = Session()
    assert crypto.marche_crypto("BTC-USD", "capitalisation", session=s)["valeur"] == 10.0
    assert crypto.marche_crypto("ETH-USD", "volume_24h", session=s)["valeur"] == 1.0
    assert crypto.marche_crypto("ETH-USD", "prix", session=s)["valeur"] == 0.5
    assert s.appels == 1


def test_mention_coingecko_dans_la_reference():
    r = crypto.marche_crypto("BTC-USD", session=Session())
    assert "Powered by CoinGecko" in r["sources"][0] and r["periode"]["debut"] == "2026-11-15"


def test_cache_de_24_heures_au_plus():
    assert crypto.FRAICHEUR_H <= 24


def test_symbole_non_suivi():
    with pytest.raises(ValueError):
        crypto.marche_crypto("SPY", session=Session())
