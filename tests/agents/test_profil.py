import pytest
from pydantic import ValidationError

from agents.profil import LIMITES_PAR_TOLERANCE, Profil, contraintes

BASE = dict(horizon_annees=10, objectif="croissance", tolerance_risque="modéré", connaissance="avancé",
            capital_fictif=10000)


def test_valeurs_par_defaut_et_nettoyage():
    p = Profil(**BASE, centres_interet=[" jeu vidéo ", "Jeu vidéo", ""])
    assert p.devise == "CAD" and p.preferences == [] and p.centres_interet == ["jeu vidéo"]


@pytest.mark.parametrize("champ,valeur", [("tolerance_risque", "très élevé"), ("capital_fictif", 0),
                                          ("horizon_annees", 0), ("devise", "EUR"), ("age", 30)])
def test_valeurs_refusees(champ, valeur):
    with pytest.raises(ValidationError):
        Profil(**{**BASE, champ: valeur})


def test_horizon_court_resserre_les_limites():
    c = contraintes(Profil(**{**BASE, "horizon_annees": 3}))
    assert c["limites"]["max_crypto"] == 0 and c["limites"]["max_part_risquee"] == 0.50
    assert "horizon" in c["origine"]["max_crypto"]
    assert c["limites"]["max_titre_individuel"] == LIMITES_PAR_TOLERANCE["modéré"]["max_titre_individuel"]


def test_horizon_court_ne_relache_jamais():
    c = contraintes(Profil(**{**BASE, "horizon_annees": 3, "tolerance_risque": "faible"}))
    assert c["limites"]["max_part_risquee"] == 0.40


def test_plafond_theme_parametre():
    p = Profil(**BASE, centres_interet=["jeu vidéo"])
    assert contraintes(p)["limites"]["plafond_theme"] == 0.10
    assert contraintes(p, plafond_theme=0.05)["limites"]["plafond_theme"] == 0.05
    with pytest.raises(ValueError):
        contraintes(p, plafond_theme=1.5)


def test_connaissance_niveau_de_1_a_5():
    """Le curseur d'Eagle : la connaissance en découle si elle n'est pas donnée, et 6 est refusé."""
    sans = {k: v for k, v in BASE.items() if k != "connaissance"}
    attendu = {1: "débutant", 2: "débutant", 3: "intermédiaire", 4: "avancé", 5: "avancé"}
    for niveau, connaissance in attendu.items():
        assert Profil(**sans, connaissance_niveau=niveau).connaissance == connaissance
    assert Profil(**BASE).connaissance_niveau is None
    assert Profil(**BASE, connaissance_niveau=2).connaissance == BASE["connaissance"]
    with pytest.raises(ValidationError):
        Profil(**sans, connaissance_niveau=6)
