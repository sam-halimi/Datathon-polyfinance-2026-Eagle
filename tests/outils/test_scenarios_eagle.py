import json

import pytest

from agents import serveur
from tools.scenarios import eventail_scenarios, fiche_actif, trouver_symbole

POIDS = {"SPY": 0.6, "AGG": 0.3, "BTC-USD": 0.1}


def test_eventail_part_du_capital_et_reste_ordonne():
    e = eventail_scenarios(POIDS, 8, capital=50_000)
    v = e["valeur"]
    assert v["annees"] == list(range(9))
    assert all(v[c][0] == 50_000 for c in ("p10", "p25", "p50", "p75", "p90"))
    for i in range(1, 9):
        assert v["p10"][i] <= v["p25"][i] <= v["p50"][i] <= v["p75"][i] <= v["p90"][i]
    assert v["p90"][8] - v["p10"][8] > v["p90"][1] - v["p10"][1]  # l'incertitude grandit avec le temps
    assert "prévision" in e["details"]["avertissement"]
    assert 0 <= e["details"]["part_des_scenarios_sous_le_capital"] <= 1
    json.dumps(e)  # la référence complète se sérialise


def test_eventail_se_reproduit():
    assert eventail_scenarios(POIDS, 5)["valeur"] == eventail_scenarios(POIDS, 5)["valeur"]
    assert eventail_scenarios(POIDS, 5, graine=1)["valeur"] != eventail_scenarios(POIDS, 5)["valeur"]


def test_eventail_refuse_un_horizon_absurde():
    with pytest.raises(ValueError):
        eventail_scenarios(POIDS, 0)
    with pytest.raises(ValueError):
        eventail_scenarios(POIDS, 80)


def test_trouver_symbole_par_nom_ou_symbole():
    assert trouver_symbole("tesla") == "TSLA"
    assert trouver_symbole("TSLA") == "TSLA"
    assert trouver_symbole("btc") == "BTC-USD"
    assert trouver_symbole("shop") == "SHOP.TO"
    assert trouver_symbole("zzz inconnu") is None


def test_fiche_tesla_pour_un_profil_prudent():
    f = fiche_actif("Tesla", "faible", 3)
    assert f["statut"] == "à plafonner" and f["symbole"] == "TSLA"
    texte = " ".join(f["raisons"])
    assert "59,6 %" in texte and "-73,0 %" in texte and "270 %" in texte and "5 % du capital" in texte
    assert "conseil" not in (f["titre"] + texte).lower()
    assert f["chiffres"]["pire_baisse"]["outil"] == "pire_baisse"  # chaque chiffre garde sa référence
    json.dumps(f)


def test_fiche_crypto_exclue_sous_cinq_ans_et_plafonnee_sinon():
    assert fiche_actif("BTC-USD", "élevé", 3)["statut"] == "hors profil"
    f = fiche_actif("bitcoin", "eleve", 15)
    assert f["statut"] == "à plafonner" and f["plafond_crypto"] == 0.10


def test_fiche_compatible_et_inconnue():
    assert fiche_actif("ZST.TO", "faible", 3)["statut"] == "compatible"
    assert fiche_actif("Nintendo", "modéré", 8)["statut"] == "inconnu"


def test_serveur_routes_sans_cle():
    assert serveur.repondre("GET", "/sante", {}, {})["ok"] is True
    f = serveur.repondre("GET", "/actif", {"symbole": ["tesla"], "tolerance": ["faible"], "horizon": ["3"]}, {})
    assert f["symbole"] == "TSLA"
    e = serveur.repondre("POST", "/scenarios", {}, {"poids": POIDS, "horizon_annees": 5, "capital": 1000})
    assert e["outil"] == "eventail_scenarios"
    d = serveur.repondre("GET", "/demonstration/robert", {}, {})
    assert d["scenarios"]["valeur"]["annees"][-1] == d["profil"]["horizon_annees"]


def test_serveur_refuse_proprement():
    for appel in (("GET", "/actif", {}, {}), ("GET", "/demonstration/inconnu", {}, {}),
                  ("POST", "/scenarios", {}, {"poids": POIDS}), ("POST", "/analyse", {}, {"profil": {}}),
                  ("POST", "/analyse", {}, {"profil": {}, "demande": "x"}), ("GET", "/nimporte", {}, {})):
        with pytest.raises(serveur.Refus):
            serveur.repondre(*appel)
