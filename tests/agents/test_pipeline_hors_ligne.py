"""Le pipeline complet sans Bedrock : chaque agent est remplacé par une réponse fixe.

Vérifie l'assemblage de la sortie (format v2) ; les tests sur Bedrock lisent agents/sorties/.
"""

import json
from pathlib import Path

import pytest

from agents import pipeline
from agents.journal import REPERE
from agents.profil import Profil

ROBERT = json.loads((Path(__file__).parents[1] / "scenarios" / "robert.json").read_text(encoding="utf-8"))
LIGNES = [("ZST.TO", 0.40, "amortisseur"), ("XBB.TO", 0.20, "amortisseur"), ("GLD", 0.10, "diversification"),
          ("XIU.TO", 0.20, "coeur"), ("FTS.TO", 0.05, "diversification"), ("JNJ", 0.05, "diversification")]


def reponse(modele, prompt):
    nom = modele.__name__
    if nom == "DemandeAnalysee":
        return modele(symboles=[{"symbole": "TSLA", "poids": 0.4}], resume="Une grosse part sur Tesla.")
    if nom == "Constats":
        return modele(constats=["La pire baisse de TSLA est {pb_tsla}."])
    if nom == "Propositions":
        return modele(portefeuilles=[
            {"id": i, "nom": f"Prudent {i}", "intention": "Préserver le capital.",
             "lignes": [{"symbole": s, "poids": w, "role": r, **REPONSES_LIGNES.get(s, {})} for s, w, r in LIGNES]}
            for i in ("A", "B")])
    if nom == "Explication":
        return modele(**EXPLICATION)
    raise AssertionError(nom)


REPONSES_LIGNES: dict = {}
EXPLICATION = dict(
    sujet="Pourquoi pas une grosse part sur Tesla", niveau1="TSLA a perdu jusqu'à {pb_tsla}.",
    niveau2=["Le plafond par titre du profil est {lim_max_titre_individuel}."], chiffre_central="pb_tsla",
    faits=["TSLA : {vol_tsla} de volatilité."], hypotheses=["Le passé décrit le risque."], limites=["Rien sur l'avenir."],
    messages={k: "Voici." for k in ("analyse", "repartition", "risque", "verifications", "pourquoi", "limites", "tout")})


class FauxAgent:
    def __init__(self, nom, consigne, outils=None):
        self.nom, self.consigne = nom, consigne

    def __call__(self, prompt, structured_output_model=None):
        class R:
            pass
        r = R()
        r.structured_output = reponse(structured_output_model, prompt)
        return r


@pytest.fixture
def sortie(monkeypatch):
    monkeypatch.setattr(pipeline, "creer_agent", FauxAgent)
    return pipeline.Session(Profil(**ROBERT["profil"]), ROBERT["demande"], "Robert").executer()


def test_format_v2_sans_bedrock(sortie):
    assert sortie["meta"]["version_format"] == 2
    json.dumps(sortie, ensure_ascii=False)
    criteres = {e["critere"] for e in sortie["adequation"]}
    assert criteres == {"horizon", "objectif", "tolerance", "preferences", "exclusions", "centres_interet", "capital"}
    for p in sortie["portefeuilles"]:
        assert p["adequation"]
    for e in sortie["adequation"]:
        for i in REPERE.findall(e["reponse"]):
            assert i in sortie["chiffres"], i
