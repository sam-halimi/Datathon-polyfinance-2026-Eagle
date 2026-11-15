"""Chaque outil renvoie une référence d'appel complète et sérialisable en JSON.

C'est ce dictionnaire que les agents transmettent et que l'interface affiche.
"""

import json

import pytest

import tools

CLES = {"outil", "parametres", "periode", "valeur", "unite", "formule", "sources", "details"}
POIDS = {"SPY": 0.6, "AGG": 0.3, "BTC-USD": 0.1}
APPELS = {
    "volatilite": lambda: tools.volatilite("NVDA"),
    "pire_baisse": lambda: tools.pire_baisse("TSLA"),
    "rendement_annualise": lambda: tools.rendement_annualise("SPY"),
    "rendement_en_cad": lambda: tools.rendement_en_cad("SPY"),
    "gain_de_rattrapage": lambda: tools.gain_de_rattrapage(tools.pire_baisse("TSLA")),
    "correlations": lambda: tools.correlations(list(POIDS)),
    "stats_portefeuille": lambda: tools.stats_portefeuille(POIDS),
    "parts_du_risque": lambda: tools.parts_du_risque(POIDS),
    "sensibilite_taux": lambda: tools.sensibilite_taux("TLT"),
    "pente_courbe": lambda: tools.pente_courbe("Canada"),
    "verifier_contraintes": lambda: tools.verifier_contraintes(
        POIDS, {"tolerance_risque": "modéré", "horizon_annees": 10}),
}


@pytest.mark.parametrize("nom", sorted(APPELS))
def test_reference_complete_et_json(nom):
    res = APPELS[nom]()
    assert set(res) == CLES
    assert res["outil"] == nom
    assert res["formule"]
    json.loads(json.dumps(res, ensure_ascii=False))
