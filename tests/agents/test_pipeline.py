"""La boucle du pipeline sans Bedrock : les agents sont remplacés par des réponses fixes."""

import json

import pytest

from agents import etapes, pipeline
from agents.acceptation import evaluer_scenario
from agents.etapes import (CibleDemande, Explication, LigneProposee, Messages, Niveau3, NotesSpecialiste,
                           Orchestration, PortefeuillePropose, Propositions)
from pathlib import Path

ROBERT = json.loads((Path(__file__).parents[1] / "scenarios" / "robert.json").read_text(encoding="utf-8"))
PRUDENT = {"ZST.TO": 0.45, "XBB.TO": 0.15, "AGG": 0.10, "GLD": 0.10, "XIU.TO": 0.15, "FTS.TO": 0.05}
AVEC_TSLA = {"ZST.TO": 0.40, "XBB.TO": 0.15, "AGG": 0.10, "GLD": 0.10, "XIU.TO": 0.15, "FTS.TO": 0.05, "TSLA": 0.05}
TROP_TSLA = {"TSLA": 0.40, "ZST.TO": 0.30, "XBB.TO": 0.30}


def _ptf(ident, poids):
    return PortefeuillePropose(id=ident, nom=f"Option {ident}" if ident == "Z" else "Prudent", intention="Stabilité.",
                               lignes=[LigneProposee(symbole=s, poids=w, role="Ligne", au_titre_du_theme=False)
                                       for s, w in poids.items()])


def _explication(texte="TSLA a perdu jusqu'à {baisse_tsla}."):
    return Explication(sujet="Pourquoi pas TSLA en grand", niveau1=texte, niveau2=[texte],
                       niveau3=Niveau3(formule="gain = perte / (1 − perte)", lignes=["Gain : {rattrapage_tsla}."]),
                       faits=[texte], hypotheses=[], limites=[],
                       messages=Messages(analyse="a", repartition="r", risque="r", verifications="v",
                                         pourquoi="p", limites="l", tout="t"))


@pytest.fixture
def faux_agents(monkeypatch):
    appels = {"construire": [], "expliquer": []}
    reponses = {"construire": [], "expliquer": []}
    monkeypatch.setattr(etapes, "orchestrer", lambda *a, **k: Orchestration(
        resume_demande="TSLA en grand", theme=None, consignes_specialistes="Mesurer TSLA.",
        cibles=[CibleDemande(symboles=["TSLA", "INVENTE"], poids_demande=0.4, extrait="… sur Tesla")]))
    monkeypatch.setattr(etapes, "analyser_marche", lambda *a, **k: NotesSpecialiste(
        constats=[], a_privilegier=["ZST.TO"], a_limiter=["TSLA"]))

    def construire(*a, rejets=None, **k):
        appels["construire"].append(rejets)
        return reponses["construire"].pop(0)

    def expliquer(contexte, retour=None):
        appels["expliquer"].append(retour)
        return reponses["expliquer"].pop(0)

    monkeypatch.setattr(etapes, "construire", construire)
    monkeypatch.setattr(etapes, "expliquer", expliquer)
    return appels, reponses


def _lancer():
    return pipeline.lancer(ROBERT["profil"], ROBERT["demande"], "Robert", trace=lambda m: None)


def test_rejet_puis_retour_au_constructeur(faux_agents):
    appels, reponses = faux_agents
    reponses["construire"] = [Propositions(portefeuilles=[_ptf("A", PRUDENT), _ptf("B", TROP_TSLA)]),
                              Propositions(portefeuilles=[_ptf("A", PRUDENT), _ptf("B", AVEC_TSLA)])]
    reponses["expliquer"] = [_explication()]
    sortie = _lancer()
    assert appels["construire"][0] is None and "B" in appels["construire"][1] and "A" not in appels["construire"][1]
    g = sortie["gouvernance"]
    assert g["statut"] == "accepte" and g["essai"] == 2 and g["essais_max"] == 3
    assert [p["id"] for p in sortie["portefeuilles"]] == ["A", "B"]
    assert sortie["orchestration"]["cibles"][0]["symboles"] == ["TSLA"]  # symbole inventé écarté
    json.dumps(sortie)  # la sortie est du JSON
    resultats = {r["id"]: r["ok"] for r in evaluer_scenario(ROBERT, sortie)}
    assert resultats == {"R1": True, "R2": True, "R3": True, "R4": True, "R5": True, "R6": True, "R7": True}


def test_deux_retours_au_plus(faux_agents):
    appels, reponses = faux_agents
    reponses["construire"] = [Propositions(portefeuilles=[_ptf("A", TROP_TSLA)])] * 3
    reponses["expliquer"] = [_explication()]
    sortie = _lancer()
    assert len(appels["construire"]) == 3 and sortie["gouvernance"]["statut"] == "rejete"
    assert sortie["portefeuilles"] == [] and len(sortie["gouvernance"]["historique"]) == 3


def test_explication_avec_chiffre_en_clair_est_refusee_puis_retiree(faux_agents):
    appels, reponses = faux_agents
    reponses["construire"] = [Propositions(portefeuilles=[_ptf("A", PRUDENT)])]
    fautive = _explication("TSLA a perdu jusqu'à 73 %.")
    reponses["expliquer"] = [fautive, fautive, fautive]
    sortie = _lancer()
    assert len(appels["expliquer"]) == 3 and "chiffre écrit en clair" in appels["expliquer"][1][0]
    assert sortie["explication"]["niveau2"] == [] and any("retirées" in t for t in sortie["limites"]["limites"])


def test_un_texte_corrige_passe(faux_agents):
    appels, reponses = faux_agents
    reponses["construire"] = [Propositions(portefeuilles=[_ptf("A", PRUDENT)])]
    reponses["expliquer"] = [_explication("C'est huit fois trop."), _explication()]
    sortie = _lancer()
    assert len(appels["expliquer"]) == 2 and sortie["explication"]["niveau1"] == "TSLA a perdu jusqu'à {baisse_tsla}."
