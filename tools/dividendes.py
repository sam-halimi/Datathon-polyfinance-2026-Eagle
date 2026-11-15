"""Rendement en dividendes d'un actif, à partir des dividendes enregistrés par date ex.

    rendement_dividende(symbole, debut=None, fin=None)

= somme des dividendes dont la date ex tombe dans les 12 derniers mois de la fenêtre
  / dernier cours de clôture de la fenêtre.

- Dividendes : `data/corporate_actions.csv` (univers de départ) et `data/base/actions_etendues.csv`
  (univers étendu), en devise de cotation par action.
- Cours : colonne `close` (ajustée des fractionnements seulement). `adj_close` intègre déjà les
  dividendes : le prendre au dénominateur compterait le dividende deux fois.
- Un actif couvert par le fichier mais sans dividende enregistré vaut 0, et la référence le dit
  (`details.statut` = « aucun dividende enregistré »). Une crypto ou l'or valent donc 0.
- Un actif absent des deux fichiers vaut « information manquante » (`valeur` None), jamais 0.

C'est un rendement passé, observé sur 12 mois : il ne promet aucun dividende futur.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tools.donnees import DATA, charger_prix, verifier_symboles
from tools.trace import resultat

FICHIERS_ACTIONS = {"data/corporate_actions.csv": DATA / "corporate_actions.csv",
                    "data/base/actions_etendues.csv": DATA / "base" / "actions_etendues.csv"}
FICHIERS_PRIX = {"data/corporate_actions.csv": "data/prices_daily.csv",
                 "data/base/actions_etendues.csv": "data/base/prix_etendus.csv"}
INCONNU = "information manquante"


def _symboles_couverts(fichier: str) -> set[str]:
    """Symboles dont le fichier d'actions fait partie du même téléchargement que les prix."""
    prix = DATA.parent / FICHIERS_PRIX[fichier]
    if not prix.is_file():
        return set()
    return set(pd.read_csv(prix, usecols=["ticker"])["ticker"].unique())


def _dividendes(symbole: str) -> tuple[pd.DataFrame | None, str | None]:
    """(dividendes du symbole, fichier source) ; (None, None) si aucun fichier ne couvre le symbole."""
    for nom, chemin in FICHIERS_ACTIONS.items():
        if not chemin.is_file() or symbole not in _symboles_couverts(nom):
            continue
        a = pd.read_csv(chemin, parse_dates=["ex_date"])
        return a[(a["ticker"] == symbole) & (a["action"] == "dividend")], nom
    return None, None


def rendement_dividende(symbole: str, debut: str | None = None, fin: str | None = None) -> dict[str, Any]:
    """Dividendes des 12 derniers mois de la fenêtre / dernier cours. Valeur None si non couvert."""
    verifier_symboles([symbole])
    div, fichier = _dividendes(symbole)
    prix = charger_prix(symbole, debut, fin, colonne="close")[symbole].dropna()
    parametres = {"symbole": symbole, "debut": debut, "fin": fin}
    formule = ("Σ dividendes dont la date ex est dans les 365 jours précédant le dernier cours de la fenêtre "
               "/ dernier cours de clôture (close)")
    if div is None or prix.empty:
        return resultat(
            outil="rendement_dividende", parametres=parametres,
            periode={"debut": None, "fin": None, "observations": 0}, valeur=None,
            unite="fraction du cours, sur 12 mois", formule=formule, sources=list(FICHIERS_ACTIONS),
            details={"statut": INCONNU, "raison": (
                f"{symbole} n'est couvert par aucun fichier de dividendes ({', '.join(FICHIERS_ACTIONS)})"
                if div is None else f"aucun cours pour {symbole} sur la fenêtre")})
    date_fin = prix.index.max()
    date_debut = date_fin - pd.Timedelta(days=365)
    retenus = div[(div["ex_date"] > date_debut) & (div["ex_date"] <= date_fin)]
    total = float(retenus["value"].sum())
    dernier = float(prix.iloc[-1])
    statut = "dividendes enregistrés" if len(retenus) else (
        "aucun dividende enregistré sur les 12 derniers mois" if len(div) else "aucun dividende enregistré")
    return resultat(
        outil="rendement_dividende", parametres=parametres,
        periode={"debut": date_debut.date().isoformat(), "fin": date_fin.date().isoformat(),
                 "observations": int(len(retenus))},
        valeur=total / dernier, unite="fraction du cours, sur 12 mois, en devise de cotation",
        formule=formule, sources=[f"{fichier} (dividend)", f"{FICHIERS_PRIX[fichier]} (close)"],
        details={"statut": statut, "dividendes_12_mois": total, "dernier_cours": dernier,
                 "date_dernier_cours": date_fin.date().isoformat(),
                 "dates_ex": [d.date().isoformat() for d in retenus["ex_date"]],
                 "avertissement": "Rendement passé sur 12 mois : il ne promet aucun dividende futur."})


def rendement_dividende_portefeuille(poids: dict[str, float], debut: str | None = None,
                                     fin: str | None = None) -> dict[str, Any]:
    """Rendement en dividendes pondéré : Σ wᵢ × rendement_dividende(i), sur les lignes couvertes.

    `details.part_inconnue` : part du capital dont le rendement est « information manquante ».
    """
    lignes, total, inconnu, fin_max = {}, 0.0, 0.0, None
    for s, w in poids.items():
        r = rendement_dividende(s, debut, fin)
        lignes[s] = {"poids": w, "rendement": r["valeur"], "statut": r["details"]["statut"]}
        if r["valeur"] is None:
            inconnu += w
        else:
            total += w * r["valeur"]
            fin_max = max(fin_max or r["periode"]["fin"], r["periode"]["fin"])
    return resultat(
        outil="rendement_dividende_portefeuille", parametres={"poids": dict(poids), "debut": debut, "fin": fin},
        periode={"debut": None, "fin": fin_max, "observations": len(poids)},
        valeur=total, unite="fraction du capital, sur 12 mois",
        formule="Σ poids × rendement_dividende de chaque ligne ; une ligne sans donnée ne compte pas (part_inconnue)",
        sources=[*FICHIERS_ACTIONS, "tools/dividendes.py (rendement_dividende)"],
        details={"lignes": lignes, "part_inconnue": inconnu,
                 "avertissement": "Rendement passé sur 12 mois, en devise de cotation de chaque ligne."})
