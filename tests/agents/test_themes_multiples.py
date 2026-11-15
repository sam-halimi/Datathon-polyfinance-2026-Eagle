"""Plusieurs centres d'intérêt couverts : un thème chacun, plafond global partagé."""

import pytest

from agents.gouvernance import plafonds_par_theme
from agents.pipeline import construire_themes
from agents.profil import Profil
from tools.donnees import univers

TABLE = univers(etendu=True)


def _profil(interets):
    return Profil(horizon_annees=12, objectif="équilibre", tolerance_risque="modéré", connaissance_niveau=3,
                  centres_interet=interets, capital_fictif=100000)


@pytest.mark.parametrize("interets", [["énergie propre", "santé"], ["santé", "jeu vidéo"]])
def test_deux_themes_couverts_deux_themes(interets):
    themes, non_couverts = construire_themes(_profil(interets), 0.10, TABLE)
    assert [t["nom"] for t in themes] == interets and not non_couverts
    assert sum(t["plafond"] for t in themes) == pytest.approx(0.10)
    assert not set(themes[0]["symboles"]) & set(themes[1]["symboles"])


def test_plafond_par_theme_refuse_un_theme_trop_gros():
    themes, _ = construire_themes(_profil(["énergie propre", "jeu vidéo"]), 0.10, TABLE)
    ptf = {"poids": {"ICLN": 0.08, "ESPO": 0.02, "XBB.TO": 0.9}, "roles": {"ICLN": "theme", "ESPO": "theme",
                                                                           "XBB.TO": "amortisseur"}}
    c = {x["actifs"][0] if x["actifs"] else None: x["statut"] for x in plafonds_par_theme(ptf, themes)}
    assert c["ICLN"] == "non conforme" and c["ESPO"] == "conforme"


def test_ligne_de_theme_hors_des_themes_refusee():
    themes, _ = construire_themes(_profil(["jeu vidéo"]), 0.10, TABLE)
    ptf = {"poids": {"TSLA": 0.05, "XBB.TO": 0.95}, "roles": {"TSLA": "theme", "XBB.TO": "amortisseur"}}
    assert any(x["statut"] == "non conforme" and x["actifs"] == ["TSLA"] for x in plafonds_par_theme(ptf, themes))
