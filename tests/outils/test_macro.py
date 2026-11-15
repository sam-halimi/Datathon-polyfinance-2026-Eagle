"""sensibilite_taux, pente_courbe et lecture des séries macro, sur data/base/series.csv."""

import pandas as pd
import pytest

from tools.donnees import SymboleInconnu
from tools.macro import SerieInconnue, pente_courbe, sensibilite_taux, serie_macro


# --- serie_macro ---------------------------------------------------------------

def test_serie_macro_dgs10():
    s = serie_macro("DGS10")
    assert len(s) == 1249  # instantané data/base : FRED jusqu'au 12 novembre 2026
    assert s.iloc[0] == 1.58
    assert s.index.is_monotonic_increasing


def test_connue_le_respecte_la_publication():
    # IPC canadien : publié 55 jours après le début du mois mesuré. Janvier 2024
    # est publié le 25 février, février 2024 le 27 mars.
    s = serie_macro("STATIC_TOTALCPICHANGE", connue_le="2024-03-26")
    assert s.index.max() == pd.Timestamp("2024-01-01")
    s = serie_macro("STATIC_TOTALCPICHANGE", connue_le="2024-03-27")
    assert s.index.max() == pd.Timestamp("2024-02-01")


def test_serie_inconnue():
    with pytest.raises(SerieInconnue):
        serie_macro("PAS_UNE_SERIE")


# --- sensibilite_taux ----------------------------------------------------------

def test_tlt_du_contexte():
    # docs/contexte.md : TLT −14,3 % par point de hausse du 10 ans américain.
    s = sensibilite_taux("TLT")
    assert round(s["valeur"] * 100, 1) == -14.3
    d = s["details"]
    assert d["jours"] == 1245
    # Le 10 ans est passé de 1,58 % à 5,10 % (instantané data/base, FRED jusqu'au 12 novembre 2026).
    assert (d["taux_debut"], d["taux_fin"]) == (1.58, 5.10)
    assert d["duration_implicite_annees"] == pytest.approx(-s["valeur"] * 100)
    # R² 0,83 : le contexte donne 0,82 parce que analyses/exemples_explications.py
    # apparie des rendements et des variations de taux calculés sur des calendriers
    # différents (jours fériés du marché obligataire). Ici, les deux variations
    # couvrent toujours les mêmes jours.
    assert round(d["r2"], 2) == 0.83


def test_agg_du_contexte():
    s = sensibilite_taux("AGG")
    assert round(s["valeur"] * 100, 1) == -5.9
    assert round(s["details"]["r2"], 2) == 0.92  # 0,91 dans le contexte, voir TLT


def test_action_peu_sensible_et_sans_duration():
    s = sensibilite_taux("SPY")
    assert s["details"]["r2"] < 0.05
    assert "duration_implicite_annees" not in s["details"]


def test_courbe_canadienne_et_reference():
    s = sensibilite_taux("XBB.TO", "BD.CDN.10YR.DQ.YLD", debut="2023-01-01")
    assert s["valeur"] < 0
    assert s["parametres"]["serie_taux"] == "BD.CDN.10YR.DQ.YLD"
    assert s["periode"]["debut"] >= "2023-01-01"
    assert any("BD.CDN.10YR.DQ.YLD" in src for src in s["sources"])


def test_sensibilite_refuse_ce_qui_n_est_pas_un_taux_quotidien():
    with pytest.raises(ValueError):
        sensibilite_taux("TLT", "CPIAUCSL")
    with pytest.raises(SerieInconnue):
        sensibilite_taux("TLT", "XYZ")
    with pytest.raises(SymboleInconnu):
        sensibilite_taux("ZZZZ")


# --- pente_courbe --------------------------------------------------------------

def test_pente_etats_unis_du_contexte():
    # Négative 541 jours sur 1 249, minimum −1,08 point le 3 juillet 2023.
    p = pente_courbe("États-Unis")
    d = p["details"]
    assert (d["jours_negatifs"], d["jours"]) == (541, 1249)
    assert round(d["minimum"], 2) == -1.08
    assert d["date_minimum"] == "2023-07-03"
    assert round(p["valeur"], 2) == 0.24
    assert p["valeur"] == pytest.approx(d["taux_10_ans"] - d["taux_2_ans"])


def test_pente_canada_du_contexte():
    # Négative 549 jours sur 1 245, minimum −1,32 point le 30 juin 2023.
    d = pente_courbe("Canada")["details"]
    assert (d["jours_negatifs"], d["jours"]) == (549, 1245)
    assert round(d["minimum"], 2) == -1.32
    assert d["date_minimum"] == "2023-06-30"
    assert d["plus_longue_inversion_jours"] <= d["jours_negatifs"]


def test_pente_alias_et_date_de_connaissance():
    assert pente_courbe("us")["parametres"]["pays"] == "États-Unis"
    p = pente_courbe("canada", connue_le="2023-07-01")
    # Le taux du 30 juin est publié le 1er juillet : c'est la dernière valeur connue.
    assert p["details"]["date_derniere"] == "2023-06-30"
    assert p["details"]["inversee_a_la_fin"] is True
    with pytest.raises(ValueError):
        pente_courbe("France")
