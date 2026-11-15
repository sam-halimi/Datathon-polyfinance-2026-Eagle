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


def _justif(s, critere="tolerance", autre="AGG"):
    return {"critere_profil": critere, "pourquoi": f"Volatilité {{vol_{s.lower().replace('.', '_')}}}, adaptée au profil.",
            "plutot_que": autre if s != autre else "TLT", "raison_plutot_que": f"Pire baisse {{pb_{s.lower().replace('.', '_')}}}."}


REPONSES_LIGNES: dict = {s: _justif(s) for s, _, _ in LIGNES}
EXPLICATION = dict(
    sujet="Pourquoi pas une grosse part sur Tesla", niveau1="TSLA a perdu jusqu'à {pb_tsla}.",
    niveau2=["Le plafond par titre du profil est {lim_max_titre_individuel}."], chiffre_central="pb_tsla",
    faits=["TSLA : {vol_tsla} de volatilité."], hypotheses=["Le passé décrit le risque."], limites=["Rien sur l'avenir."],
    messages={k: "Voici." for k in ("analyse", "repartition", "risque", "verifications", "pourquoi", "limites", "tout")})


class FauxAgent:
    repondre = staticmethod(reponse)

    def __init__(self, nom, consigne, outils=None):
        self.nom, self.consigne = nom, consigne

    def __call__(self, prompt, structured_output_model=None):
        class R:
            pass
        r = R()
        r.structured_output = self.repondre(structured_output_model, prompt)
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


def test_lignes_detaillees_et_sourcees(sortie):
    for p in sortie["portefeuilles"]:
        for l in p["lignes"]:
            assert l["secteur"] and l["pays"] and l["devise"] in ("CAD", "USD")
            assert set(l["chiffres"]) == {"volatilite", "pire_baisse", "part_du_risque"}
            assert all(i in sortie["chiffres"] for i in l["chiffres"].values())
            assert l["pourquoi"] and l["critere_profil"] and l["plutot_que"]["symbole"]
            fichiers = {s["fichier"] for s in l["sources"]}
            assert {"data/assets_universe.csv", "data/prices_daily.csv"} <= fichiers
            if l["devise"] == "USD":
                assert "data/fx_usdcad_daily.csv" in fichiers
            if l["classe_code"] == "equity":
                assert any(s["fichier"] == "data/esg_actions.csv" and s["url"] for s in l["sources"])
    pays = {l["symbole"]: l["pays"] for l in sortie["portefeuilles"][0]["lignes"]}
    assert pays["XIU.TO"] == "Canada" and pays["JNJ"] == "États-Unis"


def test_ligne_mal_justifiee_rejetee_puis_corrigee(monkeypatch):
    """Une ligne sans repère ni critère du profil fait rejeter le portefeuille ; le constructeur corrige."""
    appels = []
    mauvaise = {"critere_profil": "centres_interet", "pourquoi": "Parce que c'est bien.",
                "plutot_que": "JNJ", "raison_plutot_que": "Moins cher."}

    def reponse_avec_retour(modele, prompt):
        if modele.__name__ == "Propositions":
            appels.append(prompt)
            if len(appels) == 1:
                lignes = [{"symbole": s, "poids": w, "role": r, **(mauvaise if s == "GLD" else REPONSES_LIGNES[s])}
                          for s, w, r in LIGNES]
                return modele(portefeuilles=[{"id": "A", "nom": "Prudent", "intention": "Préserver.", "lignes": lignes}])
        return reponse(modele, prompt)

    monkeypatch.setattr(FauxAgent, "repondre", staticmethod(reponse_avec_retour))
    monkeypatch.setattr(pipeline, "creer_agent", FauxAgent)
    s = pipeline.Session(Profil(**ROBERT["profil"]), ROBERT["demande"], "Robert").executer()
    premier = [h for h in s["gouvernance"]["historique"] if h["essai"] == 1]
    assert premier and not premier[0]["accepte"] and "justification_lignes" in premier[0]["rejets"]
    assert "GLD" in appels[1] and "critère « centres_interet » absent de ce profil" in appels[1]
    assert s["gouvernance"]["essai"] == 2 and all(h["accepte"] for h in s["gouvernance"]["historique"] if h["essai"] == 2)


def test_limites_et_hypotheses_propres_au_portefeuille(sortie):
    lim = sortie["limites"]
    spec, hyp = lim["limites_specifiques"], lim["hypotheses_specifiques"]
    assert [x["importance"] for x in spec] == list(range(1, len(spec) + 1))
    noms = {l["symbole"] for l in sortie["portefeuilles"][0]["lignes"]}
    for x in spec:
        assert REPERE.findall(x["texte"]) and all(i in sortie["chiffres"] for i in REPERE.findall(x["texte"])), x
        if x["type"] != "theme_non_couvert":
            assert x["lignes"] and any(s in x["texte"] for s in x["lignes"]) and set(x["lignes"]) & noms, x
    types = {x["type"] for x in spec}
    assert {"source_de_risque", "duree_pire_baisse", "taux", "dollar_americain", "donnee_manquante"} <= types
    # Robert : tolérance faible, horizon court -> la durée de la pire baisse passe avant le dollar américain.
    rang = {x["type"]: x["importance"] for x in spec}
    assert rang["duree_pire_baisse"] < rang["dollar_americain"]
    assert {h["type"] for h in hyp} == {"fenetre", "correlations", "conversion_cad", "plafonds"}
    for h in hyp:
        assert REPERE.findall(h["si_elle_tombe"]) or h["type"] == "plafonds", h
    assert lim["methode"] and lim["limites"][: len(spec)] == [x["texte"] for x in spec]
