"""Adéquation : chaque critère du profil vérifié par le code, avec un chiffre de tools/."""

import pytest

from agents import gouvernance as gv
from agents.adequation import NON_COUVERT, evaluer, relier_interet
from agents.journal import REPERE, Journal
from agents.profil import Profil

POIDS = {"XIU.TO": 0.2, "ESGV": 0.2, "XBB.TO": 0.25, "ZST.TO": 0.15, "GLD": 0.1, "MSFT": 0.05, "RY.TO": 0.05}
BASE = dict(horizon_annees=10, objectif="équilibre", tolerance_risque="modéré", connaissance_niveau=3,
            preferences=["ESG"], exclusions=["énergies fossiles"], centres_interet=["l'intelligence artificielle"],
            capital_fictif=50000)


def _adequation(**changement):
    p = Profil(**{**BASE, **changement})
    j = Journal()
    ids = gv.enregistrer_limites(j, gv.limites_du_profil(p))
    return {(e["critere"], e["element"]): e for e in evaluer(p, POIDS, j, "A", ids)}, j


def _differences(a, b):
    return {k for k in a.keys() | b.keys()
            if k not in a or k not in b or any(a[k][x] != b[k][x] for x in ("attente", "reponse", "statut"))}


@pytest.mark.parametrize("changement,critere,statuts", [
    ({"horizon_annees": 1}, "horizon", ("respecté", "partiel")),  # pire baisse effacée en environ un an et demi
    ({"objectif": "préservation du capital"}, "objectif", ("respecté", "partiel")),  # part risquée de la moitié
    ({"objectif": "revenu"}, "objectif", ("respecté", "non couvert")),
    ({"capital_fictif": 200000}, "capital", None),
    ({"tolerance_risque": "faible"}, "tolerance", None),
])
def test_un_seul_critere_change_une_seule_entree(changement, critere, statuts):
    a, _ = _adequation()
    b, _ = _adequation(**changement)
    assert {k[0] for k in _differences(a, b)} == {critere}
    if statuts:
        assert (a[(critere, None)]["statut"], b[(critere, None)]["statut"]) == statuts


@pytest.mark.parametrize("champ,avant,apres", [
    ("preferences", ["ESG"], ["Canada"]),
    ("exclusions", ["énergies fossiles"], ["TSLA"]),
    ("centres_interet", ["l'intelligence artificielle"], ["les jeux vidéo"]),
])
def test_un_element_de_liste_change_son_entree(champ, avant, apres):
    a, _ = _adequation()
    b, _ = _adequation(**{champ: apres})
    assert {k[0] for k in _differences(a, b)} == {champ}


def test_chaque_entree_est_chiffree_ou_dit_pourquoi_non():
    a, j = _adequation(preferences=["ESG", "dividendes"], exclusions=["énergies fossiles", "tabac"],
                       centres_interet=["les jeux vidéo", "la techno"])
    for e in a.values():
        assert j.verifier_texte(e["reponse"]) == [], e
        if e["statut"] == NON_COUVERT:
            assert e["raison"], e
        else:
            assert e["chiffres"] and set(REPERE.findall(e["reponse"])) <= set(j.chiffres), e
            assert any(j.chiffres[i]["outil"] in ("stats_portefeuille", "parts_du_risque", "exposition_transparente",
                                                  "exposition_titre") or j.chiffres[i]["outil"].startswith("agents.")
                       for i in e["chiffres"])
    assert a[("centres_interet", "les jeux vidéo")]["statut"] == NON_COUVERT
    assert a[("preferences", "dividendes")]["statut"] == NON_COUVERT


def test_l_exclusion_voit_a_travers_les_fnb():
    a, j = _adequation(exclusions=["TSLA"])
    e = a[("exclusions", "TSLA")]
    assert e["statut"] == "partiel"  # ESGV détient TSLA (data/fnb_composition.csv)
    assert j.chiffres[e["chiffres"][0]]["details"]["a_travers_les_fnb"]


def test_centres_interet_en_texte_libre():
    assert relier_interet("j'adore l'IA et les puces")["secteur"] == "Information Technology"
    assert relier_interet("le bitcoin")["type"] == "crypto"
    lien = relier_interet("les jeux vidéo")
    assert lien["type"] == NON_COUVERT and "themes.csv" in lien["raison"] and not lien["symboles"]
