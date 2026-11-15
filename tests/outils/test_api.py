"""tools/api.py avec des réponses simulées : cache, clés jamais écrites, mode proxy."""

import json

import pytest

from tools import api


class Reponse:
    def __init__(self, statut, donnees):
        self.status_code, self._d = statut, donnees
        self.text = json.dumps(donnees)

    def json(self):
        return self._d


class Session:
    def __init__(self, statut=200, donnees=None):
        self.appels, self.statut, self.donnees = [], statut, donnees or {"ok": True}

    def get(self, url, params=None, headers=None, timeout=None):
        self.appels.append({"url": url, "params": params, "headers": headers})
        return Reponse(self.statut, self.donnees)


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(api, "charger_env", lambda: None)
    for s in api.SOURCES.values():
        monkeypatch.delenv(s["variable"], raising=False)
    for v in api.VARIABLES_PROXY:
        monkeypatch.delenv(v, raising=False)


def test_cle_dans_l_entete_jamais_dans_le_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("FINNHUB_API_KEY", "cle-secrete-123")
    s = Session(donnees={"name": "Apple Inc."})
    r = api.get_json("finnhub", "https://finnhub.io/api/v1/stock/profile2", {"symbol": "AAPL"}, session=s)
    assert s.appels[0]["headers"]["X-Finnhub-Token"] == "cle-secrete-123"
    assert "token" not in (s.appels[0]["params"] or {})
    contenu = "".join(p.read_text() for p in (tmp_path / "cache").rglob("*.json"))
    assert "cle-secrete-123" not in contenu and r["donnees"]["name"] == "Apple Inc."


def test_deuxieme_appel_lu_dans_le_cache(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "x")
    s = Session()
    api.get_json("coingecko", "https://api.coingecko.com/api/v3/ping", session=s)
    r = api.get_json("coingecko", "https://api.coingecko.com/api/v3/ping", session=s)
    assert len(s.appels) == 1 and r["depuis_cache"]


def test_cache_perime_rappelle(monkeypatch):
    monkeypatch.setenv("COINGECKO_API_KEY", "x")
    s = Session()
    api.get_json("coingecko", "https://api.coingecko.com/api/v3/ping", session=s)
    api.get_json("coingecko", "https://api.coingecko.com/api/v3/ping", max_age_heures=0, session=s)
    assert len(s.appels) == 2


def test_mode_proxy_envoie_un_jeton_factice(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    assert api.valeur_entete("finnhub") == (api.JETON_PROXY, "proxy")


def test_user_agent_sec_jamais_fourni_par_le_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    with pytest.raises(api.ErreurApi, match="SEC_USER_AGENT"):
        api.valeur_entete("sec")


def test_erreur_http_sans_cle(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "cle-secrete-123")
    s = Session(statut=401, donnees={"error": "cle-secrete-123 invalide"})
    with pytest.raises(api.ErreurApi) as e:
        api.get_json("finnhub", "https://finnhub.io/api/v1/news", session=s)
    assert "cle-secrete-123" not in str(e.value) and "401" in str(e.value)
