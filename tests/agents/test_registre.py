import pytest

from agents.registre import Registre, afficher, identifiant
from tools import mesures


@pytest.fixture
def reg():
    r = Registre()
    r.inscrire(mesures.volatilite("TSLA"), "volatilite_tsla", "Volatilité de TSLA")
    return r


def test_identifiant():
    assert identifiant("pire_baisse", "XIU.TO") == "pire_baisse_xiu_to"
    assert identifiant("part_risque", "a", "BTC-USD") == "part_risque_a_btc_usd"


def test_inscription_garde_la_reference(reg):
    c = reg.chiffres["volatilite_tsla"]
    assert c["outil"] == "volatilite" and c["parametres"]["symbole"] == "TSLA"
    assert c["valeur"] == pytest.approx(0.596, abs=0.001) and c["format"] == "pourcent"
    assert c["periode"]["debut"] == "2021-11-12" and c["details"]["decrit"] == "Volatilité de TSLA"
    assert reg.appels[0]["outil"] == "volatilite" and reg.appels[0]["chiffre"] == "volatilite_tsla"


def test_affichage_a_la_francaise():
    assert afficher(-0.7297, "pourcent") == "−73,0 %"
    assert afficher(0.78, "decimal") == "0,78"
    assert afficher(200000, "montant") == "200 000 $"


def test_texte_avec_repere_accepte(reg):
    assert reg.verifier_texte("TSLA varie de {volatilite_tsla} par an, comme le S&P 500 et le taux 10 ans.") == []


@pytest.mark.parametrize("texte", ["TSLA a perdu 73 %.", "Une volatilité de 59,6 %.", "Voir {inconnu}."])
def test_chiffre_en_dur_ou_repere_inconnu_refuse(reg, texte):
    assert reg.verifier_texte(texte)


def test_seules_les_valeurs_numeriques_s_inscrivent(reg):
    with pytest.raises(TypeError):
        reg.inscrire({**mesures.volatilite("SPY"), "valeur": {"a": 1}}, "x", "x")
