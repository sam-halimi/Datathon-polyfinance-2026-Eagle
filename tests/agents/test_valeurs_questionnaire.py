"""Chaque valeur proposée par le questionnaire du site donne « respecté », « partiel » ou « non couvert »
avec une raison précise : jamais « aucune donnée de data/ ne permet de vérifier »."""

import pytest

from agents import gouvernance as gv
from agents.adequation import NON_COUVERT, evaluer
from agents.journal import Journal
from agents.profil import Profil

PREFERENCES = ["ESG", "dividendes", "Canada", "États-Unis", "FNB indiciels", "sociétés établies", "faible volatilité"]
EXCLUSIONS = ["énergies fossiles", "controverses", "crypto", "or", "finance", "tabac", "armement"]
INTERETS = ["technologie", "intelligence artificielle", "jeu vidéo", "santé", "énergie propre", "immobilier",
            "finance", "luxe", "sport", "aérospatiale", "alimentation", "crypto"]
POIDS = {"XIU.TO": 0.25, "SPY": 0.15, "XBB.TO": 0.3, "ZST.TO": 0.15, "RY.TO": 0.05, "JNJ": 0.05, "ESPO": 0.05}
GENERIQUE = ("aucune donnée de data/ ne permet de vérifier", "aucune donnée de data/ ne dit quels actifs")


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch):
    """Pas d'appel réseau dans les tests : l'ancienneté de cotation vient d'une fiche Finnhub simulée."""
    from tools import repartition

    fiches = {"RY": ("Royal Bank of Canada", "1905-06-17"), "JNJ": ("Johnson & Johnson", "1944-09-25")}

    def fiche(symbole, session=None):
        nom, ipo = fiches.get(symbole, ("", None))
        return {"valeur": bool(nom), "details": {"name": nom, "ipo": ipo, "exchange": ""}, "sources": ["simulé"]}

    monkeypatch.setattr("tools.nouvelles.fiche_societe", fiche)
    return repartition


def _entrees(**champs):
    p = Profil(horizon_annees=8, objectif="équilibre", tolerance_risque="modéré", connaissance_niveau=3,
               capital_fictif=100000, **champs)
    j = Journal()
    ids = gv.enregistrer_limites(j, gv.limites_du_profil(p))
    return evaluer(p, POIDS, j, "A", ids)


@pytest.mark.parametrize("champ,valeurs,critere", [
    ("preferences", PREFERENCES, "preferences"),
    ("exclusions", EXCLUSIONS, "exclusions"),
    ("centres_interet", INTERETS, "centres_interet"),
])
def test_aucune_valeur_du_questionnaire_sans_reponse_precise(champ, valeurs, critere):
    for v in valeurs:
        e = [x for x in _entrees(**{champ: [v]}) if x["critere"] == critere]
        assert len(e) == 1, (v, e)
        e = e[0]
        assert e["statut"] in ("respecté", "partiel", NON_COUVERT), (v, e)
        texte = f"{e.get('raison') or ''} {e['reponse']}"
        assert not any(g in texte for g in GENERIQUE), (v, texte)
        if e["statut"] == NON_COUVERT:
            assert e["raison"] and len(e["raison"]) > 40, (v, e["raison"])
        else:
            assert e["chiffres"], (v, e)


def test_valeurs_attendues_couvertes():
    """Seul le luxe reste non couvert, avec la liquidation de KLXY comme raison sourcée."""
    non_couverts = {x["element"] for x in _entrees(preferences=PREFERENCES, exclusions=EXCLUSIONS,
                                                    centres_interet=INTERETS) if x["statut"] == NON_COUVERT}
    assert non_couverts == {"luxe"}


def test_texte_libre_relie_ou_non_couvert_avec_raison():
    liens = {"Sociétés familiales": {"genre": "preference", "critere": None,
                                     "raison": "aucune donnée sur l'actionnariat familial"}}
    p = Profil(horizon_annees=8, objectif="équilibre", tolerance_risque="modéré", connaissance_niveau=3,
               capital_fictif=100000, preferences=["Sociétés familiales"])
    j = Journal()
    e = [x for x in evaluer(p, POIDS, j, "A", gv.enregistrer_limites(j, gv.limites_du_profil(p)), liens)
         if x["critere"] == "preferences"][0]
    assert e["statut"] == NON_COUVERT and "actionnariat familial" in e["raison"] and "dividendes" in e["raison"]
    liens = {"Sociétés familiales": {"genre": "preference", "critere": "sociétés établies", "raison": "relié"}}
    e = [x for x in evaluer(p, POIDS, j, "B", gv.enregistrer_limites(j, gv.limites_du_profil(p)), liens)
         if x["critere"] == "preferences"][0]
    assert e["statut"] != NON_COUVERT and "Relié par l'orchestrateur" in e["regle"]
