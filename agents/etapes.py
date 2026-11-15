"""Les agents du pipeline : consignes système et formats de sortie structurés.

Chaque agent a un seul domaine (pas de débat). Ce qu'il renvoie est validé par le code :
symboles présents dans l'univers sourcé, aucun chiffre en clair dans les textes.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from agents.modele import creer_agent

REGLES_COMMUNES = """Tu fais partie d'AlphaForge AI, un assistant qui construit des portefeuilles simulés : aucune transaction réelle.
Règles absolues :
- Vocabulaire : « portefeuille simulé », « assistant ». N'écris jamais « conseil », « conseiller », « recommander », « recommandation ».
- Aucun chiffre en clair dans tes textes : ni pourcentage, ni montant, ni année, ni date, ni nombre écrit en lettres pour remplacer un chiffre. Pour citer une valeur, écris uniquement sa clé entre accolades, par exemple {baisse_tsla}. Tu n'utilises que des clés reçues des outils ou listées dans la consigne. Tu peux compter des éléments en lettres (« trois lignes »).
- Les limites du profil sont des hypothèses de conception de l'équipe : jamais « réglementaire » ni « légal ». Pas de rapport calculé de tête (« huit fois plus », « la moitié ») : seulement les clés.
- Pas de prédiction : les données passées décrivent, elles ne promettent rien. Pas de « va monter », « rapportera ».
- Symboles : seulement ceux de l'univers fourni, jamais de mémoire.
- Tu distingues les faits (mesurés par les outils), les hypothèses (choix de conception, limites du profil) et les limites (ce que les données ne disent pas). Pas de justification inventée.
- Langue : français, phrases courtes."""


def _json(objet: Any) -> str:
    return json.dumps(objet, ensure_ascii=False, indent=1, default=str)


# --- Orchestrateur ----------------------------------------------------------------------------

class CibleDemande(BaseModel):
    symboles: list[str] = Field(description="Symboles de l'univers visés par la demande. Vide si la demande ne vise aucun actif précis.")
    poids_demande: float | None = Field(description="Part du capital demandée, en fraction (0.4 pour 40 %), seulement si l'utilisateur l'a dite explicitement. Sinon null.")
    extrait: str = Field(description="Les mots de l'utilisateur, recopiés, sans chiffre (remplace le chiffre par « … »).")


class Theme(BaseModel):
    nom: str
    symboles: list[str] = Field(description="Actions ou FNB d'actions de l'univers liés au thème (colonne secteur ou nom).")
    justification: str = Field(description="Pourquoi ces symboles : quelle colonne de l'univers les relie au thème.")


class Orchestration(BaseModel):
    resume_demande: str = Field(description="La demande en une phrase, sans chiffre.")
    cibles: list[CibleDemande]
    theme: Theme | None = Field(description="Thème tiré des centres d'intérêt, ou null s'il n'y en a pas.")
    consignes_specialistes: str = Field(description="Ce que les spécialistes doivent examiner en priorité, sans chiffre.")


CONSIGNE_ORCHESTRATEUR = REGLES_COMMUNES + """

Tu es l'orchestrateur. Tu lis le profil validé et la demande de l'utilisateur. Tu ne construis pas de portefeuille.
1. Appelle univers_actifs pour connaître les actifs autorisés.
2. Traduis la demande en cibles : quels symboles de l'univers elle vise, et la part du capital demandée seulement si l'utilisateur l'a dite (« tout » ou « cent pour cent » = 1.0). Une demande sur une catégorie (« la crypto », « la techno ») vise les symboles de l'univers de cette catégorie, d'après les colonnes classe et secteur. Fais une cible par catégorie si l'utilisateur en nomme plusieurs avec une seule part : une seule cible qui les regroupe.
3. Si le profil a des centres d'intérêt, tire-en un thème : actions et FNB d'actions de l'univers seulement (classes equity et etf_equity), jamais de crypto ni d'obligation. Pas de centre d'intérêt : theme = null.
4. Dis aux spécialistes ce qu'ils doivent examiner (la tension éventuelle entre la demande et le profil)."""


def orchestrer(profil: dict[str, Any], contraintes: dict[str, Any], demande: str, outils: list) -> Orchestration:
    agent = creer_agent("orchestrateur", CONSIGNE_ORCHESTRATEUR, outils)
    resultat = agent(f"Profil validé :\n{_json(profil)}\n\nLimites du profil :\n{_json(contraintes)}\n\n"
                     f"Demande de l'utilisateur : « {demande} »", structured_output_model=Orchestration)
    return resultat.structured_output


# --- Spécialiste marché et risque --------------------------------------------------------------

class Constat(BaseModel):
    texte: str = Field(description="Un fait mesuré, avec ses chiffres sous forme de clés {cle}.")
    symboles: list[str]


class NotesSpecialiste(BaseModel):
    constats: list[Constat]
    a_privilegier: list[str] = Field(description="Symboles qui servent le profil, d'après les mesures.")
    a_limiter: list[str] = Field(description="Symboles à limiter ou écarter pour ce profil, d'après les mesures.")


CONSIGNE_MARCHE = REGLES_COMMUNES + """

Tu es le spécialiste marché et risque. Ton seul domaine : volatilité, pire baisse, gain de rattrapage, corrélations.
1. Mesure avec mesurer_actifs les actifs visés par la demande, puis les candidats qui conviennent au profil (au moins une obligation, un FNB d'actions large, et l'or ; ajoute le thème s'il y en a un).
2. Si un thème ou plusieurs actifs risqués sont en jeu, mesure leurs corrélations avec correlations_actifs.
3. Rends des constats courts. Chaque constat cite ses chiffres par leurs clés, par exemple « {baisse_tsla} de pire baisse ». Pas de conclusion sur l'avenir.
Rappel du contexte des données : sur la fenêtre étudiée, les obligations ont aussi baissé ; ne présume pas qu'elles protègent, mesure-les."""


def analyser_marche(profil: dict[str, Any], contraintes: dict[str, Any], orchestration: Orchestration,
                    outils: list) -> NotesSpecialiste:
    agent = creer_agent("marche_et_risque", CONSIGNE_MARCHE, outils)
    resultat = agent(f"Profil :\n{_json(profil)}\n\nLimites :\n{_json(contraintes['limites'])}\n\n"
                     f"Consigne de l'orchestrateur :\n{_json(orchestration.model_dump())}",
                     structured_output_model=NotesSpecialiste)
    return resultat.structured_output


# --- Constructeur ------------------------------------------------------------------------------

class LigneProposee(BaseModel):
    symbole: str
    poids: float = Field(description="Fraction du capital (0.05 pour 5 %).")
    role: str = Field(description="Le rôle de la ligne en quelques mots, sans chiffre, par exemple « L'amortisseur ».")
    au_titre_du_theme: bool = Field(description="Vrai seulement si la ligne est là pour le thème du profil.")


class PortefeuillePropose(BaseModel):
    id: str = Field(description="A, B ou C.")
    nom: str = Field(description="Nom court, sans chiffre.")
    intention: str = Field(description="L'idée du portefeuille en une phrase, sans chiffre.")
    lignes: list[LigneProposee]


class Propositions(BaseModel):
    portefeuilles: list[PortefeuillePropose] = Field(description="Deux ou trois portefeuilles simulés différents.")


CONSIGNE_CONSTRUCTEUR = REGLES_COMMUNES + """

Tu es le constructeur. Tu proposes deux ou trois portefeuilles simulés différents (identifiants A, B, C), chacun conforme au profil.
- Les poids sont tes décisions : des fractions dont la somme vaut exactement 1, positives, sur des symboles de l'univers.
- Respecte chaque limite du profil : plafond par titre (une action ou une crypto seule), crypto au total, part risquée (actions, FNB d'actions et crypto ensemble), plafond par secteur (actions détenues en direct), thème, nombre minimal de lignes. Les seuils de volatilité et de pire baisse s'appliquent au portefeuille entier : vérifie-les avec tester_portefeuille avant de répondre.
- Une demande qui dépasse le profil n'est pas exécutée telle quelle : reste sous les limites. Si le profil le permet, garde une exposition plafonnée à ce que l'utilisateur demande plutôt que de tout refuser, mais au moins un portefeuille s'en passe, pour montrer l'option qui suit le profil sans concession.
- Les portefeuilles diffèrent vraiment (pas trois variations de poids sur les mêmes lignes).
- Marque au_titre_du_theme seulement pour les lignes du thème.
- Les noms, intentions et rôles ne contiennent aucun chiffre.
Si la gouvernance a rejeté une proposition, corrige exactement les contrôles en échec et garde le reste."""


def construire(profil: dict[str, Any], contraintes: dict[str, Any], seuils_risque: dict[str, float],
               orchestration: Orchestration, notes: NotesSpecialiste, outils: list,
               rejets: dict[str, list[str]] | None = None, precedentes: Propositions | None = None) -> Propositions:
    agent = creer_agent("constructeur", CONSIGNE_CONSTRUCTEUR, outils)
    message = (f"Profil :\n{_json(profil)}\n\nLimites du profil (fractions du capital) :\n{_json(contraintes['limites'])}\n"
               f"Exclusions : {_json(contraintes['exclusions'])}\n"
               f"Seuils de risque du portefeuille entier : {_json(seuils_risque)}\n\n"
               f"Orchestrateur :\n{_json(orchestration.model_dump())}\n\n"
               f"Spécialistes :\n{_json(notes.model_dump())}")
    if rejets:
        message += (f"\n\nTes propositions précédentes :\n{_json(precedentes.model_dump() if precedentes else None)}"
                    f"\n\nLa gouvernance a rejeté ces portefeuilles, contrôles en échec :\n{_json(rejets)}\n"
                    "Renvoie toutes les propositions, corrigées.")
    return agent(message, structured_output_model=Propositions).structured_output


# --- Explication ------------------------------------------------------------------------------

class Niveau3(BaseModel):
    formule: str = Field(description="La formule utilisée, en symboles (seul endroit où des chiffres de formule sont permis).")
    lignes: list[str] = Field(description="Le calcul appliqué au portefeuille, ligne par ligne, avec les clés.")


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
    niveau2: list[str] = Field(description="Le pourquoi chiffré : deux à quatre phrases avec des clés.")
    niveau3: Niveau3
    faits: list[str] = Field(description="Faits mesurés, avec clés.")
    hypotheses: list[str] = Field(description="Hypothèses : limites du profil, poids constants, calculs en CAD…")
    limites: list[str] = Field(description="Ce que les données ne disent pas, propres à ce cas.")
    messages: Messages = Field(description="Ce que dit l'assistant à l'ouverture de chaque carte, une phrase courte chacune.")


CONSIGNE_EXPLICATION = REGLES_COMMUNES + """

Tu es l'agent d'explication. Tu expliques les portefeuilles simulés retenus à l'utilisateur, à trois niveaux :
- niveau 1 : une phrase ;
- niveau 2 : le pourquoi chiffré, deux à quatre phrases avec des clés ;
- niveau 3 : la formule et le calcul appliqué au portefeuille, avec des clés.
Le sujet est le point qui compte le plus pour cet utilisateur : en priorité la tension entre sa demande et son profil, s'il y en a une. Ne lui donne pas raison quand sa demande contredit son profil, et ne le sermonne pas : montre les chiffres.
Tu n'utilises que les clés de la liste fournie, et seulement pour ce qu'elles décrivent. Un nom de clé n'apparaît jamais hors des accolades : écris « la pire baisse de TSLA, {baisse_tsla} », jamais « baisse_tsla : … ».
Chaque fait vient d'un contrôle ou d'un chiffre listé. N'affirme rien sur l'histoire d'un actif ou d'un marché qu'aucun chiffre listé ne montre.
Les hypothèses et limites « déjà affichées » sont vraies et affichées telles quelles : ne les répète pas et ne les contredis jamais. Ajoute seulement ce qui est propre à ce cas.
Au niveau trois, reprends la formule de l'outil qui a produit les chiffres (liste « formules »)."""


def expliquer(contexte: dict[str, Any], retour: list[str] | None = None) -> Explication:
    agent = creer_agent("explication", CONSIGNE_EXPLICATION)
    message = f"Contexte :\n{_json(contexte)}"
    if retour:
        message += ("\n\nTa réponse précédente a été refusée par le contrôle des chiffres :\n- " + "\n- ".join(retour)
                    + "\nRécris-la : chaque valeur passe par une clé de la liste, aucun chiffre en clair.")
    return agent(message, structured_output_model=Explication).structured_output
