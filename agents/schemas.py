"""Sorties structurées demandées aux agents (Strands `structured_output_model`).

Les textes destinés à l'utilisateur ne contiennent aucun chiffre écrit en clair : seulement des
repères `{id}` renvoyant au registre. Le pipeline le vérifie.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Classe = Literal["equity", "etf_equity", "etf_bond", "etf_commodity", "crypto"]
Role = Literal["coeur", "defensif", "diversification", "theme", "crypto"]


class PositionDemandee(BaseModel):
    """Une position que l'utilisateur demande explicitement dans son message."""

    symbole: str | None = Field(None, description="Symbole de la table de l'univers, si un actif précis est nommé.")
    classe: Classe | None = Field(None, description="Classe d'actifs demandée si aucun symbole précis (ex. crypto).")
    role: Literal["theme"] | None = Field(None, description="« theme » si la position vise le thème (ex. « la techno »).")
    poids: float | None = Field(None, description=(
        "Part du capital demandée par l'utilisateur, en fraction (40 % -> 0.40), recopiée de son message. "
        "None s'il ne donne pas de part. Jamais un chiffre inventé."))


class Theme(BaseModel):
    nom: str
    symboles: list[str] = Field(description="Actions ou FNB d'actions de la table de l'univers, liés au thème.")
    justification: str = Field(description="Pourquoi ces symboles : secteur ou description dans la table. Sans chiffre.")


class Orchestration(BaseModel):
    resume_demande: str = Field(description="La demande de l'utilisateur en une phrase neutre, sans chiffre.")
    positions_demandees: list[PositionDemandee]
    theme: Theme | None = Field(None, description="Seulement si le profil a des centres d'intérêt. Sinon null.")
    candidats: list[str] = Field(description=(
        "8 à 15 symboles de l'univers à faire mesurer par le spécialiste : les actifs demandés, "
        "et de quoi construire des portefeuilles adaptés au profil (défensifs, larges, thème éventuel)."))
    consigne_specialiste: str = Field(description="Ce que le spécialiste marché et risque doit regarder en priorité.")
    resume: str = Field(description="Ce que l'orchestrateur a fait, en une phrase, sans chiffre.")


class AvisActif(BaseModel):
    symbole: str
    raison: str = Field(description="Raison courte avec les repères {id} des chiffres, jamais un nombre en clair.")


class NoteSpecialiste(BaseModel):
    constats: list[str] = Field(description="3 à 6 constats factuels, chacun avec ses repères {id}.")
    actifs_adaptes: list[AvisActif]
    actifs_a_limiter: list[AvisActif]
    resume: str = Field(description="Ce que le spécialiste a fait, en une phrase, sans chiffre.")


class LigneProposee(BaseModel):
    symbole: str
    poids_pourcent: int = Field(ge=1, le=100)
    role: Role
    raison: str = Field(description="Pourquoi cette ligne, avec repères {id} si un chiffre est utile. Sans nombre en clair.")


class PortefeuillePropose(BaseModel):
    id: Literal["a", "b", "c"]
    nom: str = Field(description="Nom court, par exemple « Prudent » ou « Équilibré ».")
    intention: str = Field(description="Une phrase : à quoi sert ce portefeuille simulé. Sans chiffre.")
    lignes: list[LigneProposee]


class Proposition(BaseModel):
    portefeuilles: list[PortefeuillePropose] = Field(min_length=2, max_length=3)
    resume: str = Field(description="Ce que le constructeur a fait, en une phrase, sans chiffre.")


class Niveau3(BaseModel):
    formule: str = Field(description="La formule en une ligne, en symboles (pas de valeur numérique).")
    lignes: list[str] = Field(description="2 à 5 lignes : les termes de la formule et le résultat, avec repères {id}.")


class Limites(BaseModel):
    faits: list[str] = Field(description="Ce que les données montrent, avec repères {id}.")
    hypotheses: list[str] = Field(description="Ce que le calcul suppose.")
    limites: list[str] = Field(description="Ce que le système ne sait pas ou ne vérifie pas.")


class Messages(BaseModel):
    """Ce que l'assistant dit en montrant chaque carte : une ou deux phrases, au plus un repère, sans émoji."""

    analyse: str
    repartition: str
    risque: str
    verifications: str
    pourquoi: str
    limites: str
    tout: str


class Explication(BaseModel):
    sujet: str = Field(description="La question à laquelle l'explication répond, sans chiffre.")
    niveau1: str = Field(description="Une phrase, avec au plus deux repères {id}.")
    niveau2: list[str] = Field(description="2 à 4 phrases : le pourquoi chiffré, avec repères {id}.")
    niveau3: Niveau3
    limites: Limites
    messages: Messages
    resume: str = Field(description="Ce que l'agent d'explication a fait, en une phrase, sans chiffre.")
