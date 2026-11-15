"""Adéquation : chaque critère du profil vérifié contre un portefeuille simulé, par le code.

Une entrée par critère (`horizon`, `objectif`, `tolerance`, `capital`) et par élément de
`preferences`, `exclusions` et `centres_interet`. Chaque réponse cite au moins un chiffre de
`tools/` par un repère `{id}`. Un critère que l'univers ou les données ne couvrent pas s'écrit
« non couvert », avec la raison : on ne le déclare jamais respecté par défaut.

Les règles (bandes de part risquée par objectif, etc.) sont des hypothèses de l'équipe, écrites
dans `regle` à côté de chaque verdict.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from agents.journal import Journal, cle
from agents.profil import Profil
from tools import esg as esg_outils
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE

RACINE = Path(__file__).resolve().parents[1]
FICHIER_THEMES = RACINE / "data" / "themes.csv"
FICHIER_FONDAMENTAUX = RACINE / "data" / "fondamentaux.csv"
RESPECTE, PARTIEL, NON_COUVERT = "respecté", "partiel", "non couvert"
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")

# Bandes de part risquée (actions, FNB d'actions, crypto) par objectif. Hypothèses de l'équipe.
BANDES_OBJECTIF: dict[str, tuple[float, float]] = {
    "préservation du capital": (0.0, 0.40),
    "équilibre": (0.30, 0.70),
    "croissance": (0.50, 1.00),
}

# Faute de data/themes.csv, un centre d'intérêt en texte libre est relié à un secteur de la
# colonne `sector` de data/assets_universe.csv par des mots-clés. Les symboles viennent ensuite
# de la table sourcée, jamais de la mémoire d'un modèle.
MOTS_CLES_SECTEUR: dict[str, tuple[str, ...]] = {
    "Information Technology": ("techno", "technologie", "technologies", "informatique", "logiciel", "logiciels",
                               "ia", "intelligence artificielle", "semi conducteur", "semi conducteurs", "puce",
                               "puces", "numerique"),
    "Financials": ("banque", "banques", "finance", "financier", "financiere", "assurance", "assurances"),
    "Energy": ("energie", "energies", "petrole", "gaz", "pipeline", "pipelines", "petroliere", "petrolieres"),
    "Health Care": ("sante", "pharma", "pharmaceutique", "medicament", "medicaments", "soins"),
    "Utilities": ("services publics", "electricite", "utilites"),
    "Consumer Staples": ("consommation de base", "alimentation", "epicerie", "depanneur", "biens de consommation"),
    "Consumer Discretionary": ("automobile", "voiture", "voitures", "vehicule electrique", "vehicules electriques",
                               "commerce en ligne"),
    "Communication Services": ("internet", "moteur de recherche", "reseaux sociaux", "publicite en ligne"),
    "Industrials": ("rail", "chemin de fer", "transport", "industrie", "industriel"),
}
MOTS_CLES_CRYPTO = ("crypto", "cryptos", "cryptomonnaie", "cryptomonnaies", "cryptoactif", "cryptoactifs",
                    "bitcoin", "ethereum", "blockchain")
MOTS_FOSSILE = ("fossile", "fossiles", "petrole", "petrolieres", "petroliere", "gaz", "charbon")
MOTS_CONTROVERSE = ("controverse", "controverses", "esg", "responsable", "durable", "ethique")
MOTS_REVENU = ("dividende", "dividendes", "revenu", "revenus", "rente")
MOTS_CANADA = ("canada", "canadien", "canadienne", "canadiens", "canadiennes", "quebec")
MOTS_DIVERSIFICATION = ("diversification", "diversifie", "diversifier")


def normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def contient(texte: str, mots: tuple[str, ...]) -> bool:
    t = f" {normaliser(texte)} "
    return any(f" {m} " in t for m in mots)


SOURCE_UNIVERS = "data/assets_universe.csv, data/univers_etendu.csv"


def table_themes() -> pd.DataFrame | None:
    """data/themes.csv s'il existe (colonnes `theme`, `synonymes`, `symbole`…), sinon None."""
    if not FICHIER_THEMES.is_file():
        return None
    t = pd.read_csv(FICHIER_THEMES, dtype=str, keep_default_na=False)
    return t if {"theme", "symbole"} <= set(t.columns) else None


def theme_de(interet: str) -> dict[str, Any] | None:
    """Le thème de data/themes.csv qui correspond à un centre d'intérêt en texte libre (nom ou synonyme)."""
    themes = table_themes()
    if themes is None:
        return None
    table = univers(etendu=True)
    for nom, lignes in themes.groupby("theme", sort=False):
        termes = [nom] + [x for s in lignes.get("synonymes", pd.Series(dtype=str)) for x in str(s).split(";") if x.strip()]
        if contient(interet, tuple(normaliser(x) for x in termes)):
            symboles = [s for s in lignes["symbole"] if s in table.index]
            if symboles:
                premiere = lignes.iloc[0]
                return {"type": "table_themes", "theme": nom, "symboles": symboles, "source": "data/themes.csv",
                        "source_url": premiere.get("source_url") or None, "source_date": premiere.get("source_date") or None,
                        "roles": dict(zip(lignes["symbole"], lignes.get("role", [""] * len(lignes))))}
    return None


def relier_interet(interet: str) -> dict[str, Any]:
    """Ce qu'un centre d'intérêt désigne dans l'univers sourcé : secteur, crypto, ou rien."""
    table = univers(etendu=True)
    lien = theme_de(interet)
    if lien:
        return lien
    if contient(interet, MOTS_CLES_CRYPTO):
        return {"type": "crypto", "symboles": [s for s in table.index if table.at[s, "asset_class"] == "crypto"],
                "source": SOURCE_UNIVERS}
    for secteur, mots in MOTS_CLES_SECTEUR.items():
        if contient(interet, mots):
            membres = [s for s in table.index if table.at[s, "sector"] == secteur and table.at[s, "asset_class"] == "equity"]
            return {"type": "secteur", "secteur": secteur, "symboles": membres, "source": SOURCE_UNIVERS}
    raison = (("ni thème de data/themes.csv ni " if FICHIER_THEMES.is_file() else "data/themes.csv absent ; aucun ")
              + f"secteur de l'univers sourcé ne correspond à « {interet} »")
    return {"type": "non couvert", "symboles": [], "raison": raison}


# --- chiffres ---------------------------------------------------------------------------------

def _ref(outil: str, parametres: dict[str, Any], valeur: float, unite: str, formule: str, sources: list[str],
         nature: str, periode: dict[str, Any] | None = None, **details: Any) -> dict[str, Any]:
    return {"outil": outil, "parametres": parametres,
            "periode": periode or {"debut": None, "fin": None, "observations": None},
            "valeur": float(valeur), "unite": unite, "formule": formule, "sources": sources,
            "details": {"nature": nature, **details}}


def mesures_portefeuille(j: Journal, ident: str, poids: dict[str, float], devise: str) -> dict[str, Any]:
    """Statistiques et parts du risque d'un portefeuille, mesurées une fois par tools/."""
    cache = getattr(j, "_cache_ptf", None)
    if cache is None:
        cache = j._cache_ptf = {}
    cle_cache = (ident, tuple(sorted(poids.items())), devise)
    if cle_cache in cache:
        return cache[cle_cache]
    st = j.mesurer("stats_portefeuille", cle("ptf", ident), poids=poids, devise=devise)
    parts = j.mesurer("parts_du_risque", cle("part", ident), poids=poids, devise=devise)
    ref = j.chiffres[st["volatilite"]]
    pb = ref["details"]["pire_baisse"]
    fin = ref["periode"]["fin"]
    fin_baisse = pb.get("date_retour") or fin
    duree = (date.fromisoformat(fin_baisse) - date.fromisoformat(pb["date_pic"])).days / 365.25
    duree_id = j.enregistrer(cle("ptf", ident, "duree_pire_baisse"), {
        **{k: ref[k] for k in ("outil", "parametres", "periode", "sources")},
        "valeur": duree, "unite": "années", "champ": "duree_pire_baisse",
        "formule": "(date de retour au sommet, ou fin de la fenêtre si pas de retour) − date du sommet, en années",
        "details": {"date_pic": pb["date_pic"], "date_creux": pb["date_creux"], "date_retour": pb.get("date_retour"),
                    "fin_fenetre": fin, "retour_au_sommet": pb.get("date_retour") is not None}})
    m = {"stats": st, "parts": parts, "duree": duree_id, "duree_annees": duree,
         "retour": pb.get("date_retour") is not None, "details": ref["details"], "periode": ref["periode"]}
    cache[cle_cache] = m
    return m


def part_risquee(poids: dict[str, float]) -> float:
    table = univers(etendu=True)
    return sum(w for s, w in poids.items() if s in table.index and table.at[s, "asset_class"] in CLASSES_RISQUEES)


def _entree(critere: str, element: str | None, attente: str, reponse: str, statut: str, chiffres: list[str],
            regle: str, raison: str | None = None) -> dict[str, Any]:
    if statut == NON_COUVERT and not raison:
        raise ValueError(f"{critere} : « non couvert » exige une raison")
    return {"critere": critere, "element": element, "attente": attente, "reponse": reponse, "statut": statut,
            "raison": raison, "chiffres": chiffres, "regle": regle}


# --- critères ---------------------------------------------------------------------------------

def evaluer(profil: Profil, poids: dict[str, float], j: Journal, ident: str,
            ids_limites: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Adéquation d'un portefeuille simulé (`poids`) au profil. Écrit ses chiffres dans `j`."""
    table = univers(etendu=True)
    devise = "CAD" if profil.devise == "CAD" else "cotation"
    m = mesures_portefeuille(j, ident, poids, devise)
    vol, pb = m["stats"]["volatilite"], m["stats"]["pire_baisse"]
    seuils = SEUILS_PAR_TOLERANCE[profil.tolerance_risque]
    entrees: list[dict[str, Any]] = []

    # Horizon : la pire baisse du portefeuille a-t-elle été effacée dans un délai plus court que l'horizon ?
    h = profil.horizon_annees
    ok = m["retour"] and m["duree_annees"] <= h
    retour = "retour au sommet" if m["retour"] else "pas encore de retour au sommet à la fin de la fenêtre"
    entrees.append(_entree(
        "horizon", None, f"Pouvoir attendre {h} an(s) sans avoir besoin du capital.",
        f"Pire baisse du portefeuille simulé {{{pb}}}, du sommet au {retour} : {{{m['duree']}}} an(s).",
        RESPECTE if ok else PARTIEL, [pb, m["duree"]],
        "respecté si la pire baisse historique a été effacée en moins de temps que l'horizon"))

    # Objectif : bande de part risquée, et pour la préservation, pire baisse sous le seuil.
    risquee = part_risquee(poids)
    rid = j.enregistrer(cle("risquee", ident), _ref(
        "agents.adequation.part_risquee", {"portefeuille": ident}, risquee, "fraction du capital",
        "Σ poids des actions, FNB d'actions et cryptoactifs", [f"{SOURCE_UNIVERS} (asset_class)"],
        "calcul sur les poids décidés par le constructeur"))
    if profil.objectif == "revenu":
        raison = ("aucune donnée de dividendes ni de fondamentaux dans data/ "
                  + ("(data/fondamentaux.csv présent mais non branché)" if FICHIER_FONDAMENTAUX.is_file()
                     else "(data/fondamentaux.csv absent : information manquante)"))
        entrees.append(_entree("objectif", None, "Tirer un revenu régulier du capital.",
                               f"Le rendement en revenu des lignes n'est pas mesurable. Part risquée : {{{rid}}}.",
                               NON_COUVERT, [rid], "revenu mesuré par les dividendes", raison))
    else:
        bas, haut = BANDES_OBJECTIF[profil.objectif]
        dans_bande = bas - 1e-9 <= risquee <= haut + 1e-9
        ok = dans_bande and (profil.objectif != "préservation du capital" or j.chiffres[pb]["valeur"] >= seuils["pire_baisse"])
        attentes = {"préservation du capital": "Préserver le capital : peu d'actifs risqués, baisses limitées.",
                    "équilibre": "Équilibrer croissance et stabilité.",
                    "croissance": "Faire croître le capital : une part importante d'actifs de croissance."}
        reponse = f"Part risquée (actions, FNB d'actions, crypto) : {{{rid}}} ; volatilité {{{vol}}}."
        if profil.objectif == "préservation du capital":
            reponse += f" Pire baisse {{{pb}}}."
        entrees.append(_entree(
            "objectif", None, attentes[profil.objectif], reponse, RESPECTE if ok else PARTIEL, [rid, vol, pb],
            f"part risquée entre {bas:.0%} et {haut:.0%} du capital".replace("%", " %")
            + (" et pire baisse au-dessus du seuil du profil" if profil.objectif == "préservation du capital" else "")))

    # Tolérance au risque : volatilité et pire baisse du portefeuille face aux seuils.
    sv, sp = (ids_limites or {}).get("volatilite"), (ids_limites or {}).get("pire_baisse")
    ok = j.chiffres[vol]["valeur"] <= seuils["volatilite"] and j.chiffres[pb]["valeur"] >= seuils["pire_baisse"]
    entrees.append(_entree(
        "tolerance", None, f"Un risque « {profil.tolerance_risque} ».",
        f"Volatilité {{{vol}}}" + (f" pour un seuil de {{{sv}}}" if sv else "") + f" ; pire baisse {{{pb}}}"
        + (f" pour un plancher de {{{sp}}}." if sp else "."),
        RESPECTE if ok else PARTIEL, [x for x in (vol, pb, sv, sp) if x],
        "volatilité sous le seuil et pire baisse au-dessus du plancher de la tolérance"))

    # Capital : ce que la pire baisse aurait représenté en dollars.
    montant = j.enregistrer(cle("montant_pb", ident), _ref(
        "agents.adequation.montant", {"capital_fictif": profil.capital_fictif, "pire_baisse": pb},
        profil.capital_fictif * j.chiffres[pb]["valeur"], f"montant en {profil.devise}",
        "capital fictif × pire baisse du portefeuille", ["stats_portefeuille", "profil.capital_fictif"],
        "calcul sur un chiffre de tools/", periode=j.chiffres[pb]["periode"]))
    entrees.append(_entree(
        "capital", None, f"Un capital fictif de {profil.capital_fictif:,.0f} {profil.devise}.".replace(",", " "),
        f"Sur la fenêtre, la pire baisse aurait représenté {{{montant}}} {profil.devise} pour ce capital.",
        RESPECTE, [montant, pb], "le capital fixe l'échelle ; la perte en dollars est montrée telle quelle"))

    entrees += _preferences(profil, poids, j, ident, m)
    entrees += _exclusions(profil, poids, j, ident)
    entrees += _interets(profil, poids, j, ident, m)
    return entrees


def _transparence(j: Journal, ident: str, poids: dict[str, float], critere: str) -> tuple[str, str, dict]:
    res = esg_outils.exposition_transparente(poids, critere)
    base = {k: res[k] for k in ("outil", "parametres", "periode", "unite", "formule", "sources", "details")}
    v = j.enregistrer(cle("transp", ident, critere), {**base, "valeur": res["valeur"]})
    inc = j.enregistrer(cle("transp", ident, critere, "inconnu"), {
        **base, "valeur": res["details"]["part_inconnue"], "champ": "part_inconnue",
        "unite": "fraction du capital dont le statut n'est pas connu"})
    return v, inc, res["details"]


def _verdict_transparence(d: dict, valeur: float) -> str:
    if d["directe"] > 1e-9:
        return PARTIEL
    if valeur > 1e-9 or d["part_inconnue"] > 1e-9:
        return PARTIEL
    return RESPECTE


def _preferences(profil: Profil, poids: dict[str, float], j: Journal, ident: str, m: dict) -> list[dict[str, Any]]:
    table = univers(etendu=True)
    if not profil.preferences:
        return [_entree("preferences", None, "Aucune préférence déclarée.",
                        f"Rien à vérifier. Volatilité du portefeuille : {{{m['stats']['volatilite']}}}.",
                        RESPECTE, [m["stats"]["volatilite"]], "aucune")]
    sortie = []
    for pref in profil.preferences:
        if contient(pref, MOTS_CONTROVERSE):
            v, inc, d = _transparence(j, ident, poids, "controverse")
            sortie.append(_entree(
                "preferences", pref, f"« {pref} » : éviter les sociétés à controverse documentée.",
                f"Exposition à des sociétés à controverse documentée, en direct et à travers les FNB : {{{v}}} du capital ; "
                f"statut inconnu : {{{inc}}}.", _verdict_transparence(d, j.chiffres[v]["valeur"]), [v, inc],
                "respecté si aucune exposition et aucune part inconnue (data/esg_actions.csv, data/fnb_composition.csv)"))
        elif contient(pref, MOTS_REVENU):
            sortie.append(_entree("preferences", pref, f"« {pref} ».", "Les dividendes ne sont pas mesurés.", NON_COUVERT,
                                  [], "revenu mesuré par les dividendes",
                                  "aucune donnée de dividendes ; data/fondamentaux.csv absent : information manquante"))
        elif contient(pref, MOTS_CANADA):
            cad = sum(w for s, w in poids.items() if table.at[s, "currency"] == "CAD")
            cid = j.enregistrer(cle("expo_cad", ident), _ref(
                "agents.adequation.exposition_devise", {"portefeuille": ident, "devise": "CAD"}, cad,
                "fraction du capital", "Σ poids des lignes cotées en CAD", [f"{SOURCE_UNIVERS} (currency)"],
                "calcul sur les poids décidés par le constructeur"))
            sortie.append(_entree("preferences", pref, f"« {pref} » : privilégier le Canada.",
                                  f"Part du capital cotée en dollars canadiens : {{{cid}}}.",
                                  RESPECTE if cad >= 0.5 else PARTIEL, [cid],
                                  "respecté si au moins la moitié du capital est cotée au Canada"))
        elif contient(pref, MOTS_DIVERSIFICATION):
            sans = j.enregistrer(cle("ptf", ident, "vol_sans_diversification"), {
                **{k: j.chiffres[m["stats"]["volatilite"]][k] for k in ("outil", "parametres", "periode", "sources")},
                "valeur": m["details"]["volatilite_sans_diversification"], "unite": "fraction annualisée",
                "champ": "volatilite_sans_diversification", "formule": "Σ wᵢ σᵢ (toutes les corrélations à 1)",
                "details": {"nature": "fait mesuré"}})
            gain = m["details"]["effet_diversification"] > 0
            sortie.append(_entree("preferences", pref, f"« {pref} ».",
                                  f"Volatilité {{{m['stats']['volatilite']}}}, contre {{{sans}}} si toutes les lignes "
                                  "bougeaient ensemble.", RESPECTE if gain and len(poids) >= 5 else PARTIEL,
                                  [m["stats"]["volatilite"], sans], "les corrélations réduisent la volatilité, cinq lignes au moins"))
        else:
            sortie.append(_entree("preferences", pref, f"« {pref} ».", "Cette préférence n'est pas vérifiable.",
                                  NON_COUVERT, [], "aucune",
                                  f"aucune donnée de data/ ne permet de vérifier « {pref} »"))
    return sortie


def _exclusions(profil: Profil, poids: dict[str, float], j: Journal, ident: str) -> list[dict[str, Any]]:
    table = univers(etendu=True)
    if not profil.exclusions:
        return [_entree("exclusions", None, "Aucune exclusion déclarée.", "Rien à écarter.", RESPECTE, [], "aucune")]
    sortie = []
    noms = {normaliser(table.at[s, "name"]): s for s in table.index}
    for terme in profil.exclusions:
        symbole = terme.strip().upper() if terme.strip().upper() in table.index else next(
            (s for n, s in noms.items() if normaliser(terme) and normaliser(terme) in n), None)
        if contient(terme, MOTS_FOSSILE) or contient(terme, MOTS_CONTROVERSE) and not symbole:
            critere = "activite_fossile" if contient(terme, MOTS_FOSSILE) else "controverse"
            v, inc, d = _transparence(j, ident, poids, critere)
            libelle = "activité fossile" if critere == "activite_fossile" else "controverse documentée"
            sortie.append(_entree(
                "exclusions", terme, f"Écarter « {terme} ».",
                f"Exposition à des sociétés avec {libelle}, en direct et à travers les FNB : {{{v}}} du capital ; "
                f"statut inconnu : {{{inc}}}.", _verdict_transparence(d, j.chiffres[v]["valeur"]), [v, inc],
                "respecté si aucune exposition, directe ou via un FNB, et aucune part inconnue"))
        elif symbole:
            res = esg_outils.exposition_titre(poids, symbole)
            t = j.enregistrer(cle("titre", ident, symbole), {**{k: res[k] for k in (
                "outil", "parametres", "periode", "unite", "formule", "sources", "details")}, "valeur": res["valeur"]})
            statut = RESPECTE if res["valeur"] <= 1e-9 else PARTIEL
            sortie.append(_entree("exclusions", terme, f"Écarter {symbole}.",
                                  f"Exposition à {symbole}, en direct et à travers les FNB : {{{t}}} du capital.",
                                  statut, [t], "respecté si l'exposition directe et via les FNB est nulle"))
        elif contient(terme, MOTS_CLES_CRYPTO):
            crypto = sum(w for s, w in poids.items() if table.at[s, "asset_class"] == "crypto")
            cid = j.enregistrer(cle("crypto", ident), _ref(
                "agents.adequation.part_classe", {"portefeuille": ident, "classe": "crypto"}, crypto, "fraction du capital",
                "Σ poids des cryptoactifs", [SOURCE_UNIVERS], "calcul sur les poids décidés"))
            sortie.append(_entree("exclusions", terme, f"Écarter « {terme} ».", f"Crypto : {{{cid}}} du capital.",
                                  RESPECTE if crypto == 0 else PARTIEL, [cid], "respecté si aucune crypto"))
        else:
            secteur = next((s for s, mots in MOTS_CLES_SECTEUR.items() if contient(terme, mots)), None)
            if secteur is None:
                sortie.append(_entree("exclusions", terme, f"Écarter « {terme} ».", "Exclusion non vérifiable.",
                                      NON_COUVERT, [], "aucune",
                                      f"aucune donnée de data/ ne dit quels actifs relèvent de « {terme} »"))
                continue
            direct = sum(w for s, w in poids.items() if table.at[s, "sector"] == secteur and table.at[s, "asset_class"] == "equity")
            fnb = [s for s in poids if table.at[s, "asset_class"] == "etf_equity"]
            sid = j.enregistrer(cle("secteur", ident, secteur), _ref(
                "agents.adequation.part_secteur", {"portefeuille": ident, "secteur": secteur}, direct,
                "fraction du capital", "Σ poids des actions détenues en direct du secteur",
                [f"{SOURCE_UNIVERS} (sector)"], "calcul sur les poids décidés"))
            statut = PARTIEL if direct > 0 or fnb else RESPECTE
            sortie.append(_entree(
                "exclusions", terme, f"Écarter le secteur {secteur}.",
                f"Actions du secteur {secteur} détenues en direct : {{{sid}}}."
                + (f" Les FNB {', '.join(fnb)} peuvent en contenir : non mesuré par secteur." if fnb else ""),
                statut, [sid], "respecté si aucune action du secteur en direct et aucun FNB d'actions"))
    return sortie


def _interets(profil: Profil, poids: dict[str, float], j: Journal, ident: str, m: dict) -> list[dict[str, Any]]:
    if not profil.centres_interet:
        return [_entree("centres_interet", None, "Aucun centre d'intérêt déclaré.", "Pas de thème.", RESPECTE, [],
                        "aucune")]
    sortie = []
    for interet in profil.centres_interet:
        lien = relier_interet(interet)
        if lien["type"] == "non couvert":
            sortie.append(_entree("centres_interet", interet, f"Une inclinaison vers « {interet} ».",
                                  "Aucun actif de l'univers ne correspond : pas d'inclinaison.", NON_COUVERT, [],
                                  "thème relié à un secteur de l'univers sourcé", lien["raison"]))
            continue
        membres = [s for s in lien["symboles"] if poids.get(s, 0) > 0]
        part = sum(poids[s] for s in membres)
        pid = j.enregistrer(cle("interet", ident, normaliser(interet)), _ref(
            "agents.adequation.part_theme", {"portefeuille": ident, "interet": interet, "symboles": lien["symboles"]},
            part, "fraction du capital", "Σ poids des lignes de l'univers reliées au centre d'intérêt",
            [lien["source"]], "calcul sur les poids décidés"))
        risque = [m["parts"][s] for s in membres if s in m["parts"]]
        quoi = lien.get("secteur") or (f"thème « {lien['theme']} », data/themes.csv" if lien.get("theme") else "crypto")
        reponse = (f"Lignes liées à « {interet} » ({quoi}) : {', '.join(membres)}, {{{pid}}} du capital"
                   + (", part du risque " + ", ".join(f"{s} {{{r}}}" for s, r in zip(membres, risque)) if risque else "")
                   + "." if membres else f"Aucune ligne liée à « {interet} » ({quoi}) n'a été retenue : {{{pid}}}.")
        sortie.append(_entree("centres_interet", interet, f"Une inclinaison vers « {interet} », plafonnée.", reponse,
                              RESPECTE if membres else PARTIEL, [pid, *risque],
                              "respecté si au moins une ligne reliée est retenue, sous son plafond"))
    return sortie
