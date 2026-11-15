"""Briques du pipeline testables sans Bedrock : registre, gouvernance, vérification des textes."""

import json
from pathlib import Path

import pytest

from agents.gouvernance import controle_demande, pour_interface, seuils_depuis_limites, verifier_portefeuille
from agents.pipeline import verifier_textes
from agents.profil import Profil, contraintes
from agents.registre import Registre
from tools.mesures import gain_de_rattrapage, pire_baisse, volatilite
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def profil(nom):
    return Profil(**json.loads((SCENARIOS / f"{nom}.json").read_text(encoding="utf-8"))["profil"])


# --- registre ----------------------------------------------------------------------

def test_reperes_des_mesures_par_actif():
    r = Registre()
    assert r.enregistrer(volatilite("TSLA")) == ["vol_tsla"]
    assert r.enregistrer(pire_baisse("XIU.TO")) == ["baisse_xiu_to"]
    assert r.enregistrer(gain_de_rattrapage(pire_baisse("TSLA"))) == ["rattrapage_tsla"]
    assert r.chiffres["vol_tsla"]["valeur"] == volatilite("TSLA")["valeur"]
    assert r.chiffres["vol_tsla"]["outil"] == "volatilite"
    # Même appel : même repère, pas de doublon.
    assert r.enregistrer(volatilite("TSLA")) == ["vol_tsla"]
    # Autre fenêtre : autre repère.
    assert r.enregistrer(volatilite("TSLA", debut="2023-01-01")) == ["vol_tsla_2"]


def test_un_repere_par_nombre_pour_les_outils_multiples():
    r = Registre()
    poids = {"SPY": 0.6, "AGG": 0.3, "BTC-USD": 0.1}
    assert r.enregistrer(stats_portefeuille(poids), "a") == ["vol_a", "rend_a", "baisse_a"]
    assert r.enregistrer(parts_du_risque(poids), "a") == ["part_a_spy", "part_a_agg", "part_a_btc_usd"]
    assert round(r.chiffres["part_a_btc_usd"]["valeur"], 3) == 0.257
    assert r.chiffres["part_a_btc_usd"]["details"]["cle"] == "BTC-USD"
    reperes = r.enregistrer(correlations(["NVDA", "QQQ"]))
    assert reperes == ["corr_nvda_qqq"] and round(r.chiffres["corr_nvda_qqq"]["valeur"], 2) == 0.78
    # Toutes les références ont une valeur numérique unique (format Reference de l'interface).
    assert all(isinstance(c["valeur"], float) for c in r.chiffres.values())
    json.dumps(r.chiffres, ensure_ascii=False)


def test_portefeuilles_sans_nom_numerotes():
    r = Registre()
    assert r.nom_portefeuille({"SPY": 0.5, "AGG": 0.5}) == "p1"
    assert r.nom_portefeuille({"AGG": 0.5, "SPY": 0.5}) == "p1"
    assert r.nom_portefeuille({"SPY": 1.0}) == "p2"


def test_verification_des_textes():
    r = Registre()
    r.enregistrer(volatilite("TSLA"))
    v = verifier_textes(r, ["La volatilité de Tesla est {vol_tsla}.", "Plafond de 5 % et {inconnu}.",
                            "Un bon choix, je vous le recommande. Horizon de 3 ans."])
    assert v["reperes_inconnus"] == ["inconnu"]
    assert v["nombres_en_clair"] == ["5 %"]
    assert v["mots_interdits"] == ["bon choix", "recommand"]


# --- gouvernance avec les limites du profil ------------------------------------------

def test_une_seule_table_de_limites():
    p = profil("mateo")
    limites = contraintes(p)["limites"]
    seuils = seuils_depuis_limites(p, limites)["modéré"]
    assert seuils["secteur"] == limites["max_un_secteur"] == 0.20
    assert seuils["titre"] == limites["max_titre_individuel"]
    assert seuils["crypto"] == limites["max_crypto"]


def test_secteur_juge_avec_la_limite_du_profil():
    # 25 % de financières : accepté par les anciens seuils des outils (25 %), rejeté par le profil (20 %).
    p = profil("mateo")
    c = contraintes(p)
    poids = {"RY.TO": 0.10, "TD.TO": 0.10, "JPM": 0.05, "XBB.TO": 0.35, "ZST.TO": 0.2, "XIU.TO": 0.2}
    r = verifier_portefeuille(poids, None, p, c)
    assert "plafond_par_secteur" in r["rejets"]


def test_robert_demande_hors_profil_et_portefeuille_prudent():
    p = profil("robert")
    c = contraintes(p)
    tension = controle_demande({"texte": "40 % sur Tesla", "positions": [{"symbole": "TSLA", "poids": 0.4}]},
                               p, c["limites"])
    assert tension["statut"] == "à signaler" and tension["symboles"] == ["TSLA"]
    assert pour_interface(tension)["statut"] == "alerte"
    r = verifier_portefeuille({"ZST.TO": 0.45, "XBB.TO": 0.15, "XIU.TO": 0.2, "SPY": 0.1, "GLD": 0.1}, None, p, c)
    assert r["accepte"], r["rejets"]
    r = verifier_portefeuille({"TSLA": 0.4, "ZST.TO": 0.3, "XBB.TO": 0.1, "XIU.TO": 0.1, "GLD": 0.1}, None, p, c)
    assert {"plafond_par_titre", "part_risquee_max"} <= set(r["rejets"])


def test_amira_part_risquee_et_lignes():
    p = profil("amira")
    c = contraintes(p)
    tension = controle_demande({"texte": "tout en crypto et techno",
                                "positions": [{"classe": "crypto", "poids": 0.5}, {"role": "theme", "poids": 0.5}]},
                               p, c["limites"])
    assert tension["statut"] == "à signaler" and len(tension["ecarts"]) == 3
    r = verifier_portefeuille({"BTC-USD": 0.5, "NVDA": 0.5}, None, p, c)
    assert {"plafond_crypto", "lignes_min", "part_risquee_max"} <= set(r["rejets"])


def test_theme_interdit_sans_centre_d_interet():
    p = profil("robert")
    r = verifier_portefeuille({"ZST.TO": 0.45, "XBB.TO": 0.15, "XIU.TO": 0.2, "SPY": 0.1, "GLD": 0.1},
                              {"nom": "x", "symboles": ["SPY"]}, p, contraintes(p))
    assert "plafond_theme" in r["rejets"]


@pytest.mark.parametrize("statut,attendu", [("conforme", "ok"), ("non conforme", "echec"),
                                            ("à signaler", "alerte"), ("information manquante", "alerte")])
def test_statuts_de_l_interface(statut, attendu):
    assert pour_interface({"controle": "x", "statut": statut, "message": "m"})["statut"] == attendu
