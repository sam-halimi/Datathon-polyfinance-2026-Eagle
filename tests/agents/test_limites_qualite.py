"""Avertissements de data/base/rapport_prix_etendus.txt devenus limites propres au portefeuille."""

import pytest

from agents import gouvernance as gv
from agents.adequation import _ref
from agents.journal import REPERE, Journal, cle
from agents.limites import avertissements_prix, limites_specifiques
from agents.profil import Profil

PROFIL = Profil(horizon_annees=15, objectif="croissance", tolerance_risque="élevé", connaissance_niveau=3,
                centres_interet=["l'énergie propre", "les jeux vidéo"], capital_fictif=10000)
BASE = {"SPY": 0.30, "XIU.TO": 0.25, "XBB.TO": 0.20, "GLD": 0.10}


def _limites(poids):
    j = Journal()
    ids = gv.enregistrer_limites(j, gv.limites_du_profil(PROFIL))
    mesures = {s: {"vol": j.mesurer("volatilite", cle("vol", s), symbole=s)["valeur"],
                   "pb": j.mesurer("pire_baisse", cle("pb", s), symbole=s)["valeur"]} for s in poids}
    for s, w in poids.items():
        j.enregistrer(cle("poids", "A", s), _ref("constructeur", {"symbole": s}, w, "fraction du capital", "", ["x"], "décision"))
    return limites_specifiques(PROFIL, poids, "A", j, mesures, ids, []), j


def test_le_rapport_est_lu():
    a = avertissements_prix()
    assert a["NXT"][0] == {"type": "historique_court", "date": "2023-02-09", "brut": a["NXT"][0]["brut"]}
    assert [x["date"] for x in a["GME"]] == ["2024-05-13", "2024-05-14", "2024-06-06"]
    assert a["BE"][0]["type"] == "saut"


def test_lignes_signalees_retenues_deviennent_des_limites():
    lim, j = _limites({**BASE, "NXT": 0.05, "GME": 0.05, "BE": 0.05})
    qualite = {x["lignes"][0]: x for x in lim if x["type"] == "qualite_donnees"}
    assert set(qualite) == {"NXT", "GME", "BE"}
    nxt = qualite["NXT"]
    assert "2023-02-09" in nxt["texte"] and j.chiffres[cle("cours", "NXT")]["outil"] == "couverture_cours"
    gme = qualite["GME"]
    sauts = [i for i in REPERE.findall(gme["texte"]) if i.startswith("saut_gme")]
    assert len(sauts) == 3 and j.chiffres[sauts[0]]["valeur"] == pytest.approx(0.74, abs=0.01)
    assert all("rapport_prix_etendus.txt" in x["texte"] for x in qualite.values())
    for x in qualite.values():
        assert all(i in j.chiffres for i in REPERE.findall(x["texte"]))
    # Avec NXT, la fenêtre commune du portefeuille commence en 2023.
    assert "commence le 2023-02-09" in nxt["texte"]


def test_rien_si_ces_lignes_ne_sont_pas_retenues():
    lim, _ = _limites({**BASE, "QQQ": 0.15})
    assert not [x for x in lim if x["type"] == "qualite_donnees"]
