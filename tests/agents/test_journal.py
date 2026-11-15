import pytest

from agents.journal import DEMANDE, Journal, cle_propre, formater
from tools.mesures import pire_baisse


def test_cle_propre():
    assert cle_propre("vol", "BTC-USD") == "vol_btc_usd" and cle_propre("part", "XIU.TO", "A") == "part_xiu_to_a"


def test_enregistrer_garde_la_reference_et_dedoublonne():
    j = Journal()
    res = j.appeler(pire_baisse, "test", symbole="TSLA")
    cle = j.enregistrer("baisse_TSLA", res, "Pire baisse de TSLA")
    ref = j.chiffres[cle]
    assert cle == "baisse_tsla" and ref["outil"] == "pire_baisse" and ref["parametres"]["symbole"] == "TSLA"
    assert ref["valeur"] == pytest.approx(-0.730, abs=1e-3) and ref["periode"]["debut"] and ref["sources"]
    assert j.enregistrer("baisse_TSLA", res, "encore") == "baisse_tsla"  # même calcul : même clé
    autre = j.appeler(pire_baisse, "test", symbole="TSLA", devise="CAD")
    assert j.enregistrer("baisse_TSLA", autre, "en CAD") == "baisse_tsla_2"  # autre calcul : autre clé
    assert j.appels[0] == {"agent": "test", "outil": "pire_baisse", "parametres": res["parametres"]}


def test_formater_comme_l_interface():
    assert formater({"valeur": -0.7301, "unite": "fraction"}) == "−73,0 %"
    assert formater({"valeur": 0.7812, "unite": "coefficient de corrélation"}) == "0,78"


def test_problemes_texte():
    j = Journal()
    j.valeur_hors_outil("demande_tsla", 0.4, "fraction du capital", "Demandé", DEMANDE, "demande")
    assert j.problemes_texte("Vous demandez {demande_tsla} sur TSLA.") == []
    assert "chiffre écrit en clair" in j.problemes_texte("Vous demandez 40 % sur TSLA.")[0]
    assert "clé inconnue" in j.problemes_texte("Voir {vol_inconnue}.")[0]
    assert "hors accolades" in j.problemes_texte("demande_tsla : {demande_tsla}")[0]
    assert "en lettres" in j.problemes_texte("C'est huit fois le plafond.")[0]
    assert j.problemes_texte("Les trois portefeuilles, à la fois prudents.") == []
    assert j.rendre("Demandé : {demande_tsla}.") == "Demandé : 40,0 %."
