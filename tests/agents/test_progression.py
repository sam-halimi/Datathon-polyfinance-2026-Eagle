"""Écran d'attente : agents/progression.py suit une analyse d'après le journal du pipeline, sans rien estimer."""

from __future__ import annotations

import json

import pytest

from agents import progression, serveur
from agents.journal import Journal


@pytest.fixture(autouse=True)
def en_memoire(monkeypatch):
    monkeypatch.delenv("EAGLE_PROGRESSION_SEAU", raising=False)
    monkeypatch.setattr(progression, "_MEMOIRE", {})


def test_identifiant_absent_ou_mal_forme_pas_de_suivi():
    for ident in (None, "", "court", "avec espace 12345", "../../etc/passwd", "x" * 65, 12345678):
        assert progression.ouvrir(ident) is None
        assert progression.lire(ident) == {"connu": False}
    assert progression.lire("identifiant-jamais-vu") == {"connu": False}


def test_le_journal_signale_chaque_agent_et_chaque_etape():
    suivi = progression.ouvrir("essai-0001")
    journal = Journal()
    journal.suivi = suivi.recevoir
    assert progression.lire("essai-0001")["agent"] is None
    journal.agent_courant = "Orchestrateur"
    journal.etape("Orchestrateur", "Lit votre profil.")
    journal.agent_courant = "ESG et qualité"
    etat = progression.lire("essai-0001")
    assert etat["connu"] and etat["phase"] == "analyse" and etat["agent"] == "ESG et qualité"
    assert etat["faits"] == [{"agent": "Orchestrateur", "fait": "Lit votre profil."}]
    assert etat["agents"] == list(progression.AGENTS) and etat["essai"] == 1 and etat["ecoule"] >= 0
    # Le journal garde son rôle : les étapes y sont toujours.
    assert journal.etapes == [{"agent": "Orchestrateur", "fait": "Lit votre profil."}]


def test_un_retour_de_la_gouvernance_au_constructeur_compte_un_essai():
    suivi = progression.ouvrir("essai-0002")
    for agent in ("Constructeur", "Gouvernance", "Constructeur", "Gouvernance", "Gouvernance", "Explication"):
        suivi.recevoir("agent", agent)
    etat = progression.lire("essai-0002")
    assert etat["essai"] == 2 and etat["agent"] == "Explication"


def test_un_nom_qui_n_est_pas_un_agent_est_ignore():
    suivi = progression.ouvrir("essai-0003")
    suivi.recevoir("agent", "Orchestrateur")
    suivi.recevoir("agent", "pipeline")
    suivi.recevoir("inconnu", "x")
    assert progression.lire("essai-0003")["agent"] == "Orchestrateur"


def test_phases_traduction_fin_et_echec():
    suivi = progression.ouvrir("essai-0004")
    suivi.recevoir("agent", "Explication")
    for phase in ("traduction", "terminee", "echec"):
        suivi.phase(phase)
        etat = progression.lire("essai-0004")
        assert etat["phase"] == phase and etat["agent"] is None


def test_une_panne_du_suivi_ne_touche_pas_le_journal():
    journal = Journal()

    def en_panne(*_):
        raise RuntimeError("S3 injoignable")

    journal.suivi = en_panne
    journal.agent_courant = "Orchestrateur"
    journal.etape("Orchestrateur", "Lit votre profil.")
    assert journal.agent_courant == "Orchestrateur" and len(journal.etapes) == 1


def test_une_ecriture_qui_echoue_est_ignoree(monkeypatch):
    def refuse(*_):
        raise OSError("disque plein")

    monkeypatch.setattr(progression, "_ecrire", refuse)
    suivi = progression.Suivi("essai-0005")
    suivi.recevoir("agent", "Orchestrateur")
    suivi.phase("terminee")
    assert progression.lire("essai-0005") == {"connu": False}


def test_sur_lambda_l_etat_passe_par_s3(monkeypatch):
    class FauxS3:
        def __init__(self):
            self.objets = {}

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objets[(Bucket, Key)] = Body

        def get_object(self, Bucket, Key):
            import io
            return {"Body": io.BytesIO(self.objets[(Bucket, Key)])}

    s3 = FauxS3()
    monkeypatch.setenv("EAGLE_PROGRESSION_SEAU", "seau-essai")
    monkeypatch.setattr(progression, "_s3", s3)
    suivi = progression.ouvrir("essai-0006")
    suivi.recevoir("agent", "Macro et taux")
    assert ("seau-essai", "progression/essai-0006.json") in s3.objets
    assert json.loads(s3.objets[("seau-essai", "progression/essai-0006.json")])["agent"] == "Macro et taux"
    # Une autre instance (mémoire vide) lit le même état dans S3.
    monkeypatch.setattr(progression, "_MEMOIRE", {})
    assert progression.lire("essai-0006")["agent"] == "Macro et taux"
    assert progression.lire("essai-absent") == {"connu": False}


def test_la_route_de_progression_repond_sans_compte(monkeypatch):
    monkeypatch.setenv("EAGLE_COGNITO_GROUPE", "groupe")
    monkeypatch.setenv("EAGLE_COGNITO_CLIENT", "client")
    monkeypatch.setenv("EAGLE_COMPTE_OBLIGATOIRE", "1")
    progression.ouvrir("essai-0007").recevoir("agent", "Constructeur")
    assert serveur.repondre("GET", "/progression", {"id": ["essai-0007"]}, {})["agent"] == "Constructeur"
    assert serveur.repondre("GET", "/progression", {}, {}) == {"connu": False}
