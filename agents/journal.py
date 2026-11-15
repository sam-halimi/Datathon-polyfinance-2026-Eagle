"""Registre des chiffres du pipeline : le mécanisme d'explicabilité.

Règle du projet : aucun chiffre ne sort d'un modèle. Les agents n'écrivent donc jamais
un nombre. Ils appellent un outil de `tools/` par l'intermédiaire du journal, qui garde
la référence d'appel complète sous un identifiant (`vol_tsla`, `pb_ptf_a`…). Leurs textes
contiennent des repères `{identifiant}` que l'interface remplace par le chiffre, touchable
pour voir son calcul.

`Journal.verifier_texte` refuse un texte qui contient un chiffre écrit en dur ou un repère
inconnu. C'est un contrôle mécanique, pas une consigne laissée à la bonne volonté du modèle.
"""

from __future__ import annotations

import re
from typing import Any, Callable

import tools
from tools import dividendes, esg, repartition

REPERE = re.compile(r"\{([a-z0-9_]+)\}")
CHIFFRE = re.compile(r"\d")

OUTILS: dict[str, Callable[..., dict[str, Any]]] = {
    "volatilite": tools.volatilite,
    "pire_baisse": tools.pire_baisse,
    "rendement_annualise": tools.rendement_annualise,
    "rendement_en_cad": tools.rendement_en_cad,
    "gain_de_rattrapage": tools.gain_de_rattrapage,
    "correlations": tools.correlations,
    "stats_portefeuille": tools.stats_portefeuille,
    "parts_du_risque": tools.parts_du_risque,
    "sensibilite_taux": tools.sensibilite_taux,
    "pente_courbe": tools.pente_courbe,
    "exposition_fnb": esg.exposition_fnb,
    "exposition_transparente": esg.exposition_transparente,
    "exposition_titre": esg.exposition_titre,
    "rendement_dividende": dividendes.rendement_dividende,
    "rendement_dividende_portefeuille": dividendes.rendement_dividende_portefeuille,
    "part_par_marche": repartition.part_par_marche,
    "part_fnb": repartition.part_fnb,
    "part_societes_etablies": repartition.part_societes_etablies,
}


def cle(*morceaux: Any) -> str:
    """Identifiant lisible : cle("vol", "BTC-USD") -> "vol_btc_usd"."""
    brut = "_".join(str(m) for m in morceaux if m not in (None, ""))
    return re.sub(r"[^a-z0-9]+", "_", brut.lower()).strip("_")


def _scalaire(res: dict[str, Any], valeur: float, champ: str | None, **parametres_en_plus: Any) -> dict[str, Any]:
    """Une entrée de la table « chiffres » : la référence d'appel avec une valeur scalaire."""
    ref = {k: res[k] for k in ("outil", "parametres", "periode", "unite", "formule", "sources", "details")}
    ref = {**ref, "valeur": float(valeur)}
    if champ:
        ref["champ"] = champ
    if parametres_en_plus:
        ref["parametres"] = {**ref["parametres"], **parametres_en_plus}
    return ref


class Journal:
    """Table des chiffres et trace des actions des agents."""

    def __init__(self) -> None:
        self.chiffres: dict[str, dict[str, Any]] = {}
        self.appels: list[dict[str, Any]] = []  # chaque appel d'outil, dans l'ordre, avec l'agent
        self.etapes: list[dict[str, str]] = []  # ce que chaque agent a fait, pour la barre d'étapes
        self.agent_courant = "pipeline"

    # --- enregistrement ---------------------------------------------------

    def _noter(self, ident: str, ref: dict[str, Any]) -> str:
        self.chiffres[ident] = ref
        self.appels.append({"agent": self.agent_courant, "id": ident, "outil": ref["outil"],
                            "parametres": ref["parametres"]})
        return ident

    def mesurer(self, outil: str, ident: str | None = None, **parametres: Any) -> dict[str, str]:
        """Appelle un outil de tools/ et enregistre chaque valeur scalaire qu'il produit.

        Renvoie {champ: identifiant}. Un outil à valeur unique donne {"valeur": id}.
        """
        res = OUTILS[outil](**parametres)
        base = ident or cle(outil, *[v for v in parametres.values() if isinstance(v, str)])
        valeur = res["valeur"]
        if outil == "correlations":
            a, b = parametres["symboles"][:2]
            return {"valeur": self._noter(base, _scalaire(res, valeur[a][b], None, symboles=[a, b]))}
        if isinstance(valeur, dict):
            return {champ: self._noter(cle(base, champ), _scalaire(res, v, champ)) for champ, v in valeur.items()}
        return {"valeur": self._noter(base, _scalaire(res, valeur, None))}

    def enregistrer(self, ident: str, ref: dict[str, Any]) -> str:
        """Enregistre une référence déjà calculée (par exemple une limite du profil)."""
        return self._noter(ident, ref)

    def etape(self, agent: str, fait: str) -> None:
        self.etapes.append({"agent": agent, "fait": fait})

    # --- lecture pour les agents ------------------------------------------

    def apercu(self, ident: str) -> str:
        """Ce que voit un modèle : l'identifiant, ce qui est mesuré et la valeur arrondie."""
        r = self.chiffres[ident]
        v = r["valeur"]
        lisible = f"{v * 100:.1f} %" if r["unite"].startswith("fraction") else f"{v:.2f}"
        quoi = r["outil"] + (f".{r['champ']}" if r.get("champ") else "")
        params = {k: v for k, v in r["parametres"].items() if v is not None and k != "poids"}
        return f"{{{ident}}} = {lisible} ({quoi} {params})"

    def catalogue(self, idents: list[str] | None = None) -> str:
        return "\n".join(self.apercu(i) for i in (idents or self.chiffres))

    # --- contrôle des textes ----------------------------------------------

    def verifier_texte(self, texte: str) -> list[str]:
        """Erreurs d'un texte écrit par un modèle : chiffre en dur, repère inconnu."""
        erreurs = []
        faux = [m for m in re.findall(r"\{([^{}]*)\}", texte) if not REPERE.fullmatch("{" + m + "}")]
        if faux:
            erreurs.append(f"accolades autour de « {', '.join(faux[:3])} », qui n'est pas un repère : écrire le symbole "
                           "sans accolades, et n'entourer que des identifiants de la liste des chiffres")
        sans_reperes = REPERE.sub("", texte)
        if CHIFFRE.search(sans_reperes):
            erreurs.append(f"chiffre écrit en dur dans « {texte} » : utiliser un repère {{id}}")
        for ident in REPERE.findall(texte):
            if ident not in self.chiffres:
                erreurs.append(f"repère inconnu {{{ident}}} dans « {texte} »")
        return erreurs

    def reperes_utilises(self, *textes: str) -> set[str]:
        return {i for t in textes for i in REPERE.findall(t)}
