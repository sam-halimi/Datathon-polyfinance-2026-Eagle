"""Les sorties enregistrées du pipeline (agents/sorties/*.json) passent les contrôles de leur scénario.

Pour relancer le pipeline sur Bedrock pendant les tests : ALPHAFORGE_BEDROCK=1 python -m pytest tests/scenarios
"""

import json
import os
from pathlib import Path

import pytest

from agents.acceptation import MOTIF_CLE, evaluer_scenario, textes_affiches
from agents.journal import Journal

RACINE = Path(__file__).parents[2]
SCENARIOS = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted((RACINE / "tests/scenarios").glob("*.json"))}
SORTIES = RACINE / "agents/sorties"


def _sortie(nom):
    if os.environ.get("ALPHAFORGE_BEDROCK") == "1":
        from agents.pipeline import lancer
        s = SCENARIOS[nom]
        return lancer(s["profil"], s["demande"], s["persona"]["nom"])
    fichier = SORTIES / f"{nom}.json"
    if not fichier.is_file():
        pytest.skip(f"pas encore de sortie enregistrée : python -m agents.pipeline tests/scenarios/{nom}.json -o {fichier.relative_to(RACINE)}")
    return json.loads(fichier.read_text(encoding="utf-8"))


@pytest.mark.parametrize("nom", SCENARIOS)
def test_attendus_du_scenario(nom):
    resultats = evaluer_scenario(SCENARIOS[nom], _sortie(nom))
    echecs = [r for r in resultats if r["ok"] is False]
    assert not echecs, echecs


@pytest.mark.parametrize("nom", SCENARIOS)
def test_chaque_chiffre_affiche_a_sa_reference(nom):
    sortie = _sortie(nom)
    journal = Journal()
    journal.chiffres = sortie["chiffres"]
    for texte in textes_affiches(sortie):
        for cle in MOTIF_CLE.findall(texte):
            ref = sortie["chiffres"][cle]
            assert ref["outil"] and ref["sources"] and "nature" in ref["details"], cle
    e = sortie["explication"]
    for texte in [e["sujet"], e["niveau1"], *e["niveau2"], *e["niveau3"]["lignes"], *sortie["messages"].values()]:
        assert journal.problemes_texte(texte) == [], texte
    assert "conseil" not in json.dumps(sortie, ensure_ascii=False).lower()
