"""Script de création de l'agent vocal : lecture du document, requêtes, écriture de web/.env.local.

Aucun appel réseau : l'envoi est remplacé par une fonction qui enregistre les requêtes.
"""

import re

import pytest

from tools import creer_agent_elevenlabs as c

DOC = c.DOC.read_text(encoding="utf-8")


def test_premier_message_et_consigne_lus_dans_le_document():
    premier, consigne = c.lire_doc(DOC)
    assert premier.startswith("Bonjour, je suis Eagle, votre assistant.")
    assert "Vous vouvoyez toujours la personne" in consigne
    assert "connaissance_niveau" in consigne and "capital_fictif" in consigne
    assert "conseil" in consigne  # cité comme mot interdit, et seulement là
    assert not re.search(r"\btu\b|\btoi\b|\bton\b|\bta\b|\btes\b", premier + consigne, re.IGNORECASE)


def test_outils_identiques_a_l_interface():
    voix = (c.RACINE / "web" / "components" / "Voix.tsx").read_text(encoding="utf-8")
    for outil in c.OUTILS:
        assert f"{outil['name']}:" in voix
        assert outil["type"] == "client" and outil["expects_response"]
        assert f"### {outil['name']}" in DOC
    questions = (c.RACINE / "web" / "lib" / "questions.ts").read_text(encoding="utf-8")
    for champ in c.CHAMPS[:8]:
        assert f'champ: "{champ}"' in questions
    diapos = (c.RACINE / "web" / "components" / "Diapositives.tsx").read_text(encoding="utf-8")
    for d in c.DIAPOSITIVES:
        assert f'id: "{d}"' in diapos


def test_creation_outils_puis_agent():
    envois = []

    def envoyer(chemin, corps):
        envois.append((chemin, corps))
        return {"id": f"outil_{len(envois)}"} if chemin.endswith("/tools") else {"agent_id": "agent_123"}

    premier, consigne = c.lire_doc(DOC)
    agent = c.creer(envoyer, premier, consigne, "voix_fr", "gemini-2.5-flash", "eleven_flash_v2_5", dire=lambda _: None)
    assert agent == "agent_123"
    assert [e[0] for e in envois] == ["/v1/convai/tools"] * 3 + ["/v1/convai/agents/create"]
    cfg = envois[-1][1]["conversation_config"]
    assert cfg["agent"]["prompt"]["tool_ids"] == ["outil_1", "outil_2", "outil_3"]
    assert cfg["agent"]["language"] == "fr" and cfg["agent"]["first_message"] == premier
    assert cfg["tts"] == {"model_id": "eleven_flash_v2_5", "voice_id": "voix_fr"}


def test_reponse_sans_identifiant_refusee():
    with pytest.raises(c.ErreurElevenLabs):
        c.creer(lambda chemin, corps: {}, "a", "b", None, "x", "y", dire=lambda _: None)


def test_env_local_remplace_sans_toucher_au_reste(tmp_path):
    f = tmp_path / ".env.local"
    f.write_text("NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_ELEVENLABS_AGENT_ID=ancien\n", encoding="utf-8")
    c.ecrire_env_web("nouveau", f)
    assert f.read_text(encoding="utf-8") == "NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_ELEVENLABS_AGENT_ID=nouveau\n"


def test_sans_cle_le_script_s_arrete(monkeypatch, capsys):
    monkeypatch.setattr(c, "charger_env", lambda: [])
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert c.main([]) == 1
    assert "ELEVENLABS_API_KEY absente" in capsys.readouterr().err
