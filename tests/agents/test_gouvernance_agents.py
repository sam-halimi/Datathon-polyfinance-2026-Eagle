from agents.gouvernance import controle_demande, enregistrer_limites, seuils_du_profil, verifier_portefeuille
from agents.journal import Journal
from agents.profil import Profil, contraintes

ROBERT = Profil(horizon_annees=3, objectif="préservation du capital", tolerance_risque="faible",
                connaissance="avancé", capital_fictif=200000)
PRUDENT = {"ZST.TO": 0.45, "XBB.TO": 0.15, "AGG": 0.10, "GLD": 0.10, "XIU.TO": 0.15, "FTS.TO": 0.05}


def _statuts(res):
    return {k["controle"]: k["statut"] for k in res["controles"]}


def test_une_seule_table_de_limites():
    """Les limites de poids viennent de agents/profil.py, pas des seuils propres à tools/."""
    p = Profil(horizon_annees=10, objectif="équilibre", tolerance_risque="modéré", connaissance="avancé",
               capital_fictif=1000)
    seuils = seuils_du_profil(p, contraintes(p))["modéré"]
    assert seuils["secteur"] == contraintes(p)["limites"]["max_un_secteur"] == 0.20  # tools/ dit 0,25
    assert seuils["volatilite"] == 0.14  # seuil de risque gardé de tools/


def test_portefeuille_prudent_accepte():
    res = verifier_portefeuille(Journal(), ROBERT, contraintes(ROBERT), PRUDENT, [], None)
    assert res["accepte"], [k for k in res["controles"] if k["statut"] != "ok"]
    assert {"nombre_de_lignes", "part_risquee", "volatilite_max", "plafond_par_titre"} <= set(_statuts(res))


def test_la_demande_de_robert_est_rejetee():
    poids = {"TSLA": 0.40, "ZST.TO": 0.30, "XBB.TO": 0.30}
    res = verifier_portefeuille(Journal(), ROBERT, contraintes(ROBERT), poids, [], None)
    s = _statuts(res)
    assert not res["accepte"] and s["plafond_par_titre"] == "echec" and s["part_risquee"] == "ok"
    assert s["nombre_de_lignes"] == "echec"


def test_part_risquee_et_theme():
    amira = Profil(horizon_annees=15, objectif="croissance", tolerance_risque="élevé", connaissance="intermédiaire",
                   centres_interet=["technologie"], capital_fictif=10000)
    poids = {"SPY": 0.5, "QQQ": 0.3, "NVDA": 0.15, "BTC-USD": 0.05}
    res = verifier_portefeuille(Journal(), amira, contraintes(amira), poids, ["NVDA", "QQQ"], "technologie")
    s = _statuts(res)
    assert s["part_risquee"] == "echec" and s["plafond_theme"] == "echec" and s["nombre_de_lignes"] == "echec"


def test_controle_demande_releve_la_tension_avec_des_cles():
    j = Journal()
    c = contraintes(ROBERT)
    cles = enregistrer_limites(j, ROBERT, c)
    cartes = controle_demande(j, ROBERT, c, [{"symboles": ["TSLA"], "poids_demande": 0.4, "extrait": "…"}], cles)
    assert len(cartes) == 1 and cartes[0]["controle"] == "demande_hors_profil" and cartes[0]["statut"] == "alerte"
    assert not cartes[0]["bloquant"] and j.problemes_texte(cartes[0]["detail"]) == []
    outils = {j.chiffres[k]["outil"] for k in cartes[0]["chiffres"]}
    assert {"pire_baisse", "volatilite", "gain_de_rattrapage", "demande de l'utilisateur"} <= outils
