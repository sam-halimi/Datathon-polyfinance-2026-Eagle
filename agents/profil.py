"""Profil d'investisseur (sortie de l'accueil) et contraintes qui en découlent.

Le profil est structuré et validé : l'accueil pose 6 à 8 questions, affiche un récapitulatif,
et ne passe le profil au pipeline qu'une fois validé par l'utilisateur.

`contraintes(profil)` traduit le profil en limites chiffrées pour le constructeur et la
gouvernance. Ces limites sont des **hypothèses de conception** fixées par l'équipe, pas des
chiffres de marché : elles sont affichées comme telles dans la carte « vérifications ».

Usage : `python -m agents.profil` affiche le schéma JSON du profil.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Tolerance = Literal["faible", "modéré", "élevé"]
Connaissance = Literal["débutant", "intermédiaire", "avancé"]
Objectif = Literal["préservation du capital", "revenu", "équilibre", "croissance"]
Devise = Literal["CAD", "USD"]

PLAFOND_THEME_DEFAUT = 0.10
"""Inclinaison thématique maximale (part du capital), sur actions et FNB seulement."""

HORIZON_COURT_ANS = 5
"""En dessous de cet horizon, la part risquée et la crypto sont resserrées."""

# Hypothèses de conception, par tolérance au risque. Fractions du capital.
# - max_titre_individuel : une seule action (les FNB larges ne sont pas concernés)
# - max_crypto : BTC-USD et ETH-USD ensemble
# - max_part_risquee : actions, FNB d'actions et crypto ensemble
# - max_un_secteur : actions individuelles d'un même secteur (colonne `sector` de assets_universe.csv)
# - min_lignes : nombre minimal de lignes du portefeuille simulé
LIMITES_PAR_TOLERANCE: dict[str, dict[str, float | int]] = {
    "faible": {"max_titre_individuel": 0.05, "max_crypto": 0.00, "max_part_risquee": 0.40,
               "max_un_secteur": 0.15, "min_lignes": 5},
    "modéré": {"max_titre_individuel": 0.10, "max_crypto": 0.05, "max_part_risquee": 0.70,
               "max_un_secteur": 0.20, "min_lignes": 5},
    "élevé": {"max_titre_individuel": 0.15, "max_crypto": 0.10, "max_part_risquee": 0.90,
              "max_un_secteur": 0.30, "min_lignes": 5},
}
LIMITES_HORIZON_COURT = {"max_crypto": 0.00, "max_part_risquee": 0.50}

# Niveau d'explication ouvert par défaut (décision 5 de docs/contexte.md).
NIVEAU_EXPLICATION_PAR_DEFAUT = {"débutant": 1, "intermédiaire": 2, "avancé": 3}

# Échelle de connaissance de l'accueil Eagle (curseur de 1 à 5) et sa traduction en trois niveaux.
CONNAISSANCE_PAR_NIVEAU: dict[int, str] = {1: "débutant", 2: "débutant", 3: "intermédiaire", 4: "avancé", 5: "avancé"}


def _liste_propre(valeurs: list[str]) -> list[str]:
    vus, propres = set(), []
    for v in valeurs:
        v = v.strip()
        if v and v.lower() not in vus:
            vus.add(v.lower())
            propres.append(v)
    return propres


class Profil(BaseModel):
    """Profil structuré d'un investisseur. Tous les champs viennent de l'accueil."""

    model_config = ConfigDict(extra="forbid")

    horizon_annees: int = Field(ge=1, le=50, description=(
        "Horizon en années. Si l'utilisateur donne une fourchette (« 3 à 5 ans »), l'accueil retient "
        "la borne basse, plus prudente, et le dit dans le récapitulatif."))
    objectif: Objectif
    tolerance_risque: Tolerance = Field(description=(
        "Si l'utilisateur hésite entre deux niveaux, l'accueil retient le plus bas et le dit dans le récapitulatif."))
    connaissance: Connaissance
    connaissance_niveau: int | None = Field(default=None, ge=1, le=5, description=(
        "Curseur de 1 à 5 de l'accueil Eagle. S'il est donné sans `connaissance`, celle-ci en découle "
        "(1-2 débutant, 3 intermédiaire, 4-5 avancé). Il règle le vocabulaire de l'explication."))
    preferences: list[str] = Field(default_factory=list, description="Ex. : ESG, dividendes, Canada.")
    exclusions: list[str] = Field(default_factory=list, description=(
        "Secteurs, activités ou symboles à écarter. Ex. : énergies fossiles, TSLA."))
    centres_interet: list[str] = Field(default_factory=list, description=(
        "Source du thème éventuel : une inclinaison plafonnée sur actions et FNB, jamais une obligation."))
    capital_fictif: float = Field(gt=0, description="Montant simulé, dans `devise`. Aucune transaction réelle.")
    devise: Devise = "CAD"

    _nettoyer = field_validator("preferences", "exclusions", "centres_interet")(_liste_propre)

    @model_validator(mode="before")
    @classmethod
    def _connaissance_depuis_niveau(cls, valeurs: Any) -> Any:
        if isinstance(valeurs, dict) and not valeurs.get("connaissance"):
            niveau = valeurs.get("connaissance_niveau")
            if isinstance(niveau, int) and niveau in CONNAISSANCE_PAR_NIVEAU:
                valeurs = {**valeurs, "connaissance": CONNAISSANCE_PAR_NIVEAU[niveau]}
        return valeurs


def contraintes(profil: Profil, plafond_theme: float = PLAFOND_THEME_DEFAUT) -> dict[str, Any]:
    """Limites appliquées par le constructeur et vérifiées par la gouvernance.

    Renvoie les limites et, pour chacune, d'où elle vient (tolérance, horizon, paramètre),
    pour que la carte « vérifications » puisse l'expliquer.
    """
    if not 0 <= plafond_theme <= 1:
        raise ValueError("plafond_theme est une fraction entre 0 et 1")
    limites = dict(LIMITES_PAR_TOLERANCE[profil.tolerance_risque])
    origine = {nom: f"tolérance au risque « {profil.tolerance_risque} »" for nom in limites}
    if profil.horizon_annees < HORIZON_COURT_ANS:
        for nom, plafond in LIMITES_HORIZON_COURT.items():
            if plafond < limites[nom]:
                limites[nom] = plafond
                origine[nom] = f"horizon de {profil.horizon_annees} an(s), moins de {HORIZON_COURT_ANS} ans"
    limites["plafond_theme"] = plafond_theme if profil.centres_interet else 0.0
    origine["plafond_theme"] = ("paramètre plafond_theme, sur actions et FNB seulement" if profil.centres_interet
                                else "aucun centre d'intérêt déclaré")
    return {
        "limites": limites,
        "origine": origine,
        "exclusions": profil.exclusions,
        "niveau_explication_par_defaut": NIVEAU_EXPLICATION_PAR_DEFAUT[profil.connaissance],
        "nature": "hypothèses de conception de l'équipe, pas des chiffres de marché",
    }


if __name__ == "__main__":
    print(json.dumps(Profil.model_json_schema(), ensure_ascii=False, indent=2))
