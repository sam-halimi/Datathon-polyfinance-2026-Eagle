"""Fonctions de calcul d'AlphaForge AI.

Chaque mesure renvoie un dictionnaire avec sa référence d'appel (voir trace.py) :
outil, paramètres, période couverte, valeur brute, unité, formule, sources.
"""

from tools.calendriers import aligner_calendriers, convertir_cad
from tools.donnees import charger_prix, univers
from tools.gouvernance import verifier_contraintes
from tools.macro import pente_courbe, sensibilite_taux, serie_macro
from tools.mesures import (
    gain_de_rattrapage,
    pire_baisse,
    rendement_annualise,
    rendement_en_cad,
    rendements,
    volatilite,
)
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille

__all__ = [
    "aligner_calendriers",
    "charger_prix",
    "convertir_cad",
    "correlations",
    "gain_de_rattrapage",
    "parts_du_risque",
    "pente_courbe",
    "pire_baisse",
    "rendement_annualise",
    "rendement_en_cad",
    "rendements",
    "sensibilite_taux",
    "serie_macro",
    "stats_portefeuille",
    "univers",
    "verifier_contraintes",
    "volatilite",
]
