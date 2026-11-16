"""Option anglaise : agents/traduction.py traduit les textes sans jamais toucher à un chiffre.

Les tests hors ligne remplacent le modèle par une fonction. Le dernier groupe relit les
versions anglaises enregistrées des trois démonstrations et les compare au français.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from agents import traduction as T

RACINE = Path(__file__).resolve().parents[2]
SORTIES = RACINE / "agents" / "sorties"
PERSONAS = ("amira", "mateo", "robert")


@pytest.fixture(autouse=True)
def memoire_vide(monkeypatch):
    """Chaque test part d'une mémoire vide et n'écrit rien sur disque."""
    monkeypatch.setattr(T, "_memoire", {})


def faux_modele(lot: list[str]) -> list[str]:
    return [f"EN {t}" for t in lot]


def exemple() -> dict:
    return {
        "profil": {"tolerance_risque": "modéré", "objectif": "équilibre"},
        "demande_analysee": {"texte": "Je veux 40 % sur Tesla.", "resume": "Une part de 40 % sur Tesla."},
        "portefeuilles": [{
            "id": "A", "nom": "Équilibre prudent",
            "lignes": [{"symbole": "XIU.TO", "classe_code": "etf_equity", "role": "Le cœur du portefeuille",
                        "pourquoi": "XIU.TO pèse {poids_a_xiu_to} du capital, sous le plafond de 10,0 %.",
                        "sources": [{"fichier": "data/assets_universe.csv", "objet": "nom et classe"}]}],
            "controles": [{"statut": "ok", "controle": "somme_des_poids", "titre": "Le capital est réparti en entier",
                           "detail": "Les poids totalisent 100,0 % du capital fictif de 50 000 CAD."}],
            "adequation": [{"critere": "horizon", "statut": "respecté", "attente": "Pouvoir attendre 8 an(s).",
                            "reponse": "Pire baisse {ptf_a_pire_baisse}.", "regle": "respecté si effacée", "raison": None}],
        }],
        "limites": {"faits": ["Prix quotidiens du 2021-11-12 au 2026-11-12 (data/prices_daily.csv, adj_close)."]},
        "chiffres": {"ptf_a_volatilite": {
            "outil": "stats_portefeuille", "valeur": 0.0712, "unite": "fraction du capital",
            "formule": "volatilité = √(wᵀ Σ w) × 252 ; pire baisse = min(valeur / plus haut - 1)",
            "details": {"nature": "mesure passée, pas une promesse"}}},
        "meta": {"modele": "essai"},
    }


def test_les_valeurs_protegees_ne_sont_pas_montrees_au_modele():
    masque, valeurs = T.masquer("XIU.TO pèse {poids_a_xiu_to}, soit 12 500,50 $ au 2026-11-12 (data/prix.csv, adj_close).")
    assert valeurs == ["XIU.TO", "{poids_a_xiu_to}", "12 500,50", "2026-11-12", "data/prix.csv", "adj_close"]
    assert not re.search(r"\d", T._JETON.sub("", masque))
    assert "poids_a" not in masque and "csv" not in masque
    assert T.demasquer(masque, valeurs) == "XIU.TO pèse {poids_a_xiu_to}, soit 12 500,50 $ au 2026-11-12 (data/prix.csv, adj_close)."


def test_un_objet_json_reste_entier():
    masque, valeurs = T.masquer('Outil : stats_portefeuille, paramètres {"debut": null, "poids": {"A": 0.3}}')
    assert valeurs == ["stats_portefeuille", '{"debut": null, "poids": {"A": 0.3}}']


def test_un_ordinal_devient_anglais_et_rien_d_autre():
    masque, valeurs = T.masquer("le 1er rang, puis le 3e")
    assert T.demasquer(masque, valeurs) == "le 1st rang, puis le 3rd"


@pytest.mark.parametrize("cible", ["The total is ⟦0⟧.", "⟦0⟧ and ⟦1⟧ and ⟦1⟧", "⟦0⟧, ⟦1⟧ and ⟦2⟧", "No token at all"])
def test_une_traduction_qui_perd_ou_ajoute_un_jeton_est_refusee(cible):
    assert not T.jetons_respectes("Le total est ⟦0⟧ sur ⟦1⟧.", cible)


def test_l_ordre_des_jetons_peut_changer():
    assert T.jetons_respectes("⟦0⟧ janvier ⟦1⟧", "January ⟦0⟧, ⟦1⟧") and T.jetons_respectes("⟦0⟧ de ⟦1⟧", "⟦1⟧'s ⟦0⟧")


def test_la_sortie_francaise_est_rendue_telle_quelle():
    s = exemple()
    assert T.traduire_sortie(s, "fr") is s


def test_les_textes_sont_traduits_les_codes_et_les_chiffres_ne_bougent_pas():
    source = exemple()
    avant = copy.deepcopy(source)
    en = T.traduire_sortie(source, "en", faux_modele)
    assert source == avant, "la sortie d'origine ne doit pas être modifiée"
    p, l = en["portefeuilles"][0], en["portefeuilles"][0]["lignes"][0]
    assert p["nom"] == "EN Équilibre prudent"
    assert l["pourquoi"] == "EN XIU.TO pèse {poids_a_xiu_to} du capital, sous le plafond de 10,0 %."
    assert p["controles"][0]["detail"] == "EN Les poids totalisent 100,0 % du capital fictif de 50 000 CAD."
    assert en["limites"]["faits"][0].endswith("du 2021-11-12 au 2026-11-12 (data/prices_daily.csv, adj_close).")
    # Codes, symboles, valeurs et paroles de l'utilisateur : intacts.
    assert en["profil"] == avant["profil"]
    assert en["demande_analysee"]["texte"] == "Je veux 40 % sur Tesla."
    assert (l["symbole"], l["classe_code"], l["sources"][0]["fichier"]) == ("XIU.TO", "etf_equity", "data/assets_universe.csv")
    assert (p["controles"][0]["statut"], p["controles"][0]["controle"], p["adequation"][0]["statut"]) == ("ok", "somme_des_poids", "respecté")
    assert en["chiffres"]["ptf_a_volatilite"]["valeur"] == 0.0712
    assert en["langue"] == "en" and en["meta"]["traduction"]["restes_en_francais"] == 0


def test_un_objet_partage_entre_deux_endroits_est_traduit_et_compte_une_fois():
    source = exemple()
    # Comme dans le pipeline : les contrôles de la gouvernance sont ceux du portefeuille retenu, le même objet.
    source["gouvernance"] = {"controles": source["portefeuilles"][0]["controles"]}
    en = T.traduire_sortie(source, "en", faux_modele)
    assert en["gouvernance"]["controles"][0]["titre"] == "EN Le capital est réparti en entier"
    assert en["meta"]["traduction"]["restes_en_francais"] == 0


def test_unite_et_formule_restent_en_francais_avec_l_anglais_a_cote():
    c = T.traduire_sortie(exemple(), "en", faux_modele)["chiffres"]["ptf_a_volatilite"]
    assert c["unite"] == "fraction du capital" and c["unite_en"] == "EN fraction du capital"
    assert c["formule"].startswith("volatilité = ")
    # Le site choisit une partie de la formule par son rang : même nombre de parties dans les deux langues.
    assert len(c["formule_en"].split(" ; ")) == len(c["formule"].split(" ; ")) == 2


def test_une_panne_du_modele_laisse_le_francais_sans_faire_echouer_l_analyse():
    def en_panne(lot):
        raise RuntimeError("serviceUnavailableException")

    source = exemple()
    en = T.traduire_sortie(source, "en", en_panne)
    assert en["portefeuilles"] == source["portefeuilles"] and en["limites"] == source["limites"]
    bilan = en["meta"]["traduction"]
    assert bilan["restes_en_francais"] == bilan["textes"] > 0


def test_un_texte_dont_le_modele_change_un_chiffre_reste_en_francais():
    def tricheur(lot):  # perd le jeton du premier texte qui en a un, traduit bien les autres
        return [re.sub(r"⟦0⟧", "40", t, count=1) if i == 0 else f"EN {t}" for i, t in enumerate(lot)]

    source = exemple()
    en = T.traduire_sortie(source, "en", tricheur)
    assert en["meta"]["traduction"]["restes_en_francais"] >= 1
    francais = json.dumps(source, ensure_ascii=False)
    for texte in _textes(en):
        assert texte.startswith("EN ") or texte in francais


def test_un_texte_refuse_est_repris_une_fois():
    appels = []

    def capricieux(lot):  # première réponse : jeton perdu ; seconde : correcte
        appels.append(lot)
        return ["Total lost" for _ in lot] if len(appels) == 1 else faux_modele(lot)

    resultat = T.traduire_textes(["Le total est 12 %."], capricieux)
    assert len(appels) == 2 and resultat == {"Le total est 12 %.": "EN Le total est 12 %."}


def test_un_texte_deja_traduit_ne_rappelle_pas_le_modele():
    appels: list[list[str]] = []

    def compte(lot):
        appels.append(lot)
        return faux_modele(lot)

    T.traduire_textes(["Les poids totalisent 100,0 % du capital."], compte)
    resultat = T.traduire_textes(["Les poids totalisent 98,5 % du capital."], compte)
    assert len(appels) == 1, "la mémoire à jetons sert pour toutes les valeurs"
    assert resultat == {"Les poids totalisent 98,5 % du capital.": "EN Les poids totalisent 98,5 % du capital."}


def test_la_fiche_d_un_actif_est_traduite_par_la_route(monkeypatch):
    from agents import serveur

    monkeypatch.setattr(T, "modele_bedrock", faux_modele)
    monkeypatch.setattr(serveur.comptes, "exiger", lambda *a, **k: None)
    fr = serveur.repondre("GET", "/actif", {"symbole": ["TSLA"], "tolerance": ["faible"], "horizon": ["4"]}, {})
    en = serveur.repondre("GET", "/actif", {"symbole": ["TSLA"], "tolerance": ["faible"], "horizon": ["4"], "langue": ["en"]}, {})
    assert "langue" not in fr and en["langue"] == "en"
    assert en["statut"] == fr["statut"] and en["symbole"] == "TSLA"
    assert en["titre"] == f"EN {fr['titre']}" and en["raisons"] == [f"EN {r}" for r in fr["raisons"]]
    assert {k: v["valeur"] for k, v in en["chiffres"].items()} == {k: v["valeur"] for k, v in fr["chiffres"].items()}


# --- Versions anglaises enregistrées des trois démonstrations --------------------------------

def _textes(noeud):
    if isinstance(noeud, dict):
        for v in noeud.values():
            yield from _textes(v)
    elif isinstance(noeud, list):
        for v in noeud:
            yield from _textes(v)
    elif isinstance(noeud, str):
        yield noeud


def _comparer(fr, en, chemin=""):
    """Même structure ; toute valeur qui n'est pas un texte est identique ; un texte garde ses valeurs protégées."""
    if isinstance(fr, dict):
        assert isinstance(en, dict), chemin
        ajoutees = set(en) - set(fr)
        assert set(fr) <= set(en) and all(k.endswith("_en") or k in ("langue", "traduction") for k in ajoutees), (chemin, ajoutees)
        for k in fr:
            _comparer(fr[k], en[k], f"{chemin}.{k}")
    elif isinstance(fr, list):
        assert isinstance(en, list) and len(fr) == len(en), chemin
        for i, (a, b) in enumerate(zip(fr, en)):
            _comparer(a, b, f"{chemin}[{i}]")
    elif isinstance(fr, str):
        assert isinstance(en, str), chemin
        # « 1er » devient « 1st » : on compare le nombre, sans son suffixe d'ordinal.
        valeurs = lambda t: Counter(re.sub(r"^(\d+)(?:er|re|e)$", r"\1", v) for v in T.masquer(t)[1])  # noqa: E731
        assert valeurs(en) == valeurs(fr), f"{chemin} : un chiffre, un marqueur ou un fichier a changé\n{fr}\n{en}"
    else:
        assert fr == en, chemin


@pytest.mark.parametrize("persona", PERSONAS)
def test_la_demonstration_anglaise_a_les_memes_chiffres_que_la_francaise(persona):
    fr = json.loads((SORTIES / f"{persona}.json").read_text(encoding="utf-8"))
    en = json.loads((SORTIES / "en" / f"{persona}.json").read_text(encoding="utf-8"))
    _comparer(fr, en)
    assert en["langue"] == "en"
    assert en["meta"]["traduction"]["restes_en_francais"] <= 3, "trop de textes restés en français"


@pytest.mark.parametrize("persona", PERSONAS)
def test_la_demonstration_anglaise_ne_parle_ni_de_conseil_ni_de_prevision_promise(persona):
    en = (SORTIES / "en" / f"{persona}.json").read_text(encoding="utf-8").lower()
    for mot in ("advisor", "adviser", "we recommend", "i recommend", "guaranteed return"):
        assert mot not in en, mot
