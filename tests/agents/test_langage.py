"""Registre de l'explication selon connaissance_niveau."""

import json
from pathlib import Path

import pytest

from agents import langage, pipeline
from agents.profil import Profil

ROBERT = json.loads((Path(__file__).parents[1] / "scenarios" / "robert.json").read_text(encoding="utf-8"))
SORTIES = Path(__file__).parents[2] / "agents" / "sorties"


def test_registres_et_niveau_effectif():
    assert [langage.registre(n)["nom"] for n in range(1, 6)] == ["courant", "courant", "usuel", "professionnel",
                                                                  "professionnel"]
    assert langage.niveau_effectif(Profil(**ROBERT["profil"])) == 4  # Robert est « avancé »
    assert langage.niveau_effectif(Profil(**{**ROBERT["profil"], "connaissance_niveau": 5})) == 5
    assert langage.consigne(1) != langage.consigne(5) and "Vouvoie" in langage.consigne(3)


def test_lexique_aux_niveaux_un_et_deux_seulement():
    textes = ["La volatilité du portefeuille est faible, grâce aux obligations et à la diversification."]
    termes = [x["terme"] for x in langage.lexique(1, textes)]
    assert termes == ["volatilité", "diversification", "obligation"]
    assert all(x["definition"] for x in langage.lexique(2, textes))
    assert langage.lexique(3, textes) == [] and langage.lexique(5, textes) == []


def test_problemes_de_registre():
    assert "tutoiement" in langage.problemes(3, ["Tu as choisi un profil prudent."], False)[0]
    assert "jargon" in langage.problemes(1, ["La covariance des lignes est faible."], False)[0]
    pro = "La contribution au risque de XIU.TO domine ; corrélation modérée ; perte maximale contenue."
    assert langage.problemes(5, [pro], False) == []
    manque = langage.problemes(5, [pro], True)[0]  # avec des obligations : duration et sensibilité aux taux
    assert "duration" in manque and "sensibilite aux taux" in manque
    assert langage.problemes(5, ["Le portefeuille est calme."], False)


def _lancer(monkeypatch, niveau):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_pipeline_hors_ligne import FauxAgent

    consignes, prompts = [], []

    class Espion(FauxAgent):
        def __init__(self, nom, consigne, outils=None):
            super().__init__(nom, consigne, outils)
            if nom == "Explication":
                consignes.append(consigne)

        def __call__(self, prompt, structured_output_model=None):
            if self.nom == "Explication":
                prompts.append(prompt)
            return super().__call__(prompt, structured_output_model)

    monkeypatch.setattr(pipeline, "creer_agent", Espion)
    profil = Profil(**{**ROBERT["profil"], "connaissance_niveau": niveau})
    return pipeline.Session(profil, ROBERT["demande"], "Robert").executer(), consignes, prompts


def test_le_niveau_change_la_consigne_et_le_lexique(monkeypatch):
    s1, c1, _ = _lancer(monkeypatch, 1)
    s5, c5, p5 = _lancer(monkeypatch, 5)
    assert c1[0] != c5[0] and "Registre courant" in c1[0] and "Registre professionnel" in c5[0]
    assert s1["explication"]["registre"]["nom"] == "courant" and s1["explication"]["lexique"]
    assert s5["explication"]["registre"]["nom"] == "professionnel" and s5["explication"]["lexique"] == []
    assert s5["profil"]["connaissance_niveau"] == 5
    # Le texte simulé n'emploie pas le vocabulaire attendu : le niveau 5 est renvoyé une fois au modèle.
    assert len(p5) == 2 and "contribution au risque" in p5[1] and s5["explication"]["registre"]["ecarts"]


def _sortie(nom):
    f = SORTIES / f"{nom}.json"
    if not f.exists():
        pytest.skip(f"{f.name} absent : relancer l'étape 5 sur Bedrock")
    return json.loads(f.read_text(encoding="utf-8"))


def _texte(s):
    e = s["explication"]
    return " ".join([e["sujet"], e["niveau1"], *e["niveau2"], *s["limites"]["faits"]])


def test_bedrock_meme_profil_niveaux_un_et_cinq():
    """Sorties réelles : le même profil aux niveaux 1 et 5 donne des textes différents."""
    s1, s5 = _sortie("libre_niveau1"), _sortie("libre_niveau5")
    p1 = {k: v for k, v in s1["profil"].items() if k not in ("connaissance_niveau", "connaissance")}
    p5 = {k: v for k, v in s5["profil"].items() if k not in ("connaissance_niveau", "connaissance")}
    assert p1 == p5 and (s1["profil"]["connaissance_niveau"], s5["profil"]["connaissance_niveau"]) == (1, 5)
    assert _texte(s1) != _texte(s5)
    t5 = langage.normaliser(_texte(s5) + " " + " ".join(s5["explication"]["niveau2"]))
    for terme in langage.TERMES_PROFESSIONNELS:
        assert terme in t5, terme
    assert s1["explication"]["lexique"] and not s5["explication"]["lexique"]
    assert not langage.TUTOIEMENT.search(_texte(s1) + _texte(s5))
