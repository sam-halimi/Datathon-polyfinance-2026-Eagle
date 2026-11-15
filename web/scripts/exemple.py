"""Génère web/data/exemple.json, les données d'exemple de l'interface.

Usage, depuis la racine du dépôt : python web/scripts/exemple.py

L'interface affiche ce fichier tant que le pipeline (branche agents) ne lui
envoie pas sa vraie sortie. Règle du projet : aucun chiffre écrit à la main.

- Les mesures par actif viennent d'un vrai appel à tools/mesures.py ; le
  dictionnaire de référence (outil, paramètres, période, formule, sources) est
  recopié tel quel.
- Les mesures de portefeuille (volatilité, parts du risque, corrélations,
  sensibilité aux taux) n'ont pas encore leur fonction dans tools/ (branche
  outils). Elles sont recopiées de analyses/exemples_explications.py, déjà
  arrondies, et marquées comme telles. À remplacer par stats_portefeuille et
  parts_du_risque dès qu'elles existent.

Les textes contiennent des repères {id} : l'interface les remplace par le
chiffre correspondant de la table « chiffres », qu'on peut toucher pour voir
sa référence d'appel.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from tools.donnees import univers, verifier_symboles  # noqa: E402
from tools.mesures import pire_baisse, volatilite  # noqa: E402

SORTIE = RACINE / "web" / "data" / "exemple.json"


def depuis_analyses(valeur: float, unite: str, formule: str, parametres: dict, decrit: str) -> dict:
    """Chiffre recopié de analyses/exemples_explications.py (valeur déjà arrondie)."""
    return {
        "outil": "analyses/exemples_explications.py",
        "parametres": parametres,
        "periode": {"debut": "2021-11-12", "fin": "2026-11-12", "observations": None},
        "valeur": valeur,
        "unite": unite,
        "formule": formule,
        "sources": ["prices_daily.csv (adj_close)", "docs/contexte.md"],
        "details": {
            "decrit": decrit,
            "en_attente": "Valeur arrondie recopiée de l'analyse. Sera produite par tools/ "
            "(stats_portefeuille, parts_du_risque, correlations) quand la branche outils sera fusionnée.",
        },
    }


def main() -> None:
    verifier_symboles(["SPY", "AGG", "BTC-USD", "NVDA"])
    noms = univers()["name"].to_dict()

    chiffres: dict[str, dict] = {}
    for sym, cle in [("SPY", "spy"), ("AGG", "agg"), ("BTC-USD", "btc"), ("NVDA", "nvda")]:
        chiffres[f"vol_{cle}"] = volatilite(sym)
        chiffres[f"baisse_{cle}"] = pire_baisse(sym)

    poids = {"SPY": 0.6, "AGG": 0.3, "BTC-USD": 0.1}
    p_param = {"poids": poids, "devise": "cotation"}
    chiffres["vol_ptf"] = depuis_analyses(
        0.139, "fraction annualisée, en USD", "√(wᵀ Σ w), Σ = covariance annualisée (× 252)",
        p_param, "Volatilité du portefeuille simulé")
    for sym, cle, part in [("SPY", "spy", 0.699), ("AGG", "agg", 0.044), ("BTC-USD", "btc", 0.257)]:
        chiffres[f"part_{cle}"] = depuis_analyses(
            part, "fraction du risque total", "wᵢ × (Σ w)ᵢ / (wᵀ Σ w)", {**p_param, "actif": sym},
            f"Part du risque de {sym}")
    for paire, cle, c in [(("SPY", "AGG"), "corr_spy_agg", 0.22), (("SPY", "BTC-USD"), "corr_spy_btc", 0.42),
                          (("AGG", "BTC-USD"), "corr_agg_btc", 0.09)]:
        chiffres[cle] = depuis_analyses(
            c, "coefficient de corrélation", "corrélation des rendements quotidiens, jours communs",
            {"actifs": list(paire)}, f"Corrélation {paire[0]} et {paire[1]}")
    chiffres["sens_agg"] = depuis_analyses(
        -0.059, "fraction par point de taux", "pente de la régression rendement ~ variation du taux 10 ans",
        {"symbole": "AGG", "serie_taux": "DGS10"}, "Sensibilité d'AGG au taux 10 ans américain (R² 0,91)")

    lignes = [
        {"symbole": s, "nom": noms[s], "poids": w,
         "classe": {"SPY": "Actions américaines (FNB)", "AGG": "Obligations (FNB)", "BTC-USD": "Cryptoactif"}[s],
         "role": {"SPY": "Le moteur de croissance", "AGG": "L'amortisseur", "BTC-USD": "La part audacieuse, plafonnée"}[s]}
        for s, w in poids.items()
    ]

    sortie = {
        "exemple": True,
        "note": "Données d'exemple générées par web/scripts/exemple.py, en attendant la sortie du pipeline.",
        "profil": {
            "prenom": "Amira",
            "horizon_annees": "15 ans et plus",
            "objectif": "Faire croître mon capital à long terme",
            "tolerance_risque": "élevé",
            "connaissance": "intermédiaire",
            "preferences": ["Garder une diversification"],
            "exclusions": [],
            "centres_interet": ["IA et techno", "Cryptoactifs"],
            "capital_fictif": 50000,
            "devise": "CAD",
            "demande": "Tout mettre en crypto et en techno",
        },
        "etapes": [
            {"agent": "Orchestrateur", "fait": "Lit votre profil et fixe les plafonds : crypto 10 %, thème 10 %."},
            {"agent": "Marché et risque", "fait": "Mesure la volatilité et la pire baisse de chaque actif."},
            {"agent": "Macro et taux", "fait": "Mesure la sensibilité des obligations aux taux."},
            {"agent": "ESG et qualité", "fait": "Aucune exclusion demandée : rien à écarter."},
            {"agent": "Constructeur", "fait": "Assemble un portefeuille simulé de 3 actifs."},
            {"agent": "Gouvernance", "fait": "Vérifie le portefeuille contre votre profil."},
        ],
        "portefeuilles": [
            {
                "id": "A",
                "nom": "Croissance diversifiée",
                "lignes": lignes,
                "volatilite": "vol_ptf",
                "parts_du_risque": {"SPY": "part_spy", "AGG": "part_agg", "BTC-USD": "part_btc"},
                "pires_baisses": {"SPY": "baisse_spy", "AGG": "baisse_agg", "BTC-USD": "baisse_btc"},
            }
        ],
        "gouvernance": {
            "essai": 1,
            "essais_max": 2,
            "statut": "accepte",
            "controles": [
                {"statut": "alerte", "titre": "Votre demande : tout en crypto et en techno",
                 "detail": "Pas retenue telle quelle. Pire baisse sur 5 ans : Bitcoin {baisse_btc}, NVIDIA {baisse_nvda}."},
                {"statut": "ok", "titre": "Crypto plafonnée à 10 %", "detail": "Bitcoin : 10 % du capital."},
                {"statut": "ok", "titre": "Diversification", "detail": "3 actifs, 3 classes différentes."},
                {"statut": "ok", "titre": "Aucun dérivé ni option", "detail": "Seulement des FNB et un cryptoactif."},
                {"statut": "ok", "titre": "Chaque chiffre a sa source", "detail": "Touchez un chiffre pour voir son calcul."},
                {"statut": "ok", "titre": "Simulation seulement", "detail": "Aucune transaction réelle."},
            ],
        },
        "explication": {
            "niveau_par_defaut": 2,
            "sujet": "Pourquoi le Bitcoin est limité à 10 %",
            "niveau1": "Le Bitcoin ne pèse que 10 % du capital, mais déjà {part_btc} du risque.",
            "niveau2": [
                "Volatilité du Bitcoin : {vol_btc}. Celle de SPY : {vol_spy}.",
                "Sa pire baisse sur 5 ans : {baisse_btc}.",
                "Corrélation avec SPY : {corr_spy_btc}. Il ne protège pas quand les actions baissent.",
            ],
            "niveau3": {
                "formule": "part du risque de i = wᵢ × (Σw)ᵢ ÷ σ²",
                "lignes": [
                    "w = poids : SPY 60 %, AGG 30 %, Bitcoin 10 %.",
                    "Σ = covariance des rendements quotidiens, annualisée.",
                    "σ = volatilité du portefeuille : {vol_ptf}.",
                    "Résultat : SPY {part_spy}, AGG {part_agg}, Bitcoin {part_btc}.",
                ],
            },
        },
        "limites": {
            "faits": [
                "Données du 12 novembre 2021 au 12 novembre 2026.",
                "Obligations AGG, pire baisse : {baisse_agg}. En 2022, actions et obligations ont baissé ensemble.",
                "Quand le taux 10 ans américain monte d'un point, AGG varie d'environ {sens_agg}.",
            ],
            "hypotheses": [
                "Le passé décrit le risque. Il ne promet rien pour l'avenir.",
                "Calculs en dollars américains, sans conversion en CAD.",
            ],
            "limites": [
                "Composition des FNB absente : la techno contenue dans SPY n'est pas mesurée.",
                "Univers choisi en 2026 : biais du survivant.",
            ],
        },
        "messages": {
            "analyse": "Je lance l'analyse. Six étapes, chacune visible.",
            "repartition": "Voici un portefeuille simulé. Trois actifs, pas un seul pari.",
            "risque": "Le Bitcoin pèse peu en argent, mais beaucoup en risque.",
            "verifications": "J'ai vérifié la proposition contre votre profil. Une alerte.",
            "pourquoi": "Pourquoi pas tout en crypto ? Voici l'explication.",
            "limites": "Ce que je sais, ce que je suppose, et ce que je ne sais pas.",
            "tout": "Voici tout, sur un seul écran. Touchez une carte pour l'ouvrir.",
        },
        "chiffres": chiffres,
    }
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Écrit : {SORTIE.relative_to(RACINE)} ({len(chiffres)} chiffres)")


if __name__ == "__main__":
    main()
