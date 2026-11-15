"""Agent de gouvernance : vérifie chaque portefeuille simulé contre le profil.

Pas de modèle de langage ici : un contrôle se calcule, il ne se discute pas.

Une seule table de limites (décision du plan du dimanche) : les plafonds de poids viennent de
`agents.profil.contraintes(profil)` et sont passés à `tools.gouvernance.verifier_contraintes`
par son paramètre `seuils`. L'outil ne garde que ses propres seuils de volatilité et de pire
baisse, qui n'existent pas dans le profil.

Contrôles ajoutés ici, que l'outil ne fait pas :
- `diversification` : nombre minimal de lignes et part risquée maximale du profil ;
- `demande_hors_profil` : la demande de l'utilisateur comparée aux limites, chiffrée par tools/ ;
- `exclusion_esg` et `transparence_fnb` (spécialiste ESG) quand le profil a des exclusions.
"""

from __future__ import annotations

from typing import Any

from agents.journal import Journal, cle
from agents.profil import Profil, contraintes
from tools.donnees import FICHIER_UNIVERS, univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE, tolerance_normalisee, verifier_contraintes

ESSAIS_MAX = 2
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")

TITRES = {
    "somme_des_poids": "Le capital est réparti en entier",
    "poids_positifs": "Ni vente à découvert ni levier",
    "univers_source": "Actifs de l'univers sourcé",
    "instruments_autorises": "Aucun dérivé ni option",
    "exclusion": "Exclusion demandée",
    "plafond_par_titre": "Plafond par titre",
    "plafond_crypto": "Plafond crypto",
    "plafond_par_secteur": "Plafond par secteur",
    "plafond_theme": "Thème plafonné",
    "theme_actions_et_fnb": "Thème sur actions et FNB",
    "volatilite_max": "Volatilité historique",
    "pire_baisse_max": "Pire baisse historique",
    "risque_historique": "Risque historique",
    "tolerance_risque": "Tolérance retenue",
    "diversification": "Diversification",
    "demande_hors_profil": "Votre demande",
    "exclusion_esg": "Exclusion ESG",
    "transparence_fnb": "Contenu des FNB",
    "simulation": "Simulation seulement",
}
STATUT_INTERFACE = {"conforme": "ok", "à signaler": "alerte", "information manquante": "alerte",
                    "non conforme": "echec"}


def limites_du_profil(profil: Profil) -> dict[str, Any]:
    """Contraintes du profil et seuils à passer à verifier_contraintes (une seule table)."""
    c = contraintes(profil)
    lim = c["limites"]
    tolerance, _ = tolerance_normalisee(profil.tolerance_risque)
    seuils = {tolerance: {**SEUILS_PAR_TOLERANCE[tolerance],
                          "titre": lim["max_titre_individuel"], "crypto": lim["max_crypto"],
                          "secteur": lim["max_un_secteur"]}}
    return {**c, "seuils_outil": seuils, "tolerance": tolerance}


def enregistrer_limites(journal: Journal, c: dict[str, Any]) -> dict[str, str]:
    """Chaque limite du profil devient un chiffre citable, avec son origine."""
    ids = {}
    for nom, valeur in c["limites"].items():
        if nom == "min_lignes":
            continue
        ids[nom] = journal.enregistrer(cle("lim", nom), {
            "outil": "agents.profil.contraintes", "parametres": {"limite": nom},
            "periode": {"debut": None, "fin": None, "observations": None},
            "valeur": float(valeur), "unite": "fraction du capital",
            "formule": f"limite fixée par {c['origine'][nom]}",
            "sources": ["agents/profil.py (LIMITES_PAR_TOLERANCE)"],
            "details": {"nature": c["nature"]}})
    for nom in ("volatilite", "pire_baisse"):
        valeur = c["seuils_outil"][c["tolerance"]][nom]
        ids[nom] = journal.enregistrer(cle("seuil", nom), {
            "outil": "tools.gouvernance.SEUILS_PAR_TOLERANCE", "parametres": {"tolerance": c["tolerance"], "seuil": nom},
            "periode": {"debut": None, "fin": None, "observations": None},
            "valeur": float(valeur), "unite": "fraction",
            "formule": f"seuil de {nom.replace('_', ' ')} pour une tolérance « {c['tolerance']} »",
            "sources": ["tools/gouvernance.py (SEUILS_PAR_TOLERANCE)"],
            "details": {"nature": "hypothèse du projet, pas une norme réglementaire"}})
    return ids


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %"


def _controle(nom: str, statut: str, message: str, **autres: Any) -> dict[str, Any]:
    return {"controle": nom, "statut": statut, "bloquant": statut == "non conforme", "message": message, **autres}


def diversification(poids: dict[str, float], c: dict[str, Any]) -> dict[str, Any]:
    table = univers()
    lignes = [s for s, w in poids.items() if w > 0]
    risquee = sum(w for s, w in poids.items() if s in table.index and table.at[s, "asset_class"] in CLASSES_RISQUEES)
    lim = c["limites"]
    erreurs = []
    if len(lignes) < lim["min_lignes"]:
        erreurs.append(f"{len(lignes)} lignes, il en faut au moins {lim['min_lignes']}")
    if risquee > lim["max_part_risquee"] + 1e-6:
        erreurs.append(f"part risquée (actions, FNB d'actions, crypto) de {_pct(risquee)}, "
                       f"plafond {_pct(lim['max_part_risquee'])}")
    message = ("; ".join(erreurs) + "." if erreurs else
               f"{len(lignes)} lignes ; part risquée {_pct(risquee)}, plafond {_pct(lim['max_part_risquee'])}.")
    return _controle("diversification", "non conforme" if erreurs else "conforme", message,
                     mesure={"lignes": len(lignes), "part_risquee": risquee},
                     seuil={"min_lignes": lim["min_lignes"], "max_part_risquee": lim["max_part_risquee"]},
                     source="agents/profil.py (contraintes)")


def controler(portefeuille: dict[str, Any], profil: Profil, c: dict[str, Any],
              controles_en_plus: list[dict[str, Any]] | None = None,
              exclusions_traitees: list[str] | None = None) -> dict[str, Any]:
    """Contrôle d'un portefeuille. `portefeuille` : {"poids": {...}, "theme": {...} | None}.

    `exclusions_traitees` : exclusions du profil vérifiées par un contrôle en plus (exclusion_esg) ;
    le contrôle « exclusion » de l'outil, qui ne sait pas les vérifier, est alors retiré.
    """
    res = verifier_contraintes(
        {"poids": portefeuille["poids"], "theme": portefeuille.get("theme")},
        profil.model_dump(), plafond_theme=c["limites"]["plafond_theme"], seuils=c["seuils_outil"],
        debut=None, fin=None)
    controles = [x for x in res["details"]["controles"]
                 if not (x["controle"] == "exclusion" and x.get("exclusion") in (exclusions_traitees or []))]
    controles.append(diversification(portefeuille["poids"], c))
    controles.extend(controles_en_plus or [])
    rejets = [x["controle"] for x in controles if x["statut"] == "non conforme"]
    return {"accepte": not rejets, "rejets": rejets, "controles": controles,
            "reference": {k: res[k] for k in ("outil", "periode", "formule", "sources")},
            "limites_outil": res["details"]["limites"]}


def demande_hors_profil(demande: dict[str, Any], c: dict[str, Any], journal: Journal,
                        ids_limites: dict[str, str]) -> list[dict[str, Any]]:
    """Compare la demande aux limites. Non bloquant : le portefeuille, lui, respecte les limites.

    Le contrôle est « à signaler » quand la demande dépasse une limite : il dit pourquoi,
    avec la pire baisse, la volatilité et le gain de rattrapage calculés par tools/.
    """
    table = univers()
    lim = c["limites"]
    controles = []
    for d in demande.get("symboles", []):
        s, voulu = d["symbole"], d.get("poids")
        if s not in table.index:
            continue
        classe = table.at[s, "asset_class"]
        plafond_nom = "max_crypto" if classe == "crypto" else "max_titre_individuel" if classe == "equity" else None
        if plafond_nom is None:
            continue
        vol = journal.mesurer("volatilite", cle("vol", s), symbole=s)["valeur"]
        pb = journal.mesurer("pire_baisse", cle("pb", s), symbole=s)["valeur"]
        rattrapage = journal.enregistrer(cle("rattrapage", s), _rattrapage(journal, pb))
        # Sans part chiffrée (« une bonne part »), la demande est signalée : elle ne fixe aucune limite.
        depasse = voulu is None or voulu > lim[plafond_nom] + 1e-9
        portee = ("pour la crypto, BTC-USD et ETH-USD ensemble" if plafond_nom == "max_crypto"
                  else "pour une action seule")
        detail = (f"{s} : volatilité {{{vol}}}, pire baisse {{{pb}}} sur la fenêtre. "
                  f"Après une telle baisse, il faut un gain de {{{rattrapage}}} pour revenir au point de départ. "
                  f"Plafond du profil {portee} : {{{ids_limites[plafond_nom]}}}.")
        controles.append(_controle(
            "demande_hors_profil", "à signaler" if depasse else "conforme", detail,
            symboles=[s], poids_demande=voulu, plafond=lim[plafond_nom], limite=plafond_nom,
            chiffres=[vol, pb, rattrapage, ids_limites[plafond_nom]]))
    for classe in demande.get("classes", []):
        if classe == "crypto" and lim["max_crypto"] == 0:
            controles.append(_controle(
                "demande_hors_profil", "à signaler",
                f"Crypto demandée, mais le plafond du profil est {{{ids_limites['max_crypto']}}} "
                f"({c['origine']['max_crypto']}).", classes=["crypto"], chiffres=[ids_limites["max_crypto"]]))
    if demande.get("part_risquee") is not None and demande["part_risquee"] > lim["max_part_risquee"] + 1e-9:
        controles.append(_controle(
            "demande_hors_profil", "à signaler",
            f"La part risquée demandée dépasse le plafond du profil, {{{ids_limites['max_part_risquee']}}} "
            f"({c['origine']['max_part_risquee']}).", chiffres=[ids_limites["max_part_risquee"]]))
    return controles


def _rattrapage(journal: Journal, id_pb: str) -> dict[str, Any]:
    from tools.mesures import gain_de_rattrapage
    res = gain_de_rattrapage(journal.chiffres[id_pb]["valeur"])
    ref = {k: res[k] for k in ("outil", "parametres", "periode", "valeur", "unite", "formule", "sources", "details")}
    ref["parametres"] = {**ref["parametres"], "perte": f"pire_baisse({journal.chiffres[id_pb]['parametres']['symbole']})"}
    ref["periode"] = journal.chiffres[id_pb]["periode"]
    ref["sources"] = ref["sources"] or [f"pire_baisse ({id_pb})", *journal.chiffres[id_pb]["sources"]]
    return ref


def pour_interface(x: dict[str, Any]) -> dict[str, Any]:
    """Un contrôle tel que l'affiche la carte « vérifications »."""
    sortie = {"statut": STATUT_INTERFACE[x["statut"]], "titre": TITRES.get(x["controle"], x["controle"]),
              "detail": x["message"], "controle": x["controle"], "statut_outil": x["statut"]}
    for k in ("symboles", "chiffres", "reference", "source", "actifs"):
        if x.get(k):
            sortie[k] = x[k]
    return sortie


def source_univers() -> str:
    return FICHIER_UNIVERS
