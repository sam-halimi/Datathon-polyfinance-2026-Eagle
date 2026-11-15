"""Vérification d'un portefeuille simulé contre le profil de l'investisseur.

`verifier_contraintes` est le contrôle de l'agent de gouvernance. Il renvoie
chaque contrôle avec son statut, la mesure, le seuil et, pour un chiffre
calculé, la référence de l'appel qui l'a produit. Les contrôles sont affichés
tels quels dans la carte « vérifications ».

Statuts :

- `conforme` ;
- `non conforme` : bloquant, le portefeuille retourne au constructeur ;
- `à signaler` : non bloquant, à dire dans les limites ;
- `information manquante` : la donnée nécessaire n'existe pas dans data/.
  On le dit, on ne conclut pas à la conformité.

Les seuils par tolérance au risque sont des hypothèses du projet, réglables
(`SEUILS_PAR_TOLERANCE` ou paramètre `seuils`), pas une norme réglementaire.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from tools.donnees import FICHIER_UNIVERS, univers
from tools.portefeuille import TOLERANCE_SOMME, stats_portefeuille
from tools.trace import resultat

PLAFOND_THEME = 0.10
HORIZON_COURT_ANNEES = 5
CLASSES_AUTORISEES = ("equity", "etf_equity", "etf_bond", "etf_commodity", "crypto")
CLASSES_THEME = ("equity", "etf_equity")
TOLERANCES = ("faible", "modéré", "élevé")

# Hypothèses du projet. titre = un seul titre (action ou crypto) ; secteur =
# total des actions détenues en direct dans un même secteur ; pire_baisse =
# plancher de la pire baisse historique du portefeuille simulé.
SEUILS_PAR_TOLERANCE: dict[str, dict[str, float]] = {
    "faible": {"volatilite": 0.08, "pire_baisse": -0.15, "titre": 0.05, "crypto": 0.0, "secteur": 0.15},
    "modéré": {"volatilite": 0.14, "pire_baisse": -0.25, "titre": 0.10, "crypto": 0.05, "secteur": 0.25},
    "élevé": {"volatilite": 0.22, "pire_baisse": -0.40, "titre": 0.15, "crypto": 0.10, "secteur": 0.35},
}

SECTEURS = {
    "energie": "Energy", "energies": "Energy", "petrole": "Energy", "petrole et gaz": "Energy",
    "finance": "Financials", "banques": "Financials", "services financiers": "Financials",
    "technologie": "Information Technology", "techno": "Information Technology",
    "technologies de l'information": "Information Technology",
    "sante": "Health Care", "services publics": "Utilities", "industrie": "Industrials",
    "consommation de base": "Consumer Staples",
    "consommation discretionnaire": "Consumer Discretionary",
    "communication": "Communication Services", "services de communication": "Communication Services",
}
CLASSES = {
    "crypto": "crypto", "cryptos": "crypto", "cryptomonnaie": "crypto", "cryptomonnaies": "crypto",
    "cryptoactifs": "crypto", "obligations": "etf_bond", "fnb obligataires": "etf_bond",
    "or": "etf_commodity", "matieres premieres": "etf_commodity",
}
LIMITES = [
    "Les FNB ne sont pas vus en transparence : un secteur ou un titre exclu peut être "
    "détenu à travers SPY, QQQ, XIU.TO ou ESGV (composition des FNB absente de data/).",
    "Volatilité et pire baisse sont mesurées sur la fenêtre historique : elles décrivent "
    "le passé et ne garantissent rien.",
    "Les seuils par tolérance au risque sont des hypothèses du projet, pas une norme.",
]


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("_", " ").replace("-", " ").split())


def tolerance_normalisee(tolerance: str) -> tuple[str, str | None]:
    """« modere » -> « modéré ». « faible à modéré » -> la plus prudente, avec une note."""
    t = _normaliser(tolerance)
    mots = t.split()
    trouvees = [nom for nom in TOLERANCES if any(m.startswith(_normaliser(nom)) for m in mots)]
    if not trouvees:
        raise ValueError(f"tolerance_risque inconnue : {tolerance!r}. Choix : {TOLERANCES}")
    if len(trouvees) > 1:
        return trouvees[0], f"« {tolerance} » : seuils de la tolérance la plus prudente ({trouvees[0]})."
    return trouvees[0], None


def horizon_minimal(horizon: Any) -> float | None:
    """Horizon en années ; pour une fourchette (8 à 12), la borne basse, plus prudente."""
    if horizon is None:
        return None
    if isinstance(horizon, (list, tuple)):
        return float(min(horizon))
    return float(horizon)


def _controle(nom, statut, message, mesure=None, seuil=None, reference=None, **autres):
    c = {"controle": nom, "statut": statut, "bloquant": statut == "non conforme",
         "mesure": mesure, "seuil": seuil, "message": message}
    if reference is not None:
        c["reference"] = reference
    c.update(autres)
    return c


def _ref(res: dict[str, Any]) -> dict[str, Any]:
    return {k: res[k] for k in ("outil", "parametres", "periode", "formule", "sources")}


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def _cible_exclusion(terme: str, table) -> tuple[str, str] | None:
    """Ce que désigne une exclusion : ('symbole'|'classe'|'secteur', valeur)."""
    brut = str(terme).strip()
    if brut.upper() in table.index:
        return "symbole", brut.upper()
    t = _normaliser(brut)
    if t in CLASSES:
        return "classe", CLASSES[t]
    if t in SECTEURS:
        return "secteur", SECTEURS[t]
    for secteur in table["sector"].unique():
        if t == _normaliser(secteur):
            return "secteur", secteur
    for classe in table["asset_class"].unique():
        if t == _normaliser(classe):
            return "classe", classe
    return None


def verifier_contraintes(
    portefeuille: dict[str, Any],
    profil: dict[str, Any],
    plafond_theme: float = PLAFOND_THEME,
    seuils: dict[str, dict[str, float]] | None = None,
    debut: str | None = None,
    fin: str | None = None,
) -> dict[str, Any]:
    """Vérifie un portefeuille simulé contre le profil.

    `portefeuille` : {"poids": {symbole: fraction}, "theme": {"nom", "symboles"}}
    (le thème est facultatif), ou directement {symbole: fraction}.
    `profil` : champs de CLAUDE.md ; `tolerance_risque` est obligatoire.

    `valeur` vaut True si aucun contrôle n'est « non conforme ».
    """
    theme = portefeuille.get("theme")
    brut = portefeuille["poids"] if "poids" in portefeuille else {
        k: v for k, v in portefeuille.items() if k != "theme"}
    poids = {s: float(w) for s, w in brut.items()}
    if "tolerance_risque" not in profil:
        raise ValueError("Le profil doit contenir tolerance_risque.")
    tolerance, note_tolerance = tolerance_normalisee(profil["tolerance_risque"])
    seuils_profil = dict((seuils or SEUILS_PAR_TOLERANCE)[tolerance])
    horizon = horizon_minimal(profil.get("horizon_annees"))
    if horizon is not None and horizon < HORIZON_COURT_ANNEES:
        seuils_profil["crypto"] = 0.0
    devise_calcul = "CAD" if str(profil.get("devise", "CAD")).upper() == "CAD" else "cotation"

    table = univers()
    controles: list[dict[str, Any]] = []

    # 1. Somme et signe des poids.
    somme = sum(poids.values())
    controles.append(_controle(
        "somme_des_poids", "conforme" if abs(somme - 1) <= TOLERANCE_SOMME else "non conforme",
        f"Les poids totalisent {_pct(somme)} du capital fictif.", mesure=somme, seuil=1.0))
    negatifs = sorted(s for s, w in poids.items() if w < 0)
    controles.append(_controle(
        "poids_positifs", "non conforme" if negatifs else "conforme",
        f"Poids négatifs (vente à découvert) : {negatifs}." if negatifs
        else "Aucune vente à découvert ni effet de levier.", mesure=negatifs))

    # 2. Univers sourcé et instruments autorisés.
    hors_univers = sorted(s for s in poids if s not in table.index)
    controles.append(_controle(
        "univers_source", "non conforme" if hors_univers else "conforme",
        f"Symboles absents de {FICHIER_UNIVERS} : {hors_univers}." if hors_univers
        else f"Tous les symboles viennent de {FICHIER_UNIVERS}.", mesure=hors_univers))
    connus = {s: w for s, w in poids.items() if s in table.index and w != 0}
    classe = {s: table.at[s, "asset_class"] for s in connus}
    interdits = sorted(s for s in connus if classe[s] not in CLASSES_AUTORISEES)
    controles.append(_controle(
        "instruments_autorises", "non conforme" if interdits else "conforme",
        f"Instruments non autorisés : {interdits}." if interdits
        else "Actions, FNB, or et cryptos seulement : ni options ni dérivés.",
        mesure=interdits, seuil=list(CLASSES_AUTORISEES)))

    # 3. Exclusions du profil.
    for terme in profil.get("exclusions") or []:
        cible = _cible_exclusion(terme, table)
        if cible is None:
            controles.append(_controle(
                "exclusion", "information manquante",
                f"« {terme} » ne peut pas être vérifié : aucune donnée de data/ ne dit quels "
                "actifs sont concernés (table ESG absente).", mesure=None, exclusion=terme))
            continue
        genre, cle = cible
        colonne = {"classe": "asset_class", "secteur": "sector"}.get(genre)
        touches = sorted(s for s in connus if (s == cle if genre == "symbole"
                                               else table.at[s, colonne] == cle))
        poids_touche = sum(connus[s] for s in touches)
        controles.append(_controle(
            "exclusion", "non conforme" if touches else "conforme",
            f"Exclusion « {terme} » ({genre} {cle}) : {touches} détenus, {_pct(poids_touche)} du capital."
            if touches else f"Exclusion « {terme} » ({genre} {cle}) : aucun actif détenu en direct.",
            mesure=poids_touche, seuil=0.0, exclusion=terme, actifs=touches,
            source=FICHIER_UNIVERS))

    # 4. Concentration : un titre, les cryptos, un secteur.
    titres = {s: w for s, w in connus.items() if classe[s] in ("equity", "crypto")}
    plafond_titre = seuils_profil["titre"]
    trop_gros = {s: w for s, w in titres.items() if w > plafond_titre + TOLERANCE_SOMME}
    plus_gros = max(titres.items(), key=lambda x: x[1]) if titres else (None, 0.0)
    controles.append(_controle(
        "plafond_par_titre", "non conforme" if trop_gros else "conforme",
        "; ".join(f"{s} pèse {_pct(w)} du capital, au-dessus du plafond de {_pct(plafond_titre)} "
                  f"pour une tolérance « {tolerance} »" for s, w in sorted(trop_gros.items()))
        if trop_gros else f"Aucun titre au-dessus de {_pct(plafond_titre)} du capital.",
        mesure={"symbole": plus_gros[0], "poids": plus_gros[1]}, seuil=plafond_titre,
        actifs=sorted(trop_gros)))

    crypto = sum(w for s, w in connus.items() if classe[s] == "crypto")
    plafond_crypto = seuils_profil["crypto"]
    raison_crypto = (f"horizon de moins de {HORIZON_COURT_ANNEES} ans"
                     if horizon is not None and horizon < HORIZON_COURT_ANNEES
                     else f"tolérance « {tolerance} »")
    controles.append(_controle(
        "plafond_crypto", "non conforme" if crypto > plafond_crypto + TOLERANCE_SOMME else "conforme",
        f"Cryptos : {_pct(crypto)} du capital, plafond {_pct(plafond_crypto)} ({raison_crypto}).",
        mesure=crypto, seuil=plafond_crypto))

    par_secteur: dict[str, float] = {}
    for s, w in connus.items():
        if classe[s] == "equity":
            par_secteur[table.at[s, "sector"]] = par_secteur.get(table.at[s, "sector"], 0) + w
    plafond_secteur = seuils_profil["secteur"]
    secteurs_trop = {k: v for k, v in par_secteur.items() if v > plafond_secteur + TOLERANCE_SOMME}
    controles.append(_controle(
        "plafond_par_secteur", "non conforme" if secteurs_trop else "conforme",
        "; ".join(f"{k} : {_pct(v)} en actions détenues en direct, plafond {_pct(plafond_secteur)}"
                  for k, v in sorted(secteurs_trop.items()))
        if secteurs_trop else f"Aucun secteur au-dessus de {_pct(plafond_secteur)} en actions détenues en direct.",
        mesure=par_secteur, seuil=plafond_secteur, limite=LIMITES[0]))

    # 5. Thème plafonné, sur actions et FNB d'actions seulement.
    if theme:
        symboles_theme = list(theme.get("symboles", []))
        poids_theme = sum(poids.get(s, 0.0) for s in symboles_theme)
        controles.append(_controle(
            "plafond_theme", "non conforme" if poids_theme > plafond_theme + TOLERANCE_SOMME else "conforme",
            f"Thème « {theme.get('nom', '')} » : {_pct(poids_theme)} du capital, plafond {_pct(plafond_theme)}.",
            mesure=poids_theme, seuil=plafond_theme, actifs=symboles_theme))
        hors_classe = sorted(s for s in symboles_theme
                             if s in table.index and table.at[s, "asset_class"] not in CLASSES_THEME)
        controles.append(_controle(
            "theme_actions_et_fnb", "non conforme" if hors_classe else "conforme",
            f"Le thème contient des actifs qui ne sont ni des actions ni des FNB d'actions : {hors_classe}."
            if hors_classe else "Le thème ne contient que des actions et des FNB d'actions.",
            mesure=hors_classe, seuil=list(CLASSES_THEME)))

    # 6. Risque mesuré sur l'historique (si le portefeuille est calculable).
    calculable = not any(c["bloquant"] for c in controles
                         if c["controle"] in ("somme_des_poids", "poids_positifs", "univers_source"))
    if calculable:
        stats = stats_portefeuille({s: w for s, w in poids.items() if w != 0}, debut, fin, devise_calcul)
        vol, pb = stats["valeur"]["volatilite"], stats["valeur"]["pire_baisse"]
        controles.append(_controle(
            "volatilite_max", "non conforme" if vol > seuils_profil["volatilite"] else "conforme",
            f"Volatilité historique {_pct(vol)}, plafond {_pct(seuils_profil['volatilite'])} "
            f"pour une tolérance « {tolerance} ».",
            mesure=vol, seuil=seuils_profil["volatilite"], reference=_ref(stats)))
        controles.append(_controle(
            "pire_baisse_max", "non conforme" if pb < seuils_profil["pire_baisse"] else "conforme",
            f"Pire baisse historique {_pct(pb)} (du {stats['details']['pire_baisse']['date_pic']} "
            f"au {stats['details']['pire_baisse']['date_creux']}), plancher "
            f"{_pct(seuils_profil['pire_baisse'])}.",
            mesure=pb, seuil=seuils_profil["pire_baisse"], reference=_ref(stats)))
    else:
        controles.append(_controle(
            "risque_historique", "information manquante",
            "Volatilité et pire baisse non calculées : corriger d'abord les poids ou les symboles."))

    if note_tolerance:
        controles.append(_controle("tolerance_risque", "à signaler", note_tolerance,
                                   mesure=profil["tolerance_risque"], seuil=tolerance))

    rejets = [c["controle"] for c in controles if c["statut"] == "non conforme"]
    return resultat(
        outil="verifier_contraintes",
        parametres={"portefeuille": {"poids": poids, "theme": theme}, "profil": profil,
                    "plafond_theme": plafond_theme, "debut": debut, "fin": fin},
        periode=next((c["reference"]["periode"] for c in controles if "reference" in c), {}),
        valeur=not rejets,
        unite="booléen : True si aucun contrôle n'est non conforme",
        formule="chaque contrôle compare une mesure à un seuil du profil ; un seul « non conforme » rejette",
        sources=[FICHIER_UNIVERS, "tools/gouvernance.py (SEUILS_PAR_TOLERANCE)"],
        details={
            "controles": controles,
            "rejets": rejets,
            "a_signaler": [c["controle"] for c in controles if c["statut"] == "à signaler"],
            "information_manquante": [c["controle"] for c in controles
                                      if c["statut"] == "information manquante"],
            "tolerance_retenue": tolerance,
            "horizon_retenu_annees": horizon,
            "seuils": {**seuils_profil, "theme": plafond_theme},
            "devise_calcul": devise_calcul,
            "hypotheses": "Seuils = paramètres du projet, réglables, pas une norme réglementaire.",
            "limites": LIMITES,
        },
    )
