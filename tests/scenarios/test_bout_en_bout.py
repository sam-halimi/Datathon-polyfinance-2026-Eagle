"""Étape 2 des tests d'acceptation : chaque attendu appliqué à la vraie sortie du pipeline.

Les sorties sont produites sur Bedrock par `python -m agents.pipeline robert amira mateo` et
enregistrées dans `agents/sorties/`. Ces tests ne rappellent pas le modèle : ils vérifient ce
qu'il a produit. Une sortie absente est signalée (skip), pas inventée.
"""

import json
import re
from pathlib import Path

import pytest

from agents.profil import Profil, contraintes
from tools.donnees import univers

DOSSIER = Path(__file__).parent
SORTIES = DOSSIER.parent.parent / "agents" / "sorties"
SCENARIOS = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(DOSSIER.glob("*.json"))}
REPERE = re.compile(r"\{([a-z0-9_]+)\}")
TABLE = univers()


def _sortie(nom):
    f = SORTIES / f"{nom}.json"
    if not f.exists():
        pytest.skip(f"{f.name} absent : lancer python -m agents.pipeline {nom}")
    return json.loads(f.read_text(encoding="utf-8"))


def _textes(s, zone=None):
    """Tout le texte affiché, ou celui d'une carte."""
    if zone == "limites":
        return [t for v in s["limites"].values() for t in v]
    e = s["explication"]
    textes = [x["fait"] for x in s["etapes"]]
    textes += [t for p in s["portefeuilles"] for t in (p["nom"], p["intention"])]
    textes += [t for c in s["gouvernance"]["controles"] for t in (c["titre"], c["detail"])]
    textes += [e["sujet"], e["niveau1"], *e["niveau2"], *e["niveau3"]["lignes"]]
    textes += [t for v in s["limites"].values() for t in v] + list(s["messages"].values())
    textes += [t for v in s.get("specialistes", {}).values() if isinstance(v, list) for t in v if isinstance(t, str)]
    return textes


def _cites(s):
    """Identifiants des chiffres affichés : repères des textes et champs des portefeuilles."""
    ids = {i for t in _textes(s) for i in REPERE.findall(t)}
    for p in s["portefeuilles"]:
        ids |= {p["volatilite"], p["pire_baisse"], *p["parts_du_risque"].values(), *p["pires_baisses"].values()}
    return ids


def _poids(p):
    return {l["symbole"]: l["poids"] for l in p["lignes"]}


def _groupe(p, c):
    """Poids d'un groupe : symboles, classe ou rôle."""
    if "symboles" in c:
        return sum(w for s, w in _poids(p).items() if s in c["symboles"])
    if "classe" in c:
        return sum(l["poids"] for l in p["lignes"] if l["classe_code"] == c["classe"])
    if "role" in c:
        return sum(l["poids"] for l in p["lignes"] if l["role_code"] == c["role"])
    raise ValueError(c)


def _correspond(ref, attendu, s):
    if ref["outil"] != attendu["outil"]:
        return False
    for k, v in attendu["parametres"].items():
        r = ref["parametres"].get(k)
        if v == "portefeuille retenu":
            retenu = next(p for p in s["portefeuilles"] if p["id"] == s["gouvernance"]["portefeuille_retenu"])
            if r != _poids(retenu):
                return False
        elif isinstance(v, list):
            if sorted(r or []) != sorted(v):
                return False
        elif r != v:
            return False
    return "valeur_attendue" not in attendu or ref["valeur"] == pytest.approx(
        attendu["valeur_attendue"], abs=attendu["tolerance"])


def verifier(s, attendu, limites):
    c = attendu["controle"]
    t = c["type"]
    if t == "plafond_poids":
        for p in s["portefeuilles"]:
            assert _groupe(p, c) <= limites[c["max"]] + 1e-6, (p["id"], _groupe(p, c))
    elif t == "diversification":
        for p in s["portefeuilles"]:
            assert len(p["lignes"]) >= limites[c["min_lignes"]], p["id"]
            risquee = sum(l["poids"] for l in p["lignes"] if l["classe_code"] in ("equity", "etf_equity", "crypto"))
            assert risquee <= limites[c["max_part_risquee"]] + 1e-6, (p["id"], risquee)
            assert risquee < 1, p["id"]
    elif t == "presence_min":
        assert any(all(_groupe(p, g) > 0 for g in c["dans_au_moins_un_portefeuille"]) for p in s["portefeuilles"])
    elif t == "controle_gouvernance":
        statut = {"signale": "à signaler", "conforme": "conforme", "non conforme": "non conforme"}[c["statut"]]
        trouves = [x for x in s["gouvernance"]["controles"]
                   if x["controle"] == c["nom"] and x["statut_outil"] == statut
                   and set(c.get("symboles", [])) <= set(x.get("symboles", []))]
        assert trouves, f"contrôle {c['nom']} « {statut} » absent"
    elif t == "chiffres_cites":
        cites = _cites(s)
        for appel in c["appels"]:
            assert any(_correspond(s["chiffres"][i], appel, s) for i in cites), appel
    elif t == "chiffre_cite_si_retenu":
        cites = _cites(s)
        for p in s["portefeuilles"]:
            for l in p["lignes"]:
                if l["classe_code"] == c["classe"]:
                    assert any(s["chiffres"][i]["outil"] == c["outil"]
                               and s["chiffres"][i]["parametres"].get("symbole") == l["symbole"] for i in cites), l
    elif t == "texte_absent":
        texte = " ".join(_textes(s, c.get("zone"))).lower()
        for motif in c["motifs"]:
            assert motif.lower() not in texte, motif
    elif t == "texte_present":
        texte = " ".join(_textes(s, c.get("zone")))
        for motif in c["motifs"]:
            assert motif in texte, motif
    elif t == "niveau_explication_par_defaut":
        assert s["explication"]["niveau_par_defaut"] == c["niveau"]
    elif t == "exclu_ou_signale":
        secteur = {x for x in TABLE.index if TABLE.at[x, "sector"] == c["secteur"] and TABLE.at[x, "asset_class"] == "equity"}
        for p in s["portefeuilles"]:
            for x in secteur & set(_poids(p)):
                assert any(x in (k.get("actifs") or k.get("symboles") or []) and k.get("source")
                           for k in s["gouvernance"]["controles"]), x
    elif t == "esg_source_ou_inconnu":
        fiches = s["specialistes"]["esg"]["fiches"]
        for x in c["symboles"]:
            f = fiches[x]
            assert f["statut"] == "information manquante" or (f["source_url"].startswith("https://") and f["source_date"]), f
            assert f["fichier"] == c["fichier"]
    elif t == "transparence_fnb":
        for p in s["portefeuilles"]:
            for x in set(c["symboles"]) & set(_poids(p)):
                assert any(k["controle"] == "transparence_fnb" and x in (k.get("actifs") or [])
                           and k.get("source") == c["fichier"] for k in p["controles"]), (p["id"], x)
    else:
        raise AssertionError(f"type inconnu {t}")


CAS = [(nom, a) for nom, s in SCENARIOS.items() for a in s["attendus"]]


@pytest.mark.parametrize("nom,attendu", CAS, ids=[f"{n}-{a['id']}" for n, a in CAS])
def test_attendu(nom, attendu):
    s = _sortie(nom)
    limites = contraintes(Profil(**SCENARIOS[nom]["profil"]))["limites"]
    verifier(s, attendu, limites)


@pytest.mark.parametrize("nom", SCENARIOS)
def test_regles_du_projet(nom):
    s = _sortie(nom)
    assert not s["exemple"] and 2 <= len(s["portefeuilles"]) <= 3
    assert s["gouvernance"]["essai"] <= s["gouvernance"]["essais_max"] == 2
    for t in _textes(s):
        assert "conseil" not in t.lower(), t
        for i in REPERE.findall(t):
            assert i in s["chiffres"], i
    for ref in s["chiffres"].values():  # chaque chiffre garde sa référence d'appel
        assert ref["outil"] and "parametres" in ref and ref["formule"] and ref["sources"]
    for p in s["portefeuilles"]:
        assert sum(l["poids"] for l in p["lignes"]) == pytest.approx(1, abs=1e-6)
        assert all(l["symbole"] in TABLE.index for l in p["lignes"])
