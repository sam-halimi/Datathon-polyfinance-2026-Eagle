"""Fonctions de calcul d'AlphaForge AI.

Chaque mesure renvoie un dictionnaire avec sa référence d'appel (voir trace.py) :
outil, paramètres, période couverte, valeur brute, unité, formule, sources.
"""

from tools.calendriers import aligner_calendriers, convertir_cad
from tools.donnees import charger_prix, univers
from tools.mesures import pire_baisse, rendement_annualise, rendements, volatilite

__all__ = [
    "aligner_calendriers",
    "charger_prix",
    "convertir_cad",
    "pire_baisse",
    "rendement_annualise",
    "rendements",
    "univers",
    "volatilite",
]
