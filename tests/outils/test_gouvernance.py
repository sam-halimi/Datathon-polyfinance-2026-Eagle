"""verifier_contraintes sur les vrais CSV, autour des trois personas."""

import pytest

from tools.gouvernance import SEUILS_PAR_TOLERANCE, tolerance_normalisee, verifier_contraintes
from tools.portefeuille import stats_portefeuille

AMIRA = {"horizon_annees": 15, "tolerance_risque": "élevé", "connaissance": "intermédiaire",
         "centres_interet": ["technologie"], "devise": "CAD"}
MATEO = {"horizon_annees": [8, 12], "tolerance_risque": "modéré", "devise": "CAD",
         "exclusions": ["énergie", "énergies fossiles"]}
ROBERT = {"horizon_annees": [3, 5], "tolerance_risque": "faible à modéré", "devise": "CAD"}

PRUDENT = {"ZST.TO": 0.4, "XBB.TO": 0.2, "XIU.TO": 0.2, "SPY": 0.1, "GLD": 0.1}
DYNAMIQUE = {"QQQ": 0.3, "SPY": 0.2, "XIU.TO": 0.15, "NVDA": 0.1, "MSFT": 0.1,
             "BTC-USD": 0.1, "GLD": 0.05}


def statuts(res):
    return {c["controle"]: c["statut"] for c in res["details"]["controles"]}


def controle(res, nom):
    return next(c for c in res["details"]["controles"] if c["controle"] == nom)


# --- Robert : grosse position sur un titre médiatisé ---------------------------

def test_robert_grosse_position_tsla_rejetee():
    res = verifier_contraintes({"TSLA": 0.4, "ZST.TO": 0.3, "XBB.TO": 0.3}, ROBERT)
    assert res["valeur"] is False
    assert {"plafond_par_titre", "volatilite_max", "pire_baisse_max"} <= set(res["details"]["rejets"])
    c = controle(res, "plafond_par_titre")
    assert c["actifs"] == ["TSLA"] and c["mesure"]["poids"] == 0.4
    assert "TSLA" in c["message"]


def test_robert_fourchette_prend_la_plus_prudente():
    res = verifier_contraintes(PRUDENT, ROBERT)
    assert res["valeur"] is True
    assert res["details"]["tolerance_retenue"] == "faible"
    assert res["details"]["horizon_retenu_annees"] == 3
    assert "tolerance_risque" in res["details"]["a_signaler"]
    # Horizon de moins de 5 ans : aucune crypto.
    assert res["details"]["seuils"]["crypto"] == 0


def test_robert_aucune_crypto_a_horizon_court():
    profil = {"horizon_annees": 4, "tolerance_risque": "élevé"}
    res = verifier_contraintes({**{k: v for k, v in DYNAMIQUE.items() if k != "GLD"},
                                "GLD": 0.04, "ETH-USD": 0.01}, profil)
    assert statuts(res)["plafond_crypto"] == "non conforme"
    assert "horizon" in controle(res, "plafond_crypto")["message"]


# --- Amira : 100 % crypto et techno --------------------------------------------

def test_amira_tout_crypto_et_techno_rejete():
    res = verifier_contraintes({"BTC-USD": 0.5, "ETH-USD": 0.2, "NVDA": 0.3}, AMIRA)
    assert res["valeur"] is False
    assert {"plafond_crypto", "plafond_par_titre", "volatilite_max"} <= set(res["details"]["rejets"])
    assert controle(res, "plafond_crypto")["mesure"] == pytest.approx(0.7)


def test_amira_portefeuille_diversifie_accepte():
    res = verifier_contraintes(DYNAMIQUE, AMIRA)
    assert res["valeur"] is True, res["details"]["rejets"]
    assert controle(res, "plafond_crypto")["mesure"] == pytest.approx(0.1)


def test_amira_theme_plafonne():
    pf = {"poids": DYNAMIQUE, "theme": {"nom": "techno", "symboles": ["NVDA", "MSFT"]}}
    res = verifier_contraintes(pf, AMIRA)
    assert res["details"]["rejets"] == ["plafond_theme"]
    assert controle(res, "plafond_theme")["mesure"] == pytest.approx(0.2)
    # Le plafond est un paramètre.
    assert verifier_contraintes(pf, AMIRA, plafond_theme=0.2)["valeur"] is True


def test_theme_sur_actions_et_fnb_seulement():
    pf = {"poids": DYNAMIQUE, "theme": {"nom": "crypto", "symboles": ["BTC-USD"]}}
    res = verifier_contraintes(pf, AMIRA)
    assert statuts(res)["theme_actions_et_fnb"] == "non conforme"


# --- Mateo : exclusions, et dire quand l'information manque ---------------------

def test_mateo_exclusion_par_secteur():
    pf = {"ESGV": 0.4, "XIU.TO": 0.25, "XBB.TO": 0.2, "ZST.TO": 0.1, "ENB.TO": 0.05}
    res = verifier_contraintes(pf, MATEO)
    assert res["valeur"] is False
    energie = [c for c in res["details"]["controles"]
               if c["controle"] == "exclusion" and c["exclusion"] == "énergie"][0]
    assert energie["statut"] == "non conforme"
    assert energie["actifs"] == ["ENB.TO"]
    assert energie["source"] == "assets_universe.csv"


def test_mateo_information_manquante_signalee():
    pf = {"ESGV": 0.4, "XIU.TO": 0.25, "XBB.TO": 0.2, "ZST.TO": 0.1, "GLD": 0.05}
    res = verifier_contraintes(pf, MATEO)
    assert res["valeur"] is True
    fossiles = [c for c in res["details"]["controles"] if c.get("exclusion") == "énergies fossiles"][0]
    assert fossiles["statut"] == "information manquante"
    assert "exclusion" in res["details"]["information_manquante"]
    # La limite des FNB non vus en transparence est dite.
    assert any("transparence" in l for l in res["details"]["limites"])


def test_exclusion_par_symbole_et_par_classe():
    profil = {**AMIRA, "exclusions": ["nvda", "cryptomonnaies"]}
    res = verifier_contraintes(DYNAMIQUE, profil)
    exclusions = [c for c in res["details"]["controles"] if c["controle"] == "exclusion"]
    assert [c["actifs"] for c in exclusions] == [["NVDA"], ["BTC-USD"]]


# --- Contrôles de base et références --------------------------------------------

def test_poids_et_symboles_invalides():
    res = verifier_contraintes({"SPY": 0.7, "ZZZZ": 0.2}, AMIRA)
    s = statuts(res)
    assert s["somme_des_poids"] == "non conforme"
    assert s["univers_source"] == "non conforme"
    assert s["risque_historique"] == "information manquante"
    res = verifier_contraintes({"SPY": 1.2, "AGG": -0.2}, AMIRA)
    assert statuts(res)["poids_positifs"] == "non conforme"


def test_chiffres_avec_reference_d_appel():
    res = verifier_contraintes(PRUDENT, ROBERT)
    vol = controle(res, "volatilite_max")
    attendu = stats_portefeuille(PRUDENT, devise="CAD")
    assert vol["mesure"] == attendu["valeur"]["volatilite"]
    assert vol["reference"]["outil"] == "stats_portefeuille"
    assert vol["reference"]["parametres"]["devise"] == "CAD"
    assert res["periode"] == attendu["periode"]
    assert res["outil"] == "verifier_contraintes"


def test_seuils_reglables():
    seuils = {k: dict(v) for k, v in SEUILS_PAR_TOLERANCE.items()}
    seuils["faible"]["volatilite"] = 0.01
    res = verifier_contraintes(PRUDENT, ROBERT, seuils=seuils)
    assert "volatilite_max" in res["details"]["rejets"]


def test_tolerances():
    assert tolerance_normalisee("modere") == ("modéré", None)
    assert tolerance_normalisee("Élevée") == ("élevé", None)
    assert tolerance_normalisee("faible à modéré")[0] == "faible"
    with pytest.raises(ValueError):
        tolerance_normalisee("extrême")
    with pytest.raises(ValueError):
        verifier_contraintes(PRUDENT, {"horizon_annees": 5})
