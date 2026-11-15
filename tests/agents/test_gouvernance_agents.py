"""Une seule table de limites : la gouvernance applique contraintes(profil), pas ses propres plafonds."""

from agents.gouvernance import controler, limites_du_profil
from agents.profil import Profil

MODERE = Profil(horizon_annees=8, objectif="équilibre", tolerance_risque="modéré", connaissance="intermédiaire",
                capital_fictif=50000)


def _statut(verdict, nom):
    return next(c["statut"] for c in verdict["controles"] if c["controle"] == nom)


def test_plafond_secteur_du_profil_et_non_de_l_outil():
    # 22 % en actions financières : sous les 25 % de tools/gouvernance.py, au-dessus des 20 % du profil.
    c = limites_du_profil(MODERE)
    assert c["limites"]["max_un_secteur"] == 0.20
    ptf = {"poids": {"RY.TO": 0.08, "TD.TO": 0.07, "JPM": 0.07, "XBB.TO": 0.38, "ZST.TO": 0.20, "SPY": 0.20}}
    v = controler(ptf, MODERE, c)
    assert _statut(v, "plafond_par_secteur") == "non conforme"
    assert not v["accepte"]


def test_diversification_du_profil():
    c = limites_du_profil(MODERE)
    v = controler({"poids": {"SPY": 0.5, "XBB.TO": 0.5}}, MODERE, c)
    assert _statut(v, "diversification") == "non conforme"
