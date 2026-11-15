"""Outils donnés aux agents : les fonctions de `tools/`, branchées sur le registre.

Chaque outil appelle la vraie fonction de `tools/`, inscrit le résultat au registre et renvoie
à l'agent le repère à citer et la valeur formatée. L'agent ne reçoit jamais de valeur brute à
recopier : il cite `{repère}`.

Les calculs déterministes que le pipeline fait de toute façon (fiche de chaque actif candidat,
statistiques des portefeuilles) sont aussi ici, pour passer par le même registre.
"""

from __future__ import annotations

from typing import Any, Callable

from agents.registre import Registre, identifiant
from tools import macro, mesures, portefeuille
from tools.donnees import univers, verifier_symboles


def _symbole(s: str) -> str:
    s = s.strip().upper()
    verifier_symboles([s])
    return s


# ---------- Calculs déterministes ----------

def fiche_actif(reg: Registre, symbole: str, par: str = "spécialiste marché et risque") -> dict[str, str]:
    """Volatilité et pire baisse d'un actif (devise de cotation, comme docs/contexte.md)."""
    ids = {}
    vid = identifiant("volatilite", symbole)
    if vid not in reg.chiffres:
        reg.inscrire(mesures.volatilite(symbole), vid, f"Volatilité annualisée de {symbole}", par=par)
    ids["volatilite"] = vid
    pid = identifiant("pire_baisse", symbole)
    if pid not in reg.chiffres:
        res = mesures.pire_baisse(symbole)
        d = res["details"]
        reg.inscrire(res, pid, f"Pire baisse de {symbole} (du {d['date_pic']} au {d['date_creux']})", par=par)
    ids["pire_baisse"] = pid
    return ids


def rattrapage(reg: Registre, symbole: str, par: str = "spécialiste marché et risque") -> str:
    rid = identifiant("rattrapage", symbole)
    if rid not in reg.chiffres:
        res = mesures.gain_de_rattrapage(mesures.pire_baisse(symbole))
        reg.inscrire(res, rid, f"Gain nécessaire pour effacer la pire baisse de {symbole}", par=par)
    return rid


def correlation(reg: Registre, a: str, b: str, par: str = "spécialiste marché et risque") -> str:
    cid = identifiant("correlation", a, b)
    if cid not in reg.chiffres:
        res = portefeuille.correlations([a, b])
        reg.inscrire(res, cid, f"Corrélation des rendements quotidiens de {a} et {b}",
                     valeur=res["valeur"][a][b], cle=f"{a}/{b}", fmt="decimal", par=par)
    return cid


def stats_et_parts(reg: Registre, ptf_id: str, poids: dict[str, float], devise: str,
                   par: str = "constructeur") -> dict[str, Any]:
    """Volatilité, pire baisse et parts du risque d'un portefeuille simulé, inscrites au registre."""
    stats = portefeuille.stats_portefeuille(poids, devise=devise)
    d = stats["details"]["pire_baisse"]
    ids = {
        "volatilite": reg.inscrire(stats, identifiant("volatilite_ptf", ptf_id),
                                   f"Volatilité du portefeuille simulé {ptf_id}",
                                   valeur=stats["valeur"]["volatilite"], cle="volatilite",
                                   unite=f"fraction annualisée, {'en CAD' if devise == 'CAD' else 'en devise de cotation'}",
                                   par=par),
        "pire_baisse": reg.inscrire(stats, identifiant("pire_baisse_ptf", ptf_id),
                                    f"Pire baisse du portefeuille simulé {ptf_id} (du {d['date_pic']} au {d['date_creux']})",
                                    valeur=stats["valeur"]["pire_baisse"], cle="pire_baisse",
                                    unite="fraction", par=par),
        "effet_diversification": reg.inscrire(
            stats, identifiant("diversification_ptf", ptf_id),
            f"Volatilité retirée par la diversification dans le portefeuille {ptf_id}",
            valeur=stats["details"]["effet_diversification"], cle="effet_diversification",
            unite="fraction annualisée", par=par),
    }
    parts = portefeuille.parts_du_risque(poids, devise=devise)
    ids["parts_du_risque"] = {
        s: reg.inscrire(parts, identifiant("part_risque", ptf_id, s),
                        f"Part de {s} dans le risque du portefeuille {ptf_id}",
                        valeur=p, cle=s, par=par)
        for s, p in parts["valeur"].items()
    }
    return ids


# ---------- Outils Strands ----------

def outils_marche(reg: Registre, par: str = "spécialiste marché et risque") -> list[Callable[..., Any]]:
    from strands import tool

    @tool
    def risque_actif(symbole: str) -> str:
        """Volatilité annualisée et pire baisse historiques d'un actif de l'univers (tools/mesures.py).

        Args:
            symbole: symbole exact de l'univers, par exemple TSLA ou XIU.TO.
        """
        try:
            ids = fiche_actif(reg, _symbole(symbole), par)
            return reg.catalogue(list(ids.values()))
        except Exception as e:  # l'agent lit l'erreur et corrige
            return f"Erreur : {e}"

    @tool
    def gain_de_rattrapage(symbole: str) -> str:
        """Gain nécessaire pour revenir au sommet après la pire baisse d'un actif : perte / (1 - perte).

        Args:
            symbole: symbole exact de l'univers.
        """
        try:
            s = _symbole(symbole)
            fiche_actif(reg, s, par)
            return reg.ligne(rattrapage(reg, s, par))
        except Exception as e:
            return f"Erreur : {e}"

    @tool
    def correlation_entre(symbole_a: str, symbole_b: str) -> str:
        """Corrélation des rendements quotidiens de deux actifs, sur leurs jours communs (tools/portefeuille.py).

        Args:
            symbole_a: premier symbole de l'univers.
            symbole_b: second symbole de l'univers.
        """
        try:
            return reg.ligne(correlation(reg, _symbole(symbole_a), _symbole(symbole_b), par))
        except Exception as e:
            return f"Erreur : {e}"

    return [risque_actif, gain_de_rattrapage, correlation_entre]


def outils_macro(reg: Registre, par: str = "spécialiste macro et taux") -> list[Callable[..., Any]]:
    from strands import tool

    @tool
    def sensibilite_aux_taux(symbole: str, serie_taux: str = "DGS10") -> str:
        """Variation de prix d'un actif par point de hausse d'un taux, par régression (tools/macro.py).

        Args:
            symbole: symbole de l'univers, surtout les FNB obligataires (AGG, TLT, XBB.TO, ZST.TO).
            serie_taux: DGS10 (10 ans américain) ou BD.CDN.10YR.DQ.YLD (10 ans canadien).
        """
        try:
            s = _symbole(symbole)
            sid = identifiant("sensibilite", s, serie_taux)
            if sid not in reg.chiffres:
                res = macro.sensibilite_taux(s, serie_taux)
                reg.inscrire(res, sid, f"Variation de prix de {s} par point de hausse de {serie_taux}",
                             fmt="pourcent", par=par)
                reg.inscrire(res, sid + "_r2", f"Part des mouvements de {s} expliquée par {serie_taux} (R²)",
                             valeur=res["details"]["r2"], cle="r2", fmt="decimal", par=par)
            return reg.catalogue([sid, sid + "_r2"])
        except Exception as e:
            return f"Erreur : {e}"

    @tool
    def pente_de_la_courbe(pays: str) -> str:
        """Pente de la courbe des taux (10 ans moins 2 ans) et jours de courbe inversée (tools/macro.py).

        Args:
            pays: « États-Unis » ou « Canada ».
        """
        try:
            res = macro.pente_courbe(pays)
            nom = res["parametres"]["pays"]
            base = identifiant("pente", nom)
            if base not in reg.chiffres:
                d = res["details"]
                reg.inscrire(res, base, f"Pente 10 ans moins 2 ans, {nom}, au {d['date_derniere']}", par=par)
                reg.inscrire(res, base + "_minimum", f"Pente la plus basse, {nom}, le {d['date_minimum']}",
                             valeur=d["minimum"], cle="minimum", par=par)
                reg.inscrire(res, base + "_jours_negatifs", f"Jours de courbe inversée, {nom}",
                             valeur=d["jours_negatifs"], cle="jours_negatifs", fmt="entier", unite="jours", par=par)
                reg.inscrire(res, base + "_jours", f"Jours observés, {nom}",
                             valeur=d["jours"], cle="jours", fmt="entier", unite="jours", par=par)
            return reg.catalogue([base, base + "_minimum", base + "_jours_negatifs", base + "_jours"])
        except Exception as e:
            return f"Erreur : {e}"

    return [sensibilite_aux_taux, pente_de_la_courbe]


def table_univers() -> str:
    """L'univers sourcé, une ligne par actif, pour les consignes des agents."""
    t = univers()
    return "\n".join(f"{s} | {r['name']} | {r['asset_class']} | {r['currency']} | {r['sector']}"
                     for s, r in t.iterrows())
