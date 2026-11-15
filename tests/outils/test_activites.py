"""tools/activites.py sur data/activites_sensibles.csv et data/fnb_composition.csv."""

import pandas as pd
import pytest

from tools.activites import ACTIVITES, exposition_activite, fiche_activites, table_activites
from tools.donnees import DATA


def test_une_ligne_par_action_et_une_source_par_valeur():
    t = table_activites()
    u = pd.concat([pd.read_csv(DATA / "assets_universe.csv"), pd.read_csv(DATA / "univers_etendu.csv")])
    assert set(u.loc[u["asset_class"] == "equity", "ticker"]) <= set(t.index)
    for a in ACTIVITES:
        assert set(t[a]) <= {"oui", "non", "inconnu"}
        connues = t[t[a] != "inconnu"]
        assert connues[f"{a}_source_url"].str.startswith("https://").all(), a
        assert (connues[f"{a}_source_date"].str.len() >= 7).all(), a


def test_couche_tard_tabac_et_alcool_avec_source():
    f = fiche_activites("ATD.TO")
    assert f["tabac"]["valeur"] == "oui" and f["alcool"]["valeur"] == "oui"
    assert "Nicotine" in f["tabac"]["extrait"]


def test_absent_de_la_table_jamais_non():
    assert fiche_activites("SPY")["statut"] == "information manquante"
    e = exposition_activite({"XBB.TO": 1.0}, "tabac")
    assert e["valeur"] == 0 and e["details"]["part_inconnue"] == 0  # une obligation n'est pas une société


def test_regard_a_travers_xiu():
    e = exposition_activite({"XIU.TO": 0.5, "ZST.TO": 0.5}, "tabac")
    assert e["details"]["directe"] == 0
    assert e["details"]["a_travers_les_fnb"] == pytest.approx(0.5 * 0.0146)  # ATD.TO dans XIU.TO
    assert "ATD.TO" in e["details"]["lignes"]["XIU.TO"]["titres_oui"]
    assert e["details"]["part_inconnue"] > 0  # le reste du TSX 60 n'est pas jugé


def test_detention_directe():
    e = exposition_activite({"ATD.TO": 0.1, "RY.TO": 0.9}, "alcool")
    assert e["valeur"] == pytest.approx(0.1) and e["details"]["part_inconnue"] == 0
