"""Cohérence des scénarios d'acceptation (étape 1). Le passage de bout en bout viendra à l'étape 2."""

import csv
import json
from pathlib import Path

import pytest

from agents.profil import Profil, contraintes
from tools import mesures

DOSSIER = Path(__file__).parent
RACINE = DOSSIER.parent.parent
SCENARIOS = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(DOSSIER.glob("*.json"))}
TYPES = {"plafond_poids", "diversification", "presence_min", "controle_gouvernance", "chiffres_cites",
         "chiffre_cite_si_retenu", "texte_absent", "texte_present", "niveau_explication_par_defaut",
         "exclu_ou_signale", "esg_source_ou_inconnu", "transparence_fnb"}
OUTILS_DISPONIBLES = {"volatilite": mesures.volatilite, "pire_baisse": mesures.pire_baisse,
                      "rendement_annualise": mesures.rendement_annualise}
# Outils arrivés avec la branche outils : ajoutés dès qu'ils existent.
for _module, _nom in (("tools.mesures", "gain_de_rattrapage"), ("tools.portefeuille", "correlations")):
    try:
        OUTILS_DISPONIBLES[_nom] = getattr(__import__(_module, fromlist=[_nom]), _nom)
    except (ImportError, AttributeError):
        pass

with open(RACINE / "data/assets_universe.csv", encoding="utf-8") as f:
    UNIVERS = {ligne["ticker"]: ligne for ligne in csv.DictReader(f)}


def test_les_trois_personas_sont_la():
    assert set(SCENARIOS) == {"amira", "mateo", "robert"}


@pytest.mark.parametrize("nom", SCENARIOS)
def test_scenario_complet_et_profil_valide(nom):
    s = SCENARIOS[nom]
    assert s["id"] == nom and s["demande"] and s["piege"] and s["attendus"]
    Profil(**s["profil"])
    ids = [a["id"] for a in s["attendus"]]
    assert len(ids) == len(set(ids))
    for a in s["attendus"]:
        assert a["description"] and a["controle"]["type"] in TYPES, a["id"]


@pytest.mark.parametrize("nom", SCENARIOS)
def test_limites_et_symboles_references_existent(nom):
    s = SCENARIOS[nom]
    limites = contraintes(Profil(**s["profil"]))["limites"]
    for a in s["attendus"]:
        c = a["controle"]
        for cle in ("max", "min_lignes", "max_part_risquee"):
            if isinstance(c.get(cle), str):
                assert c[cle] in limites, (a["id"], c[cle])
        for symbole in c.get("symboles", []):
            assert symbole in UNIVERS, (a["id"], symbole)
        for appel in c.get("appels", []):
            for symbole in appel["parametres"].get("symboles", []) + [appel["parametres"].get("symbole")]:
                assert symbole is None or symbole in UNIVERS, (a["id"], symbole)
        if "secteur" in c:
            assert any(l["sector"] == c["secteur"] for l in UNIVERS.values())


@pytest.mark.parametrize("nom", SCENARIOS)
def test_vocabulaire(nom):
    texte = json.dumps(SCENARIOS[nom], ensure_ascii=False).lower()
    assert "conseil" not in texte


APPELS = [(nom, a["id"], appel) for nom, s in SCENARIOS.items() for a in s["attendus"]
          for appel in a["controle"].get("appels", []) if "valeur_attendue" in appel]


@pytest.mark.parametrize("nom,ident,appel", APPELS, ids=[f"{n}-{i}-{a['outil']}" for n, i, a in APPELS])
def test_chiffres_attendus_retrouves_par_tools(nom, ident, appel):
    """Les chiffres attendus dans les scénarios sont ceux que calcule tools/, pas des chiffres inventés."""
    outil = OUTILS_DISPONIBLES.get(appel["outil"])
    if outil is None:
        pytest.skip(f"{appel['outil']} n'est pas encore dans tools/ (branche outils)")
    parametres = dict(appel["parametres"])
    perte = parametres.get("perte")
    if isinstance(perte, str) and perte.startswith("pire_baisse(") and perte.endswith(")"):
        # « pire_baisse(TSLA) » : le scénario chaîne deux outils, comme le fera l'agent.
        parametres["perte"] = mesures.pire_baisse(perte[len("pire_baisse("):-1])
    valeur = outil(**parametres)["valeur"]
    if isinstance(valeur, dict):  # correlations renvoie une matrice : on lit la paire demandée
        premier, second = parametres["symboles"]
        valeur = valeur[premier][second]
    assert valeur == pytest.approx(appel["valeur_attendue"], abs=appel["tolerance"])


def test_robert_les_limites_contredisent_la_demande():
    c = contraintes(Profil(**SCENARIOS["robert"]["profil"]))
    assert c["limites"]["max_titre_individuel"] == 0.05 < 0.40  # la demande : 40 % sur TSLA
    assert c["limites"]["max_crypto"] == 0 and c["limites"]["plafond_theme"] == 0
    assert c["niveau_explication_par_defaut"] == 3  # énoncé : expérience avancée


def test_amira_le_risque_est_permis_mais_plafonne():
    c = contraintes(Profil(**SCENARIOS["amira"]["profil"]))["limites"]
    assert 0 < c["max_crypto"] <= 0.10 and c["plafond_theme"] == 0.10 and c["max_part_risquee"] < 1


def test_mateo_exclusion_et_pas_de_theme():
    c = contraintes(Profil(**SCENARIOS["mateo"]["profil"]))
    assert c["exclusions"] == ["énergies fossiles"] and c["limites"]["plafond_theme"] == 0
