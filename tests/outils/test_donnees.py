import pandas as pd
import pytest

from tools.donnees import (
    SymboleInconnu,
    charger_prix,
    devise,
    jours_par_an,
    taux_change,
    univers,
)


def test_univers_31_actifs():
    u = univers()
    assert len(u) == 31
    assert u.index.is_unique


def test_charger_prix_tout_l_univers():
    px = charger_prix()
    assert px.shape[1] == 31
    assert px.index.min() == pd.Timestamp("2021-11-12")
    assert px.index.max() == pd.Timestamp("2026-11-12")
    # Une valeur par ligne du CSV : 40 049 lignes de prix au total.
    assert int(px.notna().sum().sum()) == 40049


def test_charger_prix_un_symbole_valeur_connue():
    px = charger_prix("AAPL")
    assert list(px.columns) == ["AAPL"]
    assert len(px) == 1255
    assert px.loc["2021-11-12", "AAPL"] == pytest.approx(146.398193)


def test_charger_prix_colonne_close():
    px = charger_prix("AAPL", colonne="close")
    assert px.loc["2021-11-12", "AAPL"] == pytest.approx(149.990005)


def test_charger_prix_bornes_inclusives():
    px = charger_prix(["SPY", "XIU.TO"], debut="2022-01-03", fin="2022-01-31")
    assert px.index.min() == pd.Timestamp("2022-01-03")
    assert px.index.max() == pd.Timestamp("2022-01-31")
    assert list(px.columns) == ["SPY", "XIU.TO"]


def test_calendriers_non_alignes_laissent_des_trous():
    px = charger_prix(["SPY", "BTC-USD"])
    assert px["BTC-USD"].notna().sum() == 1827
    assert px["SPY"].notna().sum() == 1255
    # Les week-ends n'ont pas de prix SPY : aucun remplissage implicite.
    assert px["SPY"].isna().sum() == 1827 - 1255


def test_symbole_inconnu_refuse():
    with pytest.raises(SymboleInconnu):
        charger_prix(["AAPL", "ZZZZ"])


def test_colonne_invalide_refusee():
    with pytest.raises(ValueError):
        charger_prix("AAPL", colonne="prix")


def test_devise_et_jours_par_an():
    assert devise("RY.TO") == "CAD"
    assert devise("AAPL") == "USD"
    assert devise("BTC-USD") == "USD"
    assert jours_par_an("BTC-USD") == 365
    assert jours_par_an("SPY") == 252


def test_taux_change_sans_trou_de_valeur():
    fx = taux_change()
    assert fx.index.is_monotonic_increasing
    assert fx["usdcad"].notna().all()
    assert fx.index.min() == pd.Timestamp("2021-11-12")


def test_univers_etendu_reconnu_sans_changer_le_depart():
    """Les actifs ajoutés par API (univers_etendu.csv) sont reconnus ; sans argument, rien ne change."""
    from tools.donnees import classe_actif, devise, fichier_prix, sources_prix

    assert len(univers()) == 31 and charger_prix().shape[1] == 31
    complet = univers(etendu=True)
    assert len(complet) == 42 and set(complet["univers"]) == {"départ", "étendu"}
    assert classe_actif("ESPO") == "etf_equity" and devise("GME") == "USD"
    px = charger_prix(["GME", "SPY"])
    assert px["GME"].notna().sum() > 1000 and px["SPY"].notna().sum() == 1255
    assert charger_prix("NXT")["NXT"].first_valid_index() == pd.Timestamp("2023-02-09")
    assert fichier_prix("GME") == "base/prix_etendus.csv" and fichier_prix("SPY") == "prices_daily.csv"
    assert sources_prix(["SPY", "GME", "AAPL"]) == ["prices_daily.csv (adj_close)", "base/prix_etendus.csv (adj_close)"]
