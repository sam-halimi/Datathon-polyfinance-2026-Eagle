"""Registre des chiffres d'une exécution du pipeline.

Règle du projet : aucun chiffre ne sort d'un modèle. Chaque appel à `tools/` passe par le
registre, qui garde la référence complète (outil, paramètres, période, formule, sources) et
donne à chaque chiffre affichable un repère court, par exemple `vol_tsla`. Les agents écrivent
`{vol_tsla}` dans leurs textes, jamais le nombre : l'interface remplace le repère par le
chiffre, qu'on peut toucher pour voir son calcul.

Les références enregistrées ont toutes une `valeur` numérique unique (format `Reference` de
web/lib/types.ts). Un outil qui renvoie plusieurs nombres (corrélations, statistiques d'un
portefeuille, parts du risque) donne un repère par nombre ; `details["cle"]` dit lequel.
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Repères acceptés par l'interface : minuscules, chiffres et soulignés.
MOTIF_REPERE = re.compile(r"\{([a-z0-9_]+)\}")
# Un nombre écrit en clair dans un texte d'agent : pourcentage ou décimal.
MOTIF_NOMBRE_EN_CLAIR = re.compile(r"[+−-]?\d+(?:[.,]\d+)?\s*%|\b\d+[.,]\d+\b")

COURT = {
    "volatilite": "vol",
    "pire_baisse": "baisse",
    "rendement_annualise": "rend",
    "rendement_en_cad": "rend_cad",
    "gain_de_rattrapage": "rattrapage",
    "sensibilite_taux": "sens",
    "pente_courbe": "pente",
}
UNITES_STATS = {
    "volatilite": "fraction annualisée",
    "rendement_annualise": "fraction par an (passé, ne prédit rien)",
    "pire_baisse": "fraction",
}
COURT_STATS = {"volatilite": "vol", "rendement_annualise": "rend", "pire_baisse": "baisse"}


def slug(texte: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(texte).lower()).strip("_")


class Registre:
    """Chiffres et appels d'une exécution. Un même appel n'est enregistré qu'une fois."""

    def __init__(self) -> None:
        self.chiffres: dict[str, dict[str, Any]] = {}
        self.appels: list[dict[str, Any]] = []
        self._portefeuilles: dict[tuple, str] = {}

    # --- noms -------------------------------------------------------------------

    def nom_portefeuille(self, poids: dict[str, float], nom: str | None = None) -> str:
        """Repère stable d'un jeu de poids : le nom donné, sinon p1, p2…"""
        cle = tuple(sorted((s, round(float(w), 10)) for s, w in poids.items() if w))
        if nom:
            self._portefeuilles[cle] = slug(nom)
        elif cle not in self._portefeuilles:
            self._portefeuilles[cle] = f"p{len(self._portefeuilles) + 1}"
        return self._portefeuilles[cle]

    # --- enregistrement ---------------------------------------------------------

    def _ajouter(self, repere: str, res: dict[str, Any], valeur: float, unite: str | None = None,
                 cle: Any = None, decrit: str = "") -> str:
        ref = {k: copy.deepcopy(res[k]) for k in ("outil", "parametres", "periode", "unite",
                                                  "formule", "sources", "details")}
        ref["valeur"] = float(valeur)
        if unite:
            ref["unite"] = unite
        if cle is not None:
            ref["details"] = {"cle": cle, **{k: v for k, v in ref["details"].items()
                                             if not isinstance(v, (dict, list)) or k == "origine"}}
        if decrit:
            ref["details"]["decrit"] = decrit
        # Même repère pour un autre appel (autre fenêtre, autres poids) : suffixe _2, _3…
        base, n = repere, 1
        while repere in self.chiffres and (self.chiffres[repere]["parametres"] != ref["parametres"]
                                           or self.chiffres[repere]["details"].get("cle") != ref["details"].get("cle")):
            n += 1
            repere = f"{base}_{n}"
        self.chiffres[repere] = ref
        return repere

    def enregistrer(self, res: dict[str, Any], portefeuille: str | None = None) -> list[str]:
        """Enregistre un résultat de tools/ et renvoie ses repères."""
        self.appels.append(res)
        outil, p = res["outil"], res["parametres"]
        if outil in COURT:
            suffixe = p.get("symbole") or p.get("pays") or ""
            if outil == "gain_de_rattrapage" and "origine" in res["details"]:
                suffixe = res["details"]["origine"]["parametres"].get("symbole", "")
            repere = f"{COURT[outil]}_{slug(suffixe)}".strip("_")
            if outil == "sensibilite_taux":
                repere += f"_{slug(p['serie_taux'])}"
            if p.get("devise") == "CAD" and outil not in ("rendement_en_cad",):
                repere += "_cad"
            return [self._ajouter(repere, res, res["valeur"])]
        if outil == "correlations":
            symboles = p["symboles"]
            reperes = []
            for i, a in enumerate(symboles):
                for b in symboles[i + 1:]:
                    reperes.append(self._ajouter(
                        f"corr_{slug(a)}_{slug(b)}", res, res["valeur"][a][b], cle=[a, b],
                        decrit=f"Corrélation des rendements quotidiens de {a} et {b}"))
            return reperes
        nom = portefeuille or self.nom_portefeuille(p["poids"])
        if outil == "stats_portefeuille":
            return [self._ajouter(f"{COURT_STATS[k]}_{nom}", res, v, unite=UNITES_STATS[k], cle=k,
                                  decrit=f"{k} du portefeuille simulé {nom}")
                    for k, v in res["valeur"].items()]
        if outil == "parts_du_risque":
            return [self._ajouter(f"part_{nom}_{slug(s)}", res, v, cle=s,
                                  decrit=f"Part de {s} dans le risque du portefeuille simulé {nom}")
                    for s, v in res["valeur"].items()]
        raise ValueError(f"Outil non pris en charge par le registre : {outil}")

    def enregistrer_decision(self, repere: str, valeur: float, outil: str, parametres: dict[str, Any],
                             formule: str, sources: list[str], decrit: str, unite: str = "fraction du capital") -> str:
        """Chiffre qui n'est pas une mesure : limite du profil ou poids choisi par le constructeur.

        Il garde aussi sa référence (qui l'a fixé et d'où il vient)."""
        self.chiffres[repere] = {
            "outil": outil, "parametres": parametres,
            "periode": {"debut": None, "fin": None, "observations": None},
            "valeur": float(valeur), "unite": unite, "formule": formule, "sources": sources,
            "details": {"decrit": decrit, "nature": "décision ou hypothèse, pas une mesure de marché"},
        }
        return repere

    # --- contrôle des textes ----------------------------------------------------

    def reperes_inconnus(self, texte: str) -> list[str]:
        return [r for r in MOTIF_REPERE.findall(texte) if r not in self.chiffres]

    @staticmethod
    def nombres_en_clair(texte: str) -> list[str]:
        """Pourcentages et décimaux écrits sans repère : un chiffre sorti d'un modèle."""
        return MOTIF_NOMBRE_EN_CLAIR.findall(MOTIF_REPERE.sub("", texte))

    def resume(self, reperes: list[str] | None = None) -> list[dict[str, Any]]:
        """Vue courte pour un agent : repère, ce qu'il mesure, valeur arrondie pour raisonner."""
        lignes = []
        for r in reperes if reperes is not None else list(self.chiffres):
            c = self.chiffres[r]
            v = c["valeur"]
            lisible = f"{v * 100:.1f} %" if c["unite"].startswith("fraction") else f"{v:.2f}"
            lignes.append({"repere": "{" + r + "}", "outil": c["outil"],
                           "parametres": {k: v for k, v in c["parametres"].items() if v is not None},
                           "decrit": c["details"].get("decrit", ""), "valeur_pour_raisonner": lisible})
        return lignes
