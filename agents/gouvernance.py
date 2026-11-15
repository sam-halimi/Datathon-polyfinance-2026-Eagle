"""Gouvernance : chaque portefeuille simulé est vérifié contre le profil, sans modèle de langage.

Une seule table de limites (décision du plan du dimanche) : les limites de poids viennent de
`agents.profil.contraintes(profil)` et sont passées à `tools.gouvernance.verifier_contraintes`.
Celui-ci garde ses seuils de volatilité et de pire baisse. On ajoute ici trois contrôles
propres au profil : part risquée, nombre de lignes, et l'écart entre la demande de
l'utilisateur et son profil (`demande_hors_profil`).

Un « non conforme » renvoie le portefeuille au constructeur (2 essais au plus, dans
`agents.pipeline`). Les contrôles sont affichés tels quels dans la carte « vérifications ».
"""

from __future__ import annotations

from typing import Any

from agents.profil import Profil
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE, verifier_contraintes

CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")
ESSAIS_MAX = 2

TITRES = {
    "demande_hors_profil": "Votre demande comparée à votre profil",
    "somme_des_poids": "Le capital est réparti en entier",
    "poids_positifs": "Ni vente à découvert ni levier",
    "univers_source": "Actifs tirés de la table sourcée",
    "instruments_autorises": "Aucun dérivé ni option",
    "exclusion": "Vos exclusions",
    "plafond_par_titre": "Plafond par titre",
    "plafond_crypto": "Plafond crypto",
    "plafond_par_secteur": "Plafond par secteur",
    "plafond_theme": "Thème plafonné",
    "theme_actions_et_fnb": "Thème sur actions et FNB seulement",
    "part_risquee_max": "Part risquée",
    "lignes_min": "Diversification",
    "volatilite_max": "Volatilité historique",
    "pire_baisse_max": "Pire baisse historique",
    "risque_historique": "Risque historique",
    "tolerance_risque": "Tolérance au risque retenue",
}
STATUT_INTERFACE = {"conforme": "ok", "non conforme": "echec", "à signaler": "alerte",
                    "information manquante": "alerte"}


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",").replace(",0 %", " %")


def seuils_depuis_limites(profil: Profil, limites: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Seuils de `verifier_contraintes` : poids du profil, volatilité et pire baisse des outils."""
    base = dict(SEUILS_PAR_TOLERANCE[profil.tolerance_risque])
    base.update(titre=limites["max_titre_individuel"], crypto=limites["max_crypto"],
                secteur=limites["max_un_secteur"])
    return {profil.tolerance_risque: base}


def _controle(nom: str, statut: str, message: str, **autres: Any) -> dict[str, Any]:
    return {"controle": nom, "statut": statut, "bloquant": statut == "non conforme",
            "message": message, **autres}


def controle_demande(demande: dict[str, Any] | None, profil: Profil, limites: dict[str, Any]) -> dict[str, Any] | None:
    """Compare ce que l'utilisateur a demandé (positions extraites par l'orchestrateur) aux limites.

    Statut « à signaler » : la tension est dite à l'utilisateur, la demande n'est pas exécutée
    telle quelle. Les poids demandés viennent du texte de l'utilisateur, pas d'un calcul.
    """
    if not demande or not demande.get("positions"):
        return None
    table = univers()
    exclus = {e.upper() for e in profil.exclusions}
    ecarts, symboles = [], []
    totaux = {"crypto": 0.0, "risquee": 0.0, "theme": 0.0}
    for pos in demande["positions"]:
        poids, symbole = pos.get("poids"), pos.get("symbole")
        classe = pos.get("classe")
        if symbole in table.index:
            classe = table.at[symbole, "asset_class"]
            symboles.append(symbole)
            if symbole in exclus:
                ecarts.append(f"{symbole} fait partie de vos exclusions")
        if poids is None:
            continue
        totaux["crypto"] += poids if classe == "crypto" else 0
        totaux["theme"] += poids if pos.get("role") == "theme" else 0
        totaux["risquee"] += poids if classe in CLASSES_RISQUEES or pos.get("role") == "theme" else 0
        if classe == "equity" and symbole and poids > limites["max_titre_individuel"]:
            ecarts.append(f"{symbole} demandé à {_pct(poids)} du capital, plafond par titre de "
                          f"{_pct(limites['max_titre_individuel'])} pour votre profil")
    for cle, limite, libelle in (("crypto", "max_crypto", "crypto"), ("theme", "plafond_theme", "thème"),
                                 ("risquee", "max_part_risquee", "part risquée")):
        if totaux[cle] > limites[limite] + 1e-9:
            ecarts.append(f"{libelle} demandée à {_pct(totaux[cle])} du capital, plafond {_pct(limites[limite])}")
    if not ecarts:
        return _controle("demande_hors_profil", "conforme",
                         "Votre demande reste dans les limites de votre profil.", symboles=symboles)
    return _controle(
        "demande_hors_profil", "à signaler",
        "Demande non retenue telle quelle : " + " ; ".join(ecarts) + ".",
        symboles=symboles, ecarts=ecarts, demande=demande.get("texte"))


def verifier_portefeuille(poids: dict[str, float], theme: dict[str, Any] | None, profil: Profil,
                          contraintes_profil: dict[str, Any]) -> dict[str, Any]:
    """Tous les contrôles d'un portefeuille simulé. `accepte` : aucun « non conforme »."""
    limites = contraintes_profil["limites"]
    res = verifier_contraintes(
        {"poids": poids, "theme": theme}, profil.model_dump(),
        plafond_theme=limites["plafond_theme"], seuils=seuils_depuis_limites(profil, limites))
    controles = [c for c in res["details"]["controles"] if c["controle"] != "tolerance_risque"]

    table = univers()
    connus = {s: w for s, w in poids.items() if s in table.index and w > 0}
    risquee = sum(w for s, w in connus.items() if table.at[s, "asset_class"] in CLASSES_RISQUEES)
    controles.append(_controle(
        "part_risquee_max", "non conforme" if risquee > limites["max_part_risquee"] + 1e-9 else "conforme",
        f"Actions, FNB d'actions et crypto : {_pct(risquee)} du capital, plafond {_pct(limites['max_part_risquee'])}.",
        mesure=risquee, seuil=limites["max_part_risquee"]))
    lignes = len(connus)
    controles.append(_controle(
        "lignes_min", "non conforme" if lignes < limites["min_lignes"] else "conforme",
        f"{lignes} lignes, minimum {limites['min_lignes']}.", mesure=lignes, seuil=limites["min_lignes"]))
    if theme and limites["plafond_theme"] == 0:
        controles.append(_controle("plafond_theme", "non conforme",
                                   "Aucun centre d'intérêt déclaré : pas de thème permis.", mesure=theme))
    rejets = [c["controle"] for c in controles if c["statut"] == "non conforme"]
    return {
        "accepte": not rejets,
        "rejets": rejets,
        "controles": controles,
        "reference": {k: res[k] for k in ("outil", "parametres", "periode", "formule", "sources")},
        "seuils": {**res["details"]["seuils"], **limites},
        "limites_outil": res["details"]["limites"],
    }


def pour_interface(controle: dict[str, Any]) -> dict[str, str]:
    """Contrôle au format de la carte « vérifications » : statut ok, alerte ou echec."""
    titre = TITRES.get(controle["controle"], controle["controle"])
    if controle["controle"] == "exclusion":
        titre = f"Exclusion « {controle.get('exclusion', '')} »"
    sortie = {"statut": STATUT_INTERFACE[controle["statut"]], "titre": titre,
              "detail": controle["message"], "controle": controle["controle"],
              "statut_detaille": controle["statut"]}
    for cle in ("symboles", "actifs", "exclusion", "mesure", "seuil", "reference", "source"):
        if controle.get(cle) not in (None, [], {}):
            sortie[cle] = controle[cle]
    return sortie
