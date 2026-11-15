"""Acceptation du format v2 sur les sorties Bedrock enregistrées (agents/sorties/).

Une sortie encore au format v1 est ignorée avec un message : il faut la régénérer sur Bedrock.
"""

import json
import re
from pathlib import Path

import pytest

from agents import langage

SORTIES = Path(__file__).parents[2] / "agents" / "sorties"
NOMS = ["robert", "amira", "mateo", "libre_niveau1", "libre_niveau5", "libre_marc"]
REPERE = re.compile(r"\{([a-z0-9_]+)\}")
CRITERES = {"horizon", "objectif", "tolerance", "preferences", "exclusions", "centres_interet", "capital"}


def _sortie(nom):
    f = SORTIES / f"{nom}.json"
    if not f.exists():
        pytest.skip(f"{f.name} absent : python -m agents.pipeline {nom}")
    s = json.loads(f.read_text(encoding="utf-8"))
    if s.get("meta", {}).get("version_format") != 2:
        pytest.skip(f"{f.name} est au format v1 : à régénérer sur Bedrock")
    return s


@pytest.mark.parametrize("nom", NOMS)
def test_adequation(nom):
    s = _sortie(nom)
    assert {e["critere"] for e in s["adequation"]} == CRITERES
    for e in s["adequation"]:
        assert e["statut"] in ("respecté", "partiel", "non couvert")
        assert e["raison"] if e["statut"] == "non couvert" else True
        assert all(i in s["chiffres"] for i in REPERE.findall(e["reponse"]))


@pytest.mark.parametrize("nom", NOMS)
def test_lignes_justifiees_et_sourcees(nom):
    s = _sortie(nom)
    for p in s["portefeuilles"]:
        for l in p["lignes"]:
            assert l["pourquoi"] and REPERE.findall(l["pourquoi"]) and l["critere_profil"]
            assert l["plutot_que"]["symbole"] != l["symbole"] and l["plutot_que"]["raison"]
            assert l["secteur"] and l["pays"] and l["devise"] and l["sources"]
            assert all(i in s["chiffres"] for i in l["chiffres"].values())


@pytest.mark.parametrize("nom", NOMS)
def test_limites_propres_et_registre(nom):
    s = _sortie(nom)
    spec = s["limites"]["limites_specifiques"]
    assert spec and [x["importance"] for x in spec] == list(range(1, len(spec) + 1))
    for x in spec + s["limites"]["hypotheses_specifiques"]:
        assert REPERE.findall(x["texte"] + x.get("si_elle_tombe", "")), x
    niveau = s["profil"]["connaissance_niveau"]
    assert s["explication"]["registre"]["niveau"] == niveau
    assert bool(s["explication"]["lexique"]) == (niveau <= 2)


def test_robert_avance_registre_professionnel():
    s = _sortie("robert")
    assert s["profil"]["connaissance_niveau"] == 4 and s["explication"]["registre"]["nom"] == "professionnel"
    e = s["explication"]
    texte = langage.normaliser(" ".join([e["sujet"], e["niveau1"], *e["niveau2"], *s["limites"]["faits"]]))
    for terme in langage.TERMES_PROFESSIONNELS:
        assert terme in texte, terme
