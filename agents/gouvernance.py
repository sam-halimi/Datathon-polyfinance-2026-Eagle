"""Gouvernance : vérifie chaque portefeuille simulé contre le profil, sans modèle de langage.

Une seule table de limites (décision du plan du dimanche) : les limites de poids viennent de
`agents.profil.contraintes(profil)` et sont passées à `tools.gouvernance.verifier_contraintes` par
son paramètre `seuils`. Les seuils de volatilité et de pire baisse restent ceux de tools/.
Deux contrôles s'ajoutent ici, absents de tools/ : nombre de lignes et part risquée.

`controle_demande` relève la tension entre la demande de l'utilisateur et son profil.

Chaque contrôle est rendu au format de la carte « vérifications » :
{controle, statut (ok | alerte | echec), titre, detail, chiffres, source}.
"""

from __future__ import annotations

from typing import Any

from agents.journal import DECISION, DEMANDE, HYPOTHESE, Journal
from agents.outils_agents import devise_calcul, mesurer
from agents.profil import Profil
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE, verifier_contraintes

SOURCE_TOOLS = "tools/gouvernance.py : verifier_contraintes"
SOURCE_AGENTS = "agents/gouvernance.py"
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")
STATUTS = {"conforme": "ok", "non conforme": "echec", "à signaler": "alerte", "information manquante": "alerte"}
TITRES = {
    "somme_des_poids": "Poids complets",
    "poids_positifs": "Ni vente à découvert ni levier",
    "univers_source": "Actifs de la table sourcée",
    "instruments_autorises": "Ni options ni dérivés",
    "exclusion": "Exclusion",
    "plafond_par_titre": "Plafond par titre",
    "plafond_crypto": "Plafond crypto",
    "plafond_par_secteur": "Plafond par secteur",
    "plafond_theme": "Thème plafonné",
    "theme_actions_et_fnb": "Thème : actions et FNB seulement",
    "volatilite_max": "Volatilité historique",
    "pire_baisse_max": "Pire baisse historique",
    "risque_historique": "Risque historique",
    "tolerance_risque": "Tolérance au risque",
    "nombre_de_lignes": "Diversification",
    "part_risquee": "Part risquée",
    "demande_hors_profil": "Votre demande",
}


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def seuils_du_profil(profil: Profil, c: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Seuils pour verifier_contraintes : poids du profil, volatilité et pire baisse de tools/."""
    lim = c["limites"]
    base = dict(SEUILS_PAR_TOLERANCE[profil.tolerance_risque])
    base.update(titre=lim["max_titre_individuel"], crypto=lim["max_crypto"], secteur=lim["max_un_secteur"])
    return {profil.tolerance_risque: base}


def enregistrer_limites(journal: Journal, profil: Profil, c: dict[str, Any]) -> dict[str, str]:
    """Les limites du profil et les seuils de risque deviennent des chiffres cités (hypothèses)."""
    cles = {}
    for nom, valeur in c["limites"].items():
        if nom == "min_lignes":
            continue
        cles[nom] = journal.valeur_hors_outil(
            f"lim_{nom}", valeur, "fraction du capital", f"Limite « {nom} » du profil ({c['origine'][nom]})",
            HYPOTHESE, "agents/profil.py : contraintes", parametres={"tolerance_risque": profil.tolerance_risque,
                                                                    "horizon_annees": profil.horizon_annees})
    seuils = SEUILS_PAR_TOLERANCE[profil.tolerance_risque]
    for nom in ("volatilite", "pire_baisse"):
        cles[f"seuil_{nom}"] = journal.valeur_hors_outil(
            f"lim_{nom}", seuils[nom], "fraction", f"Seuil de {nom.replace('_', ' ')} pour une tolérance "
            f"« {profil.tolerance_risque} »", HYPOTHESE, "tools/gouvernance.py : SEUILS_PAR_TOLERANCE",
            parametres={"tolerance_risque": profil.tolerance_risque})
    return cles


def _carte(controle: str, statut: str, detail: str, chiffres: list[str] | None = None,
           source: str = SOURCE_TOOLS, titre: str | None = None, bloquant: bool | None = None) -> dict[str, Any]:
    statut_carte = STATUTS.get(statut, statut)
    return {"controle": controle, "statut": statut_carte, "titre": titre or TITRES.get(controle, controle),
            "detail": detail, "chiffres": chiffres or [], "source": source,
            "bloquant": statut_carte == "echec" if bloquant is None else bloquant}


def verifier_portefeuille(journal: Journal, profil: Profil, c: dict[str, Any],
                          poids: dict[str, float], symboles_theme: list[str], nom_theme: str | None) -> dict[str, Any]:
    """Tous les contrôles d'un portefeuille simulé. `accepte` est faux si un contrôle bloque."""
    portefeuille: dict[str, Any] = {"poids": poids}
    if symboles_theme:
        portefeuille["theme"] = {"nom": nom_theme or "thème", "symboles": symboles_theme}
    res = journal.appeler(verifier_contraintes, "Gouvernance", portefeuille=portefeuille,
                          profil=profil.model_dump(), plafond_theme=c["limites"]["plafond_theme"],
                          seuils=seuils_du_profil(profil, c))
    cartes = []
    for ctl in res["details"]["controles"]:
        titre = TITRES.get(ctl["controle"], ctl["controle"])
        if ctl["controle"] == "exclusion":
            titre = f"Exclusion « {ctl.get('exclusion', '')} »"
        cartes.append(_carte(ctl["controle"], ctl["statut"], ctl["message"], titre=titre))

    table = univers()
    lignes = [s for s, w in poids.items() if w > 0]
    n_min = int(c["limites"]["min_lignes"])
    cartes.append(_carte(
        "nombre_de_lignes", "conforme" if len(lignes) >= n_min else "non conforme",
        f"{len(lignes)} lignes, au moins {n_min} exigées.", source=SOURCE_AGENTS))
    risquee = sum(w for s, w in poids.items() if s in table.index and table.at[s, "asset_class"] in CLASSES_RISQUEES)
    plafond = c["limites"]["max_part_risquee"]
    cartes.append(_carte(
        "part_risquee", "conforme" if risquee <= plafond + 1e-6 else "non conforme",
        f"Actions, FNB d'actions et crypto : {_pct(risquee)} du capital, plafond {_pct(plafond)} "
        f"({c['origine']['max_part_risquee']}).", source=SOURCE_AGENTS))
    return {"accepte": not any(k["bloquant"] for k in cartes), "controles": cartes,
            "rejets": [k for k in cartes if k["bloquant"]], "reference": res["outil"]}


def limite_applicable(symboles: list[str], c: dict[str, Any]) -> tuple[str, float]:
    """La limite du profil qui s'applique à un groupe d'actifs demandé."""
    table = univers()
    classes = {table.at[s, "asset_class"] for s in symboles}
    lim = c["limites"]
    if classes == {"crypto"}:
        return "max_crypto", lim["max_crypto"]
    if len(symboles) == 1 and classes <= {"equity"}:
        return "max_titre_individuel", lim["max_titre_individuel"]
    return "max_part_risquee", lim["max_part_risquee"]


def controle_demande(journal: Journal, profil: Profil, c: dict[str, Any], cibles: list[dict[str, Any]],
                     cles_limites: dict[str, str]) -> list[dict[str, Any]]:
    """Relève chaque demande chiffrée qui dépasse une limite du profil, avec le risque des actifs visés.

    Non bloquant : la demande n'est pas exécutée telle quelle, le constructeur reste sous les limites.
    """
    cartes = []
    devise = devise_calcul(profil.model_dump())
    for cible in cibles:
        symboles, poids = cible["symboles"], cible.get("poids_demande")
        if not symboles or poids is None:
            continue
        nom_limite, plafond = limite_applicable(symboles, c)
        cle_demande = journal.valeur_hors_outil(
            f"demande_{'_'.join(symboles[:2])}", poids, "fraction du capital",
            f"Part du capital demandée pour {', '.join(symboles)}", DEMANDE, "demande de l'utilisateur",
            parametres={"extrait": cible.get("extrait", "")})
        cles = [cle_demande, cles_limites[nom_limite]]
        risque = []
        for s in symboles[:3]:
            m = mesurer(journal, "Gouvernance", s, devise)
            cles += [m["volatilite"], m["pire_baisse"], m["gain_de_rattrapage"]]
            risque.append(f"{s} : pire baisse {{{m['pire_baisse']}}}, il faudrait {{{m['gain_de_rattrapage']}}} "
                          f"pour la rattraper, volatilité {{{m['volatilite']}}}.")
        if poids > plafond + 1e-9:
            detail = (f"Demandé : {{{cle_demande}}} du capital sur {', '.join(symboles)}. Votre profil en permet "
                      f"au plus {{{cles_limites[nom_limite]}}}. La demande n'est pas retenue telle quelle. "
                      + " ".join(risque))
            cartes.append(_carte("demande_hors_profil", "à signaler", detail, cles, SOURCE_AGENTS,
                                 titre=f"Votre demande sur {', '.join(symboles)}", bloquant=False))
        else:
            detail = (f"Demandé : {{{cle_demande}}} sur {', '.join(symboles)}, dans la limite de "
                      f"{{{cles_limites[nom_limite]}}} de votre profil. " + " ".join(risque))
            cartes.append(_carte("demande_dans_le_profil", "conforme", detail, cles, SOURCE_AGENTS,
                                 titre=f"Votre demande sur {', '.join(symboles)}"))
    return cartes


def enregistrer_poids(journal: Journal, ident: str, poids: dict[str, float]) -> dict[str, str]:
    return {s: journal.valeur_hors_outil(
        f"poids_{s}_{ident}", w, "fraction du capital", f"Poids de {s} dans le portefeuille simulé {ident}",
        DECISION, "constructeur (vérifié par la gouvernance)", parametres={"portefeuille": ident})
        for s, w in poids.items()}
