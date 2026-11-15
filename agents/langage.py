"""Registre de l'explication selon `connaissance_niveau` (1 à 5), et lexique écrit par le code.

- Niveaux 1 et 2 (`courant`) : mots de tous les jours. Tout terme technique employé est défini
  dans le lexique ; les définitions viennent d'ici, pas d'un modèle. Le jargon de spécialiste
  (covariance, écart-type…) est refusé.
- Niveau 3 (`usuel`) : termes usuels (volatilité, diversification), sans définitions.
- Niveaux 4 et 5 (`professionnel`) : vocabulaire de gestion de portefeuille, sans définitions ;
  l'explication doit employer les termes attendus.
Vouvoiement et ton professionnel à tous les niveaux : le tutoiement est refusé.
"""

from __future__ import annotations

import re
from typing import Any

from agents.adequation import normaliser
from agents.profil import Profil

NIVEAU_PAR_CONNAISSANCE = {"débutant": 2, "intermédiaire": 3, "avancé": 4}

REGISTRES: dict[str, dict[str, Any]] = {
    "courant": {"niveaux": (1, 2), "description": (
        "Mots de tous les jours, phrases courtes. Un terme technique n'est employé que s'il est indispensable ; "
        "il est alors défini dans le lexique.")},
    "usuel": {"niveaux": (3,), "description": (
        "Termes usuels de l'épargne (volatilité, diversification, pire baisse, obligation), sans définition.")},
    "professionnel": {"niveaux": (4, 5), "description": (
        "Vocabulaire de gestion de portefeuille (contribution au risque, corrélation, duration, perte maximale, "
        "sensibilité aux taux), précis et sans définition.")},
}

CONSIGNES = {
    "courant": ("Registre courant : écris pour une personne qui découvre l'épargne. Mots de tous les jours, une idée "
                "par phrase. Évite le jargon ; si un terme technique est indispensable (volatilité, obligation, "
                "FNB…), garde-le simple : il sera défini dans un lexique à part. N'emploie jamais covariance, "
                "écart-type, duration, bêta, ratio de Sharpe."),
    "usuel": ("Registre usuel : la personne connaît les termes courants de l'épargne (volatilité, diversification, "
              "pire baisse, obligation, FNB). Emploie-les sans les définir. Évite le jargon de spécialiste."),
    "professionnel": ("Registre professionnel : la personne connaît la gestion de portefeuille. Emploie le vocabulaire "
                      "du métier, sans définitions : contribution au risque, corrélation, perte maximale, et, quand "
                      "des obligations sont détenues, duration et sensibilité aux taux. Sois précis et dense."),
}
TON = ("Vouvoie toujours la personne (« vous », jamais « tu »). Ton professionnel et posé, à tous les niveaux.")

# Lexique écrit par l'équipe : chaque terme technique et sa définition en mots courants.
LEXIQUE: dict[str, str] = {
    "volatilité": "À quel point la valeur monte et descend d'un jour à l'autre. Plus elle est forte, plus le chemin est cahoteux.",
    "pire baisse": "La plus grosse chute de valeur observée, d'un sommet au creux qui a suivi, sur la période étudiée.",
    "perte maximale": "La plus grosse chute de valeur observée, d'un sommet au creux qui a suivi.",
    "diversification": "Répartir l'argent sur des placements qui ne bougent pas tous en même temps, pour amortir les chocs.",
    "corrélation": "Mesure entre −1 et 1 de la façon dont deux placements bougent ensemble. Proche de 1 : ils montent et baissent en même temps.",
    "obligation": "Un prêt à un État ou à une entreprise, qui verse des intérêts. Son prix baisse quand les taux montent.",
    "fnb": "Fonds négocié en bourse : un panier de nombreux titres qu'on achète en une seule fois, comme une action.",
    "part du risque": "La part des mouvements du portefeuille qui vient d'une ligne. Elle peut être bien plus grande que son poids en argent.",
    "contribution au risque": "La part des mouvements du portefeuille qui vient d'une ligne.",
    "sensibilité aux taux": "De combien le prix d'un placement a varié quand les taux d'intérêt ont bougé d'un point.",
    "duration": "Durée moyenne d'attente des paiements d'une obligation ; plus elle est longue, plus son prix réagit aux taux.",
    "cryptoactif": "Monnaie numérique comme le bitcoin, sans État ni banque derrière, au prix très changeant.",
    "gain de rattrapage": "Ce qu'il faut regagner après une chute pour revenir au point de départ : après une baisse de moitié, il faut doubler.",
    "taux de change": "Le prix d'une monnaie dans une autre, par exemple combien de dollars canadiens vaut un dollar américain.",
    "rééquilibrage": "Remettre régulièrement chaque ligne à son poids prévu, en vendant ce qui a monté et en achetant ce qui a baissé.",
    "plafond": "Le poids maximal permis pour une ligne ou un groupe de lignes, fixé selon votre profil.",
}
# Variantes reconnues dans le texte (forme normalisée sans accents) -> entrée du lexique.
VARIANTES = {
    "volatilite": "volatilité", "volatil": "volatilité", "pire baisse": "pire baisse", "perte maximale": "perte maximale",
    "diversification": "diversification", "diversifie": "diversification", "correlation": "corrélation",
    "correle": "corrélation", "obligation": "obligation", "obligataire": "obligation", "fnb": "fnb",
    "part du risque": "part du risque", "parts du risque": "part du risque",
    "contribution au risque": "contribution au risque", "sensibilite aux taux": "sensibilité aux taux",
    "duration": "duration", "crypto": "cryptoactif", "gain de rattrapage": "gain de rattrapage",
    "taux de change": "taux de change", "reequilibr": "rééquilibrage", "plafond": "plafond",
}
JARGON_SPECIALISTE = ("covariance", "ecart type", "beta", "ratio de sharpe", "drawdown", "value at risk", "alpha")
TERMES_PROFESSIONNELS = ("contribution au risque", "correlation", "perte maximale")
TERMES_TAUX = ("duration", "sensibilite aux taux")
TUTOIEMENT = re.compile(r"\b(tu|toi|ton|tes|ta)\b", re.IGNORECASE)


def niveau_effectif(profil: Profil) -> int:
    return profil.connaissance_niveau or NIVEAU_PAR_CONNAISSANCE[profil.connaissance]


def registre(niveau: int) -> dict[str, Any]:
    nom = next(n for n, r in REGISTRES.items() if niveau in r["niveaux"])
    return {"niveau": niveau, "nom": nom, "description": REGISTRES[nom]["description"]}


def consigne(niveau: int) -> str:
    return CONSIGNES[registre(niveau)["nom"]] + " " + TON


def _present(texte_norm: str, motif: str) -> bool:
    return re.search(rf"\b{re.escape(motif)}", texte_norm) is not None


def termes_employes(textes: list[str]) -> list[str]:
    """Entrées du lexique employées dans les textes, dans l'ordre du lexique."""
    t = normaliser(" ".join(textes))
    trouves = {terme for variante, terme in VARIANTES.items() if _present(t, variante)}
    return [terme for terme in LEXIQUE if terme in trouves]


def lexique(niveau: int, textes: list[str]) -> list[dict[str, str]]:
    """Niveaux 1 et 2 : définition de chaque terme technique employé. Vide aux niveaux 3 à 5."""
    if registre(niveau)["nom"] != "courant":
        return []
    return [{"terme": "FNB" if t == "fnb" else t, "definition": LEXIQUE[t]} for t in termes_employes(textes)]


def problemes(niveau: int, textes: list[str], obligations: bool) -> list[str]:
    """Écarts au registre : tutoiement, jargon non défini (niveaux 1-2), termes attendus absents (4-5)."""
    erreurs = []
    brut = " ".join(textes)
    if TUTOIEMENT.search(brut):
        erreurs.append(f"tutoiement (« {TUTOIEMENT.search(brut).group(0)} ») : vouvoyer la personne")
    t = normaliser(brut)
    nom = registre(niveau)["nom"]
    if nom == "courant":
        jargon = [j for j in JARGON_SPECIALISTE if _present(t, j)]
        if jargon:
            erreurs.append(f"jargon de spécialiste pour un niveau {niveau} : {', '.join(jargon)} ; écrire en mots courants")
    if nom == "professionnel":
        attendus = list(TERMES_PROFESSIONNELS) + (list(TERMES_TAUX) if obligations else [])
        manquants = [x for x in attendus if not _present(t, x)]
        if manquants:
            erreurs.append(f"registre professionnel (niveau {niveau}) : employer aussi « {'», «'.join(manquants)} »")
    return erreurs
