"""tools/dividendes.py sur les vrais CSV."""

import pandas as pd
import pytest

from tools import dividendes
from tools.dividendes import rendement_dividende, rendement_dividende_portefeuille
from tools.donnees import DATA


def test_ry_recalcule_a_la_main():
    a = pd.read_csv(DATA / "corporate_actions.csv", parse_dates=["ex_date"])
    p = pd.read_csv(DATA / "prices_daily.csv", parse_dates=["date"])
    p = p[p["ticker"] == "RY.TO"].sort_values("date")
    fin = p["date"].max()
    d = a[(a["ticker"] == "RY.TO") & (a["action"] == "dividend") & (a["ex_date"] > fin - pd.Timedelta(days=365))
          & (a["ex_date"] <= fin)]
    attendu = d["value"].sum() / p["close"].iloc[-1]
    r = rendement_dividende("RY.TO")
    assert r["valeur"] == pytest.approx(attendu)
    assert r["outil"] == "rendement_dividende" and r["periode"]["fin"] == "2026-11-12"
    assert r["periode"]["observations"] == 4 and "close" in r["sources"][1]


def test_sans_dividende_vaut_zero_et_le_dit():
    for s in ("TSLA", "BTC-USD", "GLD"):
        r = rendement_dividende(s)
        assert r["valeur"] == 0 and "aucun dividende" in r["details"]["statut"]


def test_univers_etendu_lu_dans_actions_etendues():
    r = rendement_dividende("VGK")
    assert r["valeur"] > 0 and "actions_etendues" in r["sources"][0]


def test_absent_du_fichier_information_manquante_jamais_zero(monkeypatch):
    monkeypatch.setattr(dividendes, "FICHIERS_ACTIONS",
                        {"data/corporate_actions.csv": DATA / "corporate_actions.csv"})
    r = rendement_dividende("VGK")
    assert r["valeur"] is None and r["details"]["statut"] == "information manquante"


def test_fenetre_respectee():
    r = rendement_dividende("ENB.TO", fin="2023-12-31")
    assert r["periode"]["fin"] <= "2023-12-31" and r["valeur"] > 0


def test_portefeuille_pondere():
    r = rendement_dividende_portefeuille({"RY.TO": 0.5, "TSLA": 0.5})
    assert r["valeur"] == pytest.approx(0.5 * rendement_dividende("RY.TO")["valeur"])
    assert r["details"]["part_inconnue"] == 0
