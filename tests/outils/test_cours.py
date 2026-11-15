"""tools/cours.py : univers étendu sourcé, format de prices_daily.csv, réponse yfinance simulée."""

import pandas as pd
import pytest

from tools import cours

DATA = cours.DATA


def test_univers_etendu_source_et_sans_doublon():
    u = cours.univers_etendu()
    assert (u["source_url"].str.startswith("https://")).all()
    assert not set(u["ticker"]) & set(pd.read_csv(DATA / "assets_universe.csv")["ticker"])
    assert set(u["asset_class"]) <= {"equity", "etf_equity"}


def test_themes_relient_des_symboles_sources():
    t = pd.read_csv(DATA / "themes.csv", dtype=str, keep_default_na=False)
    connus = set(cours.univers_etendu()["ticker"]) | set(pd.read_csv(DATA / "assets_universe.csv")["ticker"])
    assert set(t.loc[t["role"] != "non_couvert", "symbole"]) <= connus
    assert (t.loc[t["role"] == "non_couvert", "raison"].str.len() > 40).all()
    assert t["source_url"].str.startswith("https://").all()
    assert {"jeu vidéo", "énergie propre"} <= set(t["theme"])


def test_prix_etendus_au_format_de_prices_daily():
    p = pd.read_csv(cours.SORTIE, nrows=5)
    ref = pd.read_csv(DATA / "prices_daily.csv", nrows=1)
    assert list(p.columns) == list(ref.columns) + ["telecharge_le"]


def test_prices_daily_intact():
    assert len(pd.read_csv(DATA / "prices_daily.csv")) == 40049


class FauxBuildDataset:
    START, END = "2026-01-02", "2026-01-06"

    def __init__(self):
        self.appels = 0

    def build_prices(self, univ):
        self.appels += 1
        lignes = [{"date": d, "ticker": t, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "adj_close": 1.0,
                   "volume": 10, "currency": c} for t, c in zip(univ["ticker"], univ["currency"])
                  for d in ("2026-01-02", "2026-01-05", "2026-01-06")]
        return pd.DataFrame(lignes), pd.DataFrame(columns=["ex_date", "ticker", "action", "value", "unit"])

    def check(self, universe, prices, actions, fx, macro):
        assert set(prices["ticker"]) == set(universe["ticker"])
        return []


def test_telechargement_simule_ecrit_puis_relit_le_cache(tmp_path, monkeypatch):
    for nom in ("univers_etendu.csv", "assets_universe.csv", "fx_usdcad_daily.csv", "macro_rates.csv"):
        (tmp_path / nom).write_bytes((DATA / nom).read_bytes())
    monkeypatch.setattr(cours, "DATA", tmp_path)
    monkeypatch.setattr(cours, "SORTIE", tmp_path / "base" / "prix_etendus.csv")
    monkeypatch.setattr(cours, "CACHE", tmp_path / "cache")
    faux = FauxBuildDataset()
    r = cours.telecharger(bd=faux)
    assert r["symboles"] == len(cours.univers_etendu()) and faux.appels == 1
    cours.telecharger(bd=faux)
    assert faux.appels == 1  # deuxième passage : lu dans le cache
    p = pd.read_csv(tmp_path / "base" / "prix_etendus.csv")
    assert p["telecharge_le"].notna().all()


def test_symbole_sans_source_refuse(tmp_path, monkeypatch):
    u = pd.read_csv(DATA / "univers_etendu.csv", dtype=str, keep_default_na=False)
    u.loc[0, "source_url"] = ""
    u.to_csv(tmp_path / "univers_etendu.csv", index=False)
    (tmp_path / "assets_universe.csv").write_bytes((DATA / "assets_universe.csv").read_bytes())
    monkeypatch.setattr(cours, "DATA", tmp_path)
    with pytest.raises(ValueError, match="source"):
        cours.univers_etendu()


def test_couverture_cours_avec_reference():
    r = cours.couverture_cours("NXT")
    assert r["outil"] == "couverture_cours" and r["periode"]["debut"] == "2023-02-09"
