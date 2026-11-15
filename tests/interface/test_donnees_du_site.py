"""Les tables que le site embarque couvrent tout ce que le pipeline peut renvoyer.

Une analyse en direct d'un profil quelconque peut retenir n'importe quel actif des deux
tables sourcées (univers de départ et univers étendu, thèmes compris). Le site lit le
secteur, la zone et le cours de chaque ligne dans web/data/univers.json : un symbole absent
donnait « Inconnu » dans la répartition et aucun cours. Ces tests échouent dès qu'une table
de data/ gagne un symbole sans que `python web/scripts/graphiques.py` ait été relancé.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from agents.serveur import scenarios_du_portefeuille
from tools.donnees import charger_prix, univers

RACINE = Path(__file__).resolve().parents[2]
SITE = RACINE / "web" / "data"
A_RELANCER = "relancer : python web/scripts/graphiques.py"


@pytest.fixture(scope="module")
def table() -> dict:
    return json.loads((SITE / "univers.json").read_text(encoding="utf-8"))["actifs"]


def test_tous_les_actifs_des_tables_sourcees_sont_dans_le_site(table):
    attendus = set(univers(etendu=True).index)
    themes = set(pd.read_csv(RACINE / "data" / "themes.csv", dtype=str)["symbole"])
    assert themes <= attendus, f"symboles de data/themes.csv absents des tables d'univers : {sorted(themes - attendus)}"
    assert attendus <= set(table), f"absents de web/data/univers.json ({A_RELANCER}) : {sorted(attendus - set(table))}"


def test_chaque_actif_a_un_secteur_une_zone_et_un_cours(table):
    for symbole, a in table.items():
        assert a["nom"] and a["secteur"] and a["zone"] and a["devise"], symbole
        assert "Inconnu" not in a["secteur"] and "Inconnu" not in a["zone"], symbole
        assert len(a["hebdo"]) > 50, f"{symbole} : cours hebdomadaire trop court ({len(a['hebdo'])} points)"


def test_le_dernier_cours_du_site_est_celui_des_donnees(table):
    """Les cours du site viennent des fichiers de data/, sans retouche : même dernier adj_close."""
    for symbole in ("RY.TO", "TSLA", "ICLN", "XEF.TO", "BTC-USD"):
        serie = charger_prix(symbole)[symbole].dropna()
        date, valeur = table[symbole]["hebdo"][-1]
        assert date == serie.index[-1].date().isoformat(), f"{symbole} ({A_RELANCER})"
        assert valeur == pytest.approx(float(serie.iloc[-1]))


@pytest.mark.parametrize("persona", ["robert", "amira", "mateo"])
def test_les_demonstrations_ont_leurs_graphiques_et_leur_eventail(persona, table):
    sortie = json.loads((RACINE / "agents" / "sorties" / f"{persona}.json").read_text(encoding="utf-8"))
    g = json.loads((SITE / "graphiques" / f"{persona}.json").read_text(encoding="utf-8"))
    for ptf in sortie["portefeuilles"]:
        symboles = {ligne["symbole"] for ligne in ptf["lignes"]}
        assert symboles <= set(table), f"{persona} {ptf['id']} : {sorted(symboles - set(table))} absents du site"
        parts = g["repartitions"][ptf["id"]]["actif"]
        assert {s for p in parts for s in p["symboles"]} == symboles, f"{persona} {ptf['id']} : répartition périmée ({A_RELANCER})"
    # L'éventail affiché est celui du portefeuille retenu par la gouvernance, recalculé à l'identique.
    attendu = scenarios_du_portefeuille(sortie)
    assert g["scenarios"]["parametres"] == attendu["parametres"], f"{persona} : éventail périmé ({A_RELANCER})"
    assert g["scenarios"]["valeur"]["p50"] == pytest.approx(attendu["valeur"]["p50"])


def test_l_eventail_porte_sur_le_portefeuille_retenu():
    """scenarios_du_portefeuille suit gouvernance.portefeuille_retenu, pas l'ordre de la liste."""
    sortie = json.loads((RACINE / "agents" / "sorties" / "robert.json").read_text(encoding="utf-8"))
    autre = next(p for p in sortie["portefeuilles"] if p["id"] != sortie["gouvernance"]["portefeuille_retenu"])
    sortie["gouvernance"] = {**sortie["gouvernance"], "portefeuille_retenu": autre["id"]}
    poids = scenarios_du_portefeuille(sortie)["parametres"]["poids"]
    assert poids == {ligne["symbole"]: ligne["poids"] for ligne in autre["lignes"]}
