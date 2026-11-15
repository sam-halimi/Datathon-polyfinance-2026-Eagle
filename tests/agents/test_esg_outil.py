"""tools/esg.py sur les vrais fichiers de data/."""

import pytest

from tools.esg import exposition_fnb, exposition_titre, exposition_transparente, fiche_esg


def test_fiche_connue_et_inconnue():
    f = fiche_esg("XOM")
    assert f["activite_fossile"] == "oui" and f["source_fossile_url"].startswith("https://")
    assert fiche_esg("SPY")["statut"] == "information manquante"


def test_xiu_contient_des_titres_fossiles_de_l_univers():
    e = exposition_fnb("XIU.TO", "activite_fossile")
    assert set(e["details"]["titres_signales"]) == {"ENB.TO", "CNQ.TO", "CNR.TO", "ATD.TO", "FTS.TO"}
    assert e["valeur"] == pytest.approx(0.0359 + 0.0345 + 0.0239 + 0.0146 + 0.0103)
    assert 0 < e["details"]["part_inconnue"] < 1  # le reste du TSX 60 n'est pas jugé


def test_esgv_sans_fossile_mais_composition_partielle():
    e = exposition_fnb("ESGV", "activite_fossile")
    assert e["valeur"] == 0 and not e["details"]["composition_complete"]
    assert e["details"]["part_inconnue"] > 0.5


def test_transparence_directe_et_via_fnb():
    e = exposition_transparente({"XOM": 0.05, "SPY": 0.5, "XBB.TO": 0.45}, "activite_fossile")
    assert e["details"]["directe"] == pytest.approx(0.05)
    assert e["details"]["a_travers_les_fnb"] == pytest.approx(0.5 * 0.01065439)


def test_exposition_titre_a_travers_spy_et_qqq():
    e = exposition_titre({"SPY": 0.5, "QQQ": 0.2, "TSLA": 0.05, "XBB.TO": 0.25}, "TSLA")
    assert e["valeur"] == pytest.approx(0.05 + 0.5 * 0.01709578 + 0.2 * 0.03402266)
