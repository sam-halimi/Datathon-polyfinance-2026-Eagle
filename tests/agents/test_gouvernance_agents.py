"""Gouvernance des agents : une seule table de limites, celle de agents.profil.contraintes."""

import json
from pathlib import Path

import pytest

from agents import gouvernance
from agents.outils_agents import fiche_actif
from agents.profil import Profil, contraintes
from agents.registre import Registre
from agents.schemas import Cadrage, PositionDemandee

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


def profil(nom):
    return Profil(**json.loads((SCENARIOS / f"{nom}.json").read_text(encoding="utf-8"))["profil"])


def cadrage(positions=(), classes=(), total=None):
    return Cadrage(demande_resumee="d", positions_demandees=list(positions), classes_demandees=list(classes),
                   poids_total_demande=total, tension="t", consigne_marche="", consigne_macro="", consigne_esg="")


def verifier(lignes, p, c=None):
    reg = Registre()
    gouvernance.inscrire_limites(reg, p)
    fiches = {l["symbole"]: fiche_actif(reg, l["symbole"]) for l in lignes}
    return gouvernance.verifier(lignes, p, c or cadrage(), reg, fiches)


def statut(v, nom):
    return next(c["statut"] for c in v["controles"] if c["controle"] == nom)


PRUDENT = [{"symbole": "ZST.TO", "poids": 0.35, "role": "defensif"}, {"symbole": "XBB.TO", "poids": 0.25, "role": "defensif"},
           {"symbole": "XIU.TO", "poids": 0.2, "role": "coeur"}, {"symbole": "GLD", "poids": 0.1, "role": "diversification"},
           {"symbole": "FTS.TO", "poids": 0.05, "role": "coeur"}, {"symbole": "TSLA", "poids": 0.05, "role": "demande"}]


def test_les_seuils_de_poids_viennent_du_profil():
    for nom in ("amira", "mateo", "robert"):
        p = profil(nom)
        lim = contraintes(p)["limites"]
        s = gouvernance.seuils_du_profil(p)[p.tolerance_risque]
        assert (s["titre"], s["crypto"], s["secteur"]) == (lim["max_titre_individuel"], lim["max_crypto"], lim["max_un_secteur"])


def test_secteur_de_mateo_au_plafond_du_profil():
    """Le plafond par secteur de Mateo vaut 20 % (profil), plus 25 % (ancienne table des outils)."""
    p = profil("mateo")
    lignes = [{"symbole": "RY.TO", "poids": 0.1, "role": "coeur"}, {"symbole": "TD.TO", "poids": 0.1, "role": "coeur"},
              {"symbole": "JPM", "poids": 0.03, "role": "coeur"}, {"symbole": "XBB.TO", "poids": 0.37, "role": "defensif"},
              {"symbole": "ZST.TO", "poids": 0.2, "role": "defensif"}, {"symbole": "ESGV", "poids": 0.2, "role": "coeur"}]
    assert statut(verifier(lignes, p), "plafond_par_secteur") == "non conforme"


def test_robert_prudent_accepte_et_demande_signalee():
    c = cadrage([PositionDemandee(symbole="TSLA", poids_demande=0.4, citation="40 %")])
    v = verifier(PRUDENT, profil("robert"), c)
    assert v["valeur"] and statut(v, "demande_hors_profil") == "à signaler"
    assert "TSLA : 40 % demandés, plafond du profil 5 %" in v["controles"][0]["message"]


def test_robert_demande_telle_quelle_rejetee():
    lignes = [{"symbole": "TSLA", "poids": 0.4, "role": "demande"}, {"symbole": "ZST.TO", "poids": 0.6, "role": "defensif"}]
    v = verifier(lignes, profil("robert"))
    assert not v["valeur"]
    for nom in ("plafond_par_titre", "lignes_min", "volatilite_max", "pire_baisse_max"):
        assert statut(v, nom) == "non conforme", nom


def test_part_risquee_du_profil():
    lignes = [{"symbole": s, "poids": 0.2, "role": "coeur"} for s in ("SPY", "QQQ", "XIU.TO", "ESGV")] + \
             [{"symbole": "ZST.TO", "poids": 0.2, "role": "defensif"}]
    v = verifier(lignes, profil("robert"))
    assert statut(v, "part_risquee_max") == "non conforme"


def test_amira_demande_totale_signalee():
    c = cadrage(classes=["crypto"], total=1.0)
    lignes = [{"symbole": "SPY", "poids": 0.4, "role": "coeur"}, {"symbole": "AGG", "poids": 0.2, "role": "defensif"},
              {"symbole": "GLD", "poids": 0.1, "role": "diversification"}, {"symbole": "XIU.TO", "poids": 0.15, "role": "coeur"},
              {"symbole": "NVDA", "poids": 0.1, "role": "theme"}, {"symbole": "BTC-USD", "poids": 0.05, "role": "crypto"}]
    v = verifier(lignes, profil("amira"), c)
    assert statut(v, "demande_hors_profil") == "à signaler" and v["valeur"]


def test_format_interface():
    reg = Registre()
    p = profil("robert")
    gouvernance.inscrire_limites(reg, p)
    v = gouvernance.verifier(PRUDENT, p, cadrage(), reg, {})
    sortie = gouvernance.pour_interface(v["controles"], reg, "a1")
    assert {c["statut"] for c in sortie} <= {"ok", "alerte", "echec", "manquant"}
    vol = next(c for c in sortie if c["id"] == "volatilite_max")
    assert vol["chiffres"] and reg.chiffres[vol["chiffres"][0]]["outil"] == "stats_portefeuille"
