"""Un modèle Bedrock qui résiste aux pannes passagères.

Constat du 16 novembre 2026 : entre 0 h 27 et 0 h 35 UTC, Bedrock a répondu
« serviceUnavailableException » au milieu des réponses (ConverseStream). Le pipeline
s'arrêtait net et le site affichait « erreur 500 », y compris après « Relancer ».

Trois protections, dans cet ordre :
1. réponses non diffusées (Converse) : une panne survient avant toute sortie, jamais au milieu ;
2. reprises de botocore, avec attente croissante ;
3. si le modèle reste indisponible, le suivant de la chaîne répond (même famille de modèles),
   puis on refait un tour après une pause.

Les identifiants de la chaîne viennent de la liste des profils d'inférence du compte
(`bedrock list-inference-profiles`, relevée le 16 novembre 2026), pas de mémoire. Le modèle qui a
réellement répondu est noté : `modeles_utilises()` alimente `meta.modele` de la sortie.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, AsyncGenerator

journal = logging.getLogger("eagle.modele")

# Premier de la chaîne : le défaut de Strands. Les suivants : même modèle par le profil
# américain, puis la version précédente par le profil mondial.
CHAINE_PAR_DEFAUT = (
    "global.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-sonnet-4-6",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
TOURS = 3                      # tours complets de la chaîne avant d'abandonner
PAUSES = (2.0, 6.0, 12.0)      # secondes d'attente après chaque tour infructueux
# Erreurs de Bedrock qui disparaissent d'elles-mêmes : on attend ou on change de modèle.
PASSAGERES = ("serviceunavailable", "throttl", "modelstreamerror", "internalserver", "modeltimeout",
              "modelnotready", "too many requests", "unable to process your request", "read timeout",
              "connection reset", "endpointconnection")

_utilises: list[str] = []


def chaine_de_modeles() -> list[str]:
    """`BEDROCK_MODEL_ID` en tête s'il est réglé, puis la chaîne par défaut, sans doublon."""
    regle = os.environ.get("BEDROCK_MODEL_ID", "").strip()
    return list(dict.fromkeys(([regle] if regle else []) + list(CHAINE_PAR_DEFAUT)))


def est_passagere(erreur: BaseException) -> bool:
    """Vrai pour une indisponibilité ou une limitation de débit, y compris enveloppée par Strands."""
    vus: set[int] = set()
    e: BaseException | None = erreur
    while e is not None and id(e) not in vus:
        vus.add(id(e))
        texte = f"{type(e).__name__} {e}".lower().replace("_", "")
        if any(m in texte for m in PASSAGERES):
            return True
        e = e.__cause__ or e.__context__
    return False


def modeles_utilises() -> list[str]:
    """Modèles qui ont réellement répondu depuis `oublier_modeles()`, dans l'ordre, sans doublon."""
    return list(dict.fromkeys(_utilises))


def oublier_modeles() -> None:
    _utilises.clear()


def construire_modele() -> Any:
    """Le modèle des agents : chaîne de secours, réponses non diffusées, reprises de botocore."""
    from botocore.config import Config
    from strands.models import BedrockModel

    class ModeleResistant(BedrockModel):
        def __init__(self, identifiants: list[str]) -> None:
            super().__init__(model_id=identifiants[0], streaming=False, boto_client_config=Config(
                retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=300, connect_timeout=10))
            self.identifiants = identifiants

        async def stream(self, *args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
            derniere: BaseException | None = None
            for tour in range(TOURS):
                for identifiant in self.identifiants:
                    self.update_config(model_id=identifiant)
                    emis = False
                    try:
                        async for evenement in super().stream(*args, **kwargs):
                            emis = True
                            yield evenement
                        _utilises.append(identifiant)
                        return
                    except Exception as e:  # noqa: BLE001 - on trie plus bas ce qui est passager
                        # Une réponse déjà commencée ne se rejoue pas : on laisse remonter.
                        if emis or not est_passagere(e):
                            raise
                        derniere = e
                        journal.warning("Bedrock indisponible pour %s (%s), tour %d : modèle suivant",
                                        identifiant, type(e).__name__, tour + 1)
                await asyncio.sleep(PAUSES[min(tour, len(PAUSES) - 1)])
            assert derniere is not None
            raise derniere

    return ModeleResistant(chaine_de_modeles())
