"""Gouvernance : vérifie chaque portefeuille simulé contre le profil. Déterministe, sans modèle.

Une seule table de limites (décision du plan du dimanche) : les limites de poids viennent de
`agents.profil.contraintes(profil)` (par titre, crypto, par secteur, part risquée, nombre de
lignes, thème). `tools.gouvernance.verifier_contraintes` les reçoit par son paramètre `seuils`
et garde ses propres seuils de volatilité et de pire baisse.

Deux contrôles s'ajoutent à ceux de `verifier_contraintes` :
- `part_risquee_max` et `lignes_min` (limites du profil que l'outil ne connaît pas) ;
- `demande_hors_profil` : la demande de l'utilisateur comparée au profil. Toujours affiché ;
  « à signaler » quand la demande contredit le profil. C'est le contrôle de Robert.

Un contrôle « non conforme » renvoie le portefeuille au constructeur (2 essais au plus).
"""

from __future__ import annotations

from typing import Any

from agents.profil import Profil, contraintes
from agents.registre import Registre, identifiant
from agents.schemas import Cadrage
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE, verifier_contraintes

CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")
STATUT_INTERFACE = {"conforme": "ok", "non conforme": "echec", "à signaler": "alerte",
                    "information manquante": "manquant"}
TITRES = {
    "somme_des_poids": "Les poids font un tout",
    "poids_positifs": "Ni vente à découvert ni levier",
    "univers_source": "Symboles de la table sourcée",
    "instruments_autorises": "Aucun dérivé ni option",
    "exclusion": "Exclusion respectée",
    "plafond_par_titre": "Plafond par titre",
    "plafond_crypto": "Plafond crypto",
    "plafond_par_secteur": "Plafond par secteur",
    "plafond_theme": "Thème plafonné",
    "theme_actions_et_fnb": "Thème sur actions et FNB seulement",
    "volatilite_max": "Volatilité dans la limite du profil",
    "pire_baisse_max": "Pire baisse dans la limite du profil",
    "risque_historique": "Risque historique",
    "tolerance_risque": "Tolérance retenue",
    "part_risquee_max": "Part risquée plafonnée",
    "lignes_min": "Diversification minimale",
    "demande_hors_profil": "Votre demande face à votre profil",
}

# Limites du profil -> clés de seuils de verifier_contraintes.
CORRESPONDANCE = {"max_titre_individuel": "titre", "max_crypto": "crypto", "max_un_secteur": "secteur"}


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %" if abs(x * 100 - round(x * 100)) < 1e-9 else f"{x * 100:.1f} %".replace(".", ",")


def seuils_du_profil(profil: Profil) -> dict[str, dict[str, float]]:
    """Seuils passés à verifier_contraintes : poids du profil, volatilité et pire baisse de l'outil."""
    limites = contraintes(profil)["limites"]
    seuils = {tol: dict(v) for tol, v in SEUILS_PAR_TOLERANCE.items()}
    for nom, cle in CORRESPONDANCE.items():
        seuils[profil.tolerance_risque][cle] = float(limites[nom])
    return seuils


def inscrire_limites(reg: Registre, profil: Profil) -> dict[str, str]:
    """Les limites du profil et les seuils de risque, au registre (hypothèses de conception)."""
    c = contraintes(profil)
    ids = {}
    noms = {"max_titre_individuel": "Plafond par titre individuel", "max_crypto": "Plafond des cryptoactifs",
            "max_part_risquee": "Plafond de la part risquée (actions, FNB d'actions, crypto)",
            "max_un_secteur": "Plafond par secteur (actions détenues en direct)",
            "min_lignes": "Nombre minimal de lignes du portefeuille (pas un nombre d'années)",
            "plafond_theme": "Plafond du thème"}
    for nom, v in c["limites"].items():
        fmt, unite = ("entier", "lignes") if nom == "min_lignes" else ("pourcent", "fraction du capital")
        ids[nom] = reg.entree(identifiant("limite", nom), float(v), f"{noms.get(nom, nom)} ({c['origine'][nom]})",
                              "agents/profil.py::contraintes (hypothèse de conception)", fmt, unite, par="orchestrateur")
    ids["horizon"] = reg.entree("profil_horizon", float(profil.horizon_annees),
                                "Horizon de placement retenu, en années (borne basse si une fourchette a été donnée)",
                                "profil validé à l'accueil", "entier", "années", par="accueil")
    ids["capital"] = reg.entree("profil_capital", float(profil.capital_fictif), f"Capital fictif, en {profil.devise}",
                                "profil validé à l'accueil", "montant", profil.devise, par="accueil")
    s = SEUILS_PAR_TOLERANCE[profil.tolerance_risque]
    ids["volatilite"] = reg.entree("limite_volatilite", s["volatilite"],
                                   f"Volatilité maximale pour une tolérance « {profil.tolerance_risque} »",
                                   "tools/gouvernance.py::SEUILS_PAR_TOLERANCE (hypothèse du projet)",
                                   "pourcent", "fraction annualisée", par="orchestrateur")
    ids["pire_baisse"] = reg.entree("limite_pire_baisse", s["pire_baisse"],
                                    f"Pire baisse admise pour une tolérance « {profil.tolerance_risque} »",
                                    "tools/gouvernance.py::SEUILS_PAR_TOLERANCE (hypothèse du projet)",
                                    "pourcent", "fraction", par="orchestrateur")
    return ids


def controle_demande(cadrage: Cadrage, profil: Profil, reg: Registre, fiches: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Compare la demande au profil. Le constat ne dépend que des limites et des chiffres de tools/."""
    limites = contraintes(profil)["limites"]
    table = univers()
    seuil_vol = SEUILS_PAR_TOLERANCE[profil.tolerance_risque]["volatilite"]
    ecarts, chiffres = [], []
    for p in cadrage.positions_demandees:
        if p.symbole not in table.index:
            continue
        classe = table.at[p.symbole, "asset_class"]
        f = fiches.get(p.symbole, {})
        chiffres += [i for i in f.values()]
        plafond = limites["max_crypto"] if classe == "crypto" else (
            limites["max_titre_individuel"] if classe == "equity" else None)
        if p.poids_demande is not None and plafond is not None and p.poids_demande > plafond + 1e-9:
            ecarts.append(f"{p.symbole} : {_pct(p.poids_demande)} demandés, plafond du profil {_pct(plafond)}")
        elif p.poids_demande is None and f and reg.valeur(f["volatilite"]) > seuil_vol:
            ecarts.append(f"{p.symbole} : une part importante est demandée, mais sa volatilité dépasse "
                          f"la limite du profil ({reg.affiche(f['volatilite'])} contre {_pct(seuil_vol)})")
    if "crypto" in cadrage.classes_demandees and limites["max_crypto"] == 0:
        ecarts.append("crypto demandée, plafond du profil nul")
    total = getattr(cadrage, "poids_total_demande", None)
    if total is not None and total > limites["max_part_risquee"] + 1e-9:
        ecarts.append(f"{_pct(total)} du capital demandés sur des actifs risqués, plafond du profil "
                      f"{_pct(limites['max_part_risquee'])}")
    if ecarts:
        statut, message = "à signaler", ("La demande n'est pas suivie telle quelle. " + " ; ".join(ecarts) + ".")
    elif cadrage.positions_demandees or cadrage.classes_demandees:
        statut, message = "conforme", "La demande reste dans les limites du profil."
    else:
        statut, message = "conforme", "Aucune demande particulière."
    return {"controle": "demande_hors_profil", "statut": statut, "bloquant": False, "message": message,
            "symboles": [p.symbole for p in cadrage.positions_demandees], "chiffres": sorted(set(chiffres))}


def verifier(lignes: list[dict[str, Any]], profil: Profil, cadrage: Cadrage, reg: Registre,
             fiches: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Tous les contrôles d'un portefeuille simulé. `valeur` True si rien n'est « non conforme »."""
    limites = contraintes(profil)["limites"]
    poids = {l["symbole"]: float(l["poids"]) for l in lignes}
    theme = [l["symbole"] for l in lignes if l["role"] == "theme"]
    portefeuille = {"poids": poids, "theme": {"nom": cadrage.theme.nom if cadrage.theme else "thème",
                                              "symboles": theme} if theme else None}
    res = verifier_contraintes(portefeuille, profil.model_dump(), plafond_theme=limites["plafond_theme"],
                               seuils=seuils_du_profil(profil))
    controles = [dict(c) for c in res["details"]["controles"]]

    table = univers()
    risquee = sum(w for s, w in poids.items() if s in table.index and table.at[s, "asset_class"] in CLASSES_RISQUEES)
    controles.append({"controle": "part_risquee_max",
                      "statut": "non conforme" if risquee > limites["max_part_risquee"] + 1e-6 else "conforme",
                      "message": f"Actions, FNB d'actions et crypto : {_pct(risquee)} du capital, "
                                 f"plafond {_pct(limites['max_part_risquee'])}.",
                      "mesure": risquee, "seuil": limites["max_part_risquee"]})
    n = sum(1 for w in poids.values() if w > 0)
    controles.append({"controle": "lignes_min",
                      "statut": "non conforme" if n < limites["min_lignes"] else "conforme",
                      "message": f"{n} lignes, minimum {int(limites['min_lignes'])}.",
                      "mesure": n, "seuil": limites["min_lignes"]})
    controles.insert(0, controle_demande(cadrage, profil, reg, fiches))
    for c in controles:
        c["bloquant"] = c["statut"] == "non conforme"
    return {"valeur": not any(c["bloquant"] for c in controles), "controles": controles, "reference": res}


def pour_interface(controles: list[dict[str, Any]], reg: Registre, ptf_id: str) -> list[dict[str, Any]]:
    """Contrôles au format de la carte « vérifications ». Les mesures calculées vont au registre."""
    sortie = []
    for c in controles:
        chiffres = list(c.get("chiffres", []))
        if "reference" in c and isinstance(c.get("mesure"), (int, float)):
            ref = {**c["reference"], "valeur": c["mesure"], "unite": "fraction", "details": {}}
            chiffres.append(reg.inscrire(ref, identifiant("controle", ptf_id, c["controle"]),
                                         f"{TITRES.get(c['controle'], c['controle'])}, portefeuille {ptf_id}",
                                         par="gouvernance"))
        sortie.append({
            "id": c["controle"], "titre": TITRES.get(c["controle"], c["controle"]),
            "statut": STATUT_INTERFACE[c["statut"]], "statut_outil": c["statut"],
            "bloquant": c["statut"] == "non conforme", "detail": c["message"], "chiffres": chiffres,
        })
    return sortie
