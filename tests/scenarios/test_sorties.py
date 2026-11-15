"""Étape 2 des scénarios : chaque attendu appliqué à la sortie réelle du pipeline.

Les sorties sont produites sur Bedrock par `python -m agents.pipeline amira mateo robert` et
enregistrées dans agents/sorties/. Ce test les relit (aucun appel au modèle).
"""

import json

import pytest

from tests.scenarios.verifier_sortie import DOSSIER, SORTIES, verifier

CAS = []
for nom in ("amira", "mateo", "robert"):
    scenario = json.loads((DOSSIER / f"{nom}.json").read_text(encoding="utf-8"))
    for a in scenario["attendus"]:
        CAS.append((nom, a["id"]))


@pytest.mark.parametrize("nom,ident", CAS, ids=[f"{n}-{i}" for n, i in CAS])
def test_attendu(nom, ident):
    chemin = SORTIES / f"{nom}.json"
    if not chemin.exists():
        pytest.skip(f"pas encore de sortie pour {nom} : python -m agents.pipeline {nom}")
    scenario = json.loads((DOSSIER / f"{nom}.json").read_text(encoding="utf-8"))
    verdicts = {i: (ok, d) for i, ok, d in verifier(scenario, json.loads(chemin.read_text(encoding="utf-8")))}
    ok, detail = verdicts[ident]
    assert ok, detail


@pytest.mark.parametrize("nom", ["amira", "mateo", "robert"])
def test_aucun_chiffre_sans_reference(nom):
    """Tout repère cité dans la sortie existe dans la table des chiffres, avec sa référence d'appel."""
    chemin = SORTIES / f"{nom}.json"
    if not chemin.exists():
        pytest.skip("pas encore de sortie")
    from tests.scenarios.verifier_sortie import textes_affiches
    from agents.registre import REPERE
    sortie = json.loads(chemin.read_text(encoding="utf-8"))
    for t in textes_affiches(sortie):
        for m in REPERE.findall(t):
            assert m in sortie["chiffres"], m
            assert {"outil", "parametres", "periode", "formule", "sources"} <= set(sortie["chiffres"][m])
