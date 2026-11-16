"""Crée un agent vocal Eagle NEUF sur ElevenLabs Agents et écrit son identifiant dans web/.env.local.

L'agent Eagle existe déjà (agent_1201m7gj8np7fmnvcgfq6a5gqt68, voir docs/agent-elevenlabs.md) :
ce script ne sert qu'à repartir de zéro (agent supprimé, autre compte). Il crée un nouvel agent.

    python -m tools.creer_agent_elevenlabs            # crée les trois outils, puis l'agent
    python -m tools.creer_agent_elevenlabs --a-blanc  # affiche ce qui serait envoyé, sans clé

Clé : ELEVENLABS_API_KEY, lue dans `.env` par tools.env (jamais affichée ni écrite ailleurs).
Le premier message et la consigne viennent de docs/agent-elevenlabs.md, seule source. Les outils
sont ceux de web/components/Voix.tsx (outils « client » : l'interface les exécute).

API (documentation officielle ElevenLabs, novembre 2026) :
- POST https://api.elevenlabs.io/v1/convai/tools          {"tool_config": {...}} -> {"id": ...}
- POST https://api.elevenlabs.io/v1/convai/agents/create  {"name", "conversation_config", "tags"} -> {"agent_id": ...}
- authentification : en-tête « xi-api-key ».
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from tools.env import RACINE, charger_env

API = "https://api.elevenlabs.io"
DOC = RACINE / "docs" / "agent-elevenlabs.md"
ENV_WEB = RACINE / "web" / ".env.local"
VARIABLE_AGENT = "NEXT_PUBLIC_ELEVENLABS_AGENT_ID"

LLM_DEFAUT = "gemini-2.5-flash"
TTS_DEFAUT = "eleven_flash_v2_5"  # multilingue : le français l'exige

CHAMPS = ["horizon_annees", "objectif", "tolerance_risque", "connaissance_niveau", "preferences", "exclusions",
          "centres_interet", "capital_fictif", "prenom", "demande"]
DIAPOSITIVES = ["demarche", "demande", "adequation", "repartition", "lignes", "cours", "scenarios",
                "verifications", "limites"]

OUTILS: list[dict[str, Any]] = [
    {
        "type": "client",
        "name": "noter_profil",
        "description": ("Écrit une réponse de l'accueil dans le profil affiché à droite de l'écran. "
                        "Renvoie la question suivante et ses choix."),
        "parameters": {
            "type": "object",
            "required": ["champ", "valeur"],
            "properties": {
                "champ": {"type": "string", "description": "Champ du profil à remplir.", "enum": CHAMPS},
                "valeur": {"type": "string", "description": (
                    "Valeur exacte de la consigne. Liste : valeurs séparées par des virgules. "
                    "Nombre : les chiffres seuls, par exemple 3.")},
            },
        },
        "expects_response": True,
        "interruption_mode": "disable_during_tool",
        "response_timeout_secs": 20,
    },
    {
        "type": "client",
        "name": "lancer_analyse",
        "description": ("Envoie le profil validé au pipeline et attend le résultat (une à trois minutes). À appeler "
                        "UNE seule fois, puis attendre sa réponse sans le rappeler. Renvoie « Analyse terminée » "
                        "ou la phrase qui explique l'échec."),
        "parameters": {"type": "object", "required": [], "properties": {}},
        "expects_response": True,
        "interruption_mode": "disable_during_tool",
        # -1 : attendre la réponse du site sans limite (une analyse a pris 150 s ; 120 s la coupait).
        "response_timeout_secs": -1,
        "tool_call_sound": "typing",
        "tool_call_sound_behavior": "always",
    },
    {
        "type": "client",
        "name": "afficher_diapositive",
        "description": ("Affiche une diapositive au centre de l'écran et renvoie son texte, seule source des "
                        "chiffres que vous pouvez dire."),
        "parameters": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "description": "Diapositive à afficher, ou « alternative » pour une autre proposition.",
                       "enum": DIAPOSITIVES + ["alternative"]},
                "element": {"type": "string", "description": (
                    "Facultatif. Ce qu'il faut mettre en avant : le nom d'une part sur « repartition », le symbole "
                    "d'une ligne sur « lignes » ou « cours ». Seulement un élément cité à la fin du texte renvoyé.")},
            },
        },
        "expects_response": True,
        # La diapositive suivante ne s'affiche qu'une fois la phrase en cours terminée (l'écran ne prend pas
        # d'avance sur la voix), et la personne peut couper la parole pendant la présentation.
        "execution_mode": "post_tool_speech",
        "interruption_mode": "allow",
        "response_timeout_secs": 60,
    },
]


class ErreurElevenLabs(RuntimeError):
    pass


# ---------- Lecture de docs/agent-elevenlabs.md ----------

def lire_doc(texte: str) -> tuple[str, str]:
    """(premier message, consigne) tels qu'écrits dans le document."""
    m = re.search(r"^## Premier message\s*\n+((?:> .*\n?)+)", texte, re.MULTILINE)
    if not m:
        raise ValueError(f"Section « Premier message » introuvable dans {DOC.name}.")
    premier = " ".join(ligne[2:].strip() for ligne in m.group(1).splitlines() if ligne.startswith("> "))
    c = re.search(r"^## Consigne.*?\n```text\n(.*?)\n```", texte, re.MULTILINE | re.DOTALL)
    if not c:
        raise ValueError(f"Bloc ```text de la section « Consigne » introuvable dans {DOC.name}.")
    return premier, c.group(1).strip()


# ---------- Corps des requêtes ----------

def corps_agent(premier: str, consigne: str, ids_outils: list[str], voix: str | None, llm: str, tts: str) -> dict[str, Any]:
    tts_config: dict[str, Any] = {"model_id": tts}
    if voix:
        tts_config["voice_id"] = voix
    return {
        "name": "Eagle",
        "tags": ["eagle", "portefeuille-simule"],
        "conversation_config": {
            "agent": {
                "first_message": premier,
                "language": "fr",
                "prompt": {"prompt": consigne, "llm": llm, "tool_ids": ids_outils},
            },
            "tts": tts_config,
        },
    }


# ---------- HTTP ----------

Envoi = Callable[[str, dict[str, Any]], dict[str, Any]]


def envoyeur(cle: str) -> Envoi:
    def envoyer(chemin: str, corps: dict[str, Any]) -> dict[str, Any]:
        requete = urllib.request.Request(
            API + chemin, data=json.dumps(corps).encode("utf-8"), method="POST",
            headers={"xi-api-key": cle, "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(requete, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            raise ErreurElevenLabs(f"{chemin} : HTTP {e.code} : {detail}") from e
        except urllib.error.URLError as e:
            raise ErreurElevenLabs(f"{chemin} : réseau injoignable ({e.reason})") from e
    return envoyer


# ---------- web/.env.local ----------

def ecrire_env_web(agent_id: str, chemin: Path = ENV_WEB) -> None:
    """Remplace ou ajoute NEXT_PUBLIC_ELEVENLABS_AGENT_ID, sans toucher aux autres lignes."""
    lignes = chemin.read_text(encoding="utf-8").splitlines() if chemin.exists() else []
    lignes = [l for l in lignes if not l.strip().startswith(f"{VARIABLE_AGENT}=")]
    lignes.append(f"{VARIABLE_AGENT}={agent_id}")
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


# ---------- Programme ----------

def creer(envoyer: Envoi, premier: str, consigne: str, voix: str | None, llm: str, tts: str,
          dire: Callable[[str], None] = print) -> str:
    ids = []
    for outil in OUTILS:
        r = envoyer("/v1/convai/tools", {"tool_config": outil})
        if not r.get("id"):
            raise ErreurElevenLabs(f"Outil {outil['name']} : pas d'identifiant dans la réponse.")
        ids.append(r["id"])
        dire(f"Outil créé : {outil['name']} ({r['id']})")
    r = envoyer("/v1/convai/agents/create", corps_agent(premier, consigne, ids, voix, llm, tts))
    agent_id = r.get("agent_id")
    if not agent_id:
        raise ErreurElevenLabs("Agent : pas d'agent_id dans la réponse.")
    return agent_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Crée l'agent vocal Eagle sur ElevenLabs Agents.")
    ap.add_argument("--a-blanc", action="store_true", help="affiche les requêtes sans rien envoyer")
    args = ap.parse_args(argv)

    charger_env()
    premier, consigne = lire_doc(DOC.read_text(encoding="utf-8"))
    voix = os.environ.get("ELEVENLABS_VOICE_ID") or None
    llm = os.environ.get("ELEVENLABS_LLM") or LLM_DEFAUT
    tts = os.environ.get("ELEVENLABS_TTS_MODEL") or TTS_DEFAUT

    if args.a_blanc:
        for outil in OUTILS:
            print(f"POST {API}/v1/convai/tools")
            print(json.dumps({"tool_config": outil}, ensure_ascii=False, indent=2))
        print(f"POST {API}/v1/convai/agents/create")
        print(json.dumps(corps_agent(premier, consigne[:160] + " […]", ["<id outil 1>", "<id outil 2>", "<id outil 3>"],
                                     voix, llm, tts), ensure_ascii=False, indent=2))
        print("À blanc : rien n'a été envoyé.")
        return 0

    cle = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not cle:
        print("ELEVENLABS_API_KEY absente : ajoutez-la dans .env à la racine (voir .env.example). "
              "Secours : création à la main, docs/agent-elevenlabs.md.", file=sys.stderr)
        return 1
    try:
        agent_id = creer(envoyeur(cle), premier, consigne, voix, llm, tts)
    except ErreurElevenLabs as e:
        print(f"Échec : {e}\nSecours : création à la main, docs/agent-elevenlabs.md.", file=sys.stderr)
        return 1
    ecrire_env_web(agent_id)
    print(f"Agent Eagle créé : {agent_id}")
    print(f"Écrit dans {ENV_WEB.relative_to(RACINE)} ({VARIABLE_AGENT}). Relancez npm run dev dans web/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
