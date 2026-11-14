import numpy as np
import pandas as pd
import pytest

from tools.calendriers import aligner_calendriers, convertir_cad, taux_usdcad
from tools.donnees import charger_prix, taux_change


# --- convertir_cad -----------------------------------------------------------

def test_cad_inchange():
    px = charger_prix(["RY.TO", "XIU.TO"])
    pd.testing.assert_frame_equal(convertir_cad(px), px, check_like=True)


def test_usd_multiplie_par_le_taux_du_jour():
    px = charger_prix("AAPL")
    cad = convertir_cad(px)
    fx = taux_change()
    jour = pd.Timestamp("2021-11-12")
    assert cad.loc[jour, "AAPL"] == pytest.approx(px.loc[jour, "AAPL"] * fx.loc[jour, "usdcad"])
    assert cad.loc[jour, "AAPL"] == pytest.approx(146.398193 * 1.2565)


def test_jour_ferie_canadien_reporte_le_dernier_taux():
    # 1er juillet 2022 : fête du Canada, Wall Street ouverte, pas de taux publié.
    fx = taux_change()
    ferie = pd.Timestamp("2022-07-01")
    assert ferie not in fx.index
    veille = fx.index[fx.index < ferie].max()
    px = charger_prix("SPY")
    assert ferie in px.index
    cad = convertir_cad(px)
    assert cad.loc[ferie, "SPY"] == pytest.approx(px.loc[ferie, "SPY"] * fx.loc[veille, "usdcad"])


def test_aucune_valeur_perdue_a_la_conversion():
    px = charger_prix(["SPY", "BTC-USD", "XIU.TO"])
    cad = convertir_cad(px)
    pd.testing.assert_frame_equal(cad.isna(), px.isna())
    assert cad.attrs["devise"] == "CAD"
    assert cad.attrs["conversion"]["jours_taux_reporte"] > 0


def test_crypto_week_end_utilise_le_taux_du_vendredi():
    fx = taux_change()
    samedi = pd.Timestamp("2022-01-08")
    vendredi = pd.Timestamp("2022-01-07")
    px = charger_prix("BTC-USD")
    cad = convertir_cad(px)
    assert cad.loc[samedi, "BTC-USD"] == pytest.approx(px.loc[samedi, "BTC-USD"] * fx.loc[vendredi, "usdcad"])


def test_jamais_de_taux_futur():
    # Un taux reporté est toujours un taux publié à la date ou avant.
    dates = pd.date_range("2021-11-12", "2026-11-12", freq="D")
    t = taux_usdcad(dates)
    fx = taux_change()["usdcad"]
    for d in [pd.Timestamp("2022-12-25"), pd.Timestamp("2023-07-01"), pd.Timestamp("2024-12-26")]:
        assert t.loc[d] == fx[fx.index <= d].iloc[-1]


def test_series_nommee():
    s = charger_prix("AAPL")["AAPL"]
    assert convertir_cad(s).iloc[0] == pytest.approx(146.398193 * 1.2565)


# --- aligner_calendriers -----------------------------------------------------

def test_communs_garde_les_dates_partagees():
    px = charger_prix(["SPY", "XIU.TO"])
    a = aligner_calendriers(px, "communs")
    assert a.notna().all().all()
    # 1 228 jours où la TSX et Wall Street sont ouvertes toutes les deux.
    assert len(a) == 1228
    assert a.attrs["alignement"]["dates_retirees"] == len(px) - 1228


def test_communs_crypto_et_actions_garde_le_calendrier_actions():
    px = charger_prix(["SPY", "BTC-USD"])
    a = aligner_calendriers(px)
    assert a.index.equals(px["SPY"].dropna().index)


def test_report_ne_remplit_que_vers_l_avant():
    px = charger_prix(["SPY", "XIU.TO"])
    a = aligner_calendriers(px, "report")
    assert a.notna().all().all()
    assert len(a) == len(px)  # les deux séries commencent le même jour
    # Fête du Canada 2022 : la TSX est fermée, XIU.TO reprend le prix de la veille.
    ferie = pd.Timestamp("2022-07-01")
    assert np.isnan(px.loc[ferie, "XIU.TO"])
    veille = px["XIU.TO"].loc[:ferie].dropna().index[-1]
    assert a.loc[ferie, "XIU.TO"] == px.loc[veille, "XIU.TO"]
    # Les prix observés ne sont pas modifiés.
    observe = px.notna()
    assert (a[observe] == px[observe]).sum().sum() == observe.sum().sum()


def test_report_commence_quand_tous_les_actifs_ont_un_prix():
    px = charger_prix(["SPY", "BTC-USD"], debut="2021-11-13")  # samedi : BTC seul
    a = aligner_calendriers(px, "report")
    assert a.index.min() == px["SPY"].first_valid_index()


def test_methode_inconnue():
    with pytest.raises(ValueError):
        aligner_calendriers(charger_prix("SPY"), "interpoler")
