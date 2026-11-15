"""Sorties structurées des agents (Strands `structured_output_model`).

Les agents ne renvoient jamais un chiffre calculé : un texte cite un chiffre par son repère
`{identifiant}` du registre. Seuls deux nombres viennent d'un agent, et ils sont contrôlés :
- `poids_demande` : le pourcentage que l'utilisateur a écrit dans sa demande (vérifié dans le texte) ;
- `poids` d'une ligne de portefeuille : la décision du constructeur, vérifiée par la gouvernance.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["coeur", "defensif", "diversification", "theme", "crypto", "demande"]


# ---------- Orchestrateur ----------

class PositionDemandee(BaseModel):
    symbole: str = Field(description="Symbole de l'univers fourni, jamais un symbole de mémoire.")
    poids_demande: float | None = Field(
        default=None, description="Fraction du capital écrite par l'utilisateur (40 % -> 0.40). None s'il n'en dit pas.")
    citation: str = Field(description="Les mots exacts de la demande qui désignent cette position.")


class Theme(BaseModel):
    nom: str
    symboles: list[str] = Field(description="Actions ou FNB d'actions de l'univers liés au thème.")


class Cadrage(BaseModel):
    demande_resumee: str = Field(description="La demande en une phrase, sans chiffre.")
    positions_demandees: list[PositionDemandee] = Field(default_factory=list)
    classes_demandees: list[Literal["equity", "etf_equity", "etf_bond", "etf_commodity", "crypto"]] = Field(
        default_factory=list, description="Classes d'actifs que la demande vise en bloc (« la crypto »).")
    poids_total_demande: float | None = Field(
        default=None, description=("Part du capital que la demande veut placer sur l'ensemble des positions ou "
                                   "classes demandées, si l'utilisateur l'écrit (« 100 % » -> 1.0). Sinon None."))
    theme: Theme | None = Field(default=None, description="Seulement si le profil a des centres d'intérêt.")
    tension: str = Field(description="En quoi la demande s'écarte du profil, ou « aucune ». Sans chiffre.")
    consigne_marche: str = Field(description="Ce que le spécialiste marché et risque doit examiner.")
    consigne_macro: str = Field(description="Ce que le spécialiste macro et taux doit examiner.")
    consigne_esg: str = Field(description="Ce que le spécialiste ESG et qualité doit examiner.")


# ---------- Spécialistes ----------

class Constat(BaseModel):
    texte: str = Field(description="Une phrase. Chaque chiffre est un repère {identifiant} du registre.")
    symboles: list[str] = Field(default_factory=list)


class Candidat(BaseModel):
    symbole: str
    role: Role
    raison: str = Field(description="Sans chiffre écrit en dur ; repères {identifiant} permis.")


class AEcarter(BaseModel):
    symbole: str
    raison: str


class Analyse(BaseModel):
    constats: list[Constat]
    candidats: list[Candidat] = Field(default_factory=list)
    a_ecarter: list[AEcarter] = Field(default_factory=list)
    information_manquante: list[str] = Field(default_factory=list)


# ---------- Constructeur ----------

class Ligne(BaseModel):
    symbole: str
    poids: float = Field(description="Fraction du capital, positive. Les poids d'un portefeuille totalisent 1.")
    role: Role
    raison: str


class PortefeuilleBrut(BaseModel):
    nom: str = Field(description="Deux à quatre mots, sans chiffre.")
    idee: str = Field(description="L'idée en une phrase, sans chiffre.")
    lignes: list[Ligne]


class Propositions(BaseModel):
    portefeuilles: list[PortefeuilleBrut] = Field(min_length=1, max_length=3)


# ---------- Explication ----------

class Niveau3(BaseModel):
    formule: str = Field(description="La formule, en notation simple. Seul champ où des constantes sont permises.")
    lignes: list[str] = Field(description="Le calcul pas à pas, avec les repères {identifiant}.")


class Limites(BaseModel):
    faits: list[str]
    hypotheses: list[str]
    limites: list[str]


class Messages(BaseModel):
    analyse: str
    repartition: str
    risque: str
    verifications: str
    pourquoi: str
    limites: str
    tout: str


class Explication(BaseModel):
    sujet: str = Field(description="La question à laquelle l'explication répond, sans chiffre.")
    niveau1: str = Field(description="Une phrase.")
    niveau2: list[str] = Field(description="Le pourquoi chiffré : trois ou quatre phrases courtes.")
    niveau3: Niveau3
    reponse_a_la_demande: str = Field(description="Réponse franche à la demande de l'utilisateur, sans acquiescer.")
    portefeuilles: list[str] = Field(description="Une phrase par portefeuille simulé, dans l'ordre reçu.")
    limites: Limites
    messages: Messages = Field(description="Ce que dit l'assistant en affichant chaque carte. Une ou deux phrases.")
