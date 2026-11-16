"""Données des graphiques de l'interface, calculées depuis les fichiers du dépôt.

    python web/scripts/graphiques.py          (depuis la racine du dépôt)

Écrit web/data/univers.json : secteur, zone et cours hebdomadaire de TOUS les actifs que le
pipeline peut retenir (univers de départ et univers étendu, thèmes compris, lus par
tools.donnees). Une analyse en direct d'un profil quelconque s'affiche donc comme un persona.

Écrit aussi web/data/graphiques/<persona>.json pour robert, amira et mateo :

- répartitions des portefeuilles (par actif, par secteur, par zone), à partir
  des poids de agents/sorties/<persona>.json et de data/assets_universe.csv
  (colonnes sector et market). Chaque part est un chiffre avec sa référence,
  au même format que la table « chiffres » du pipeline ;
- cours hebdomadaire de l'actif visé par la demande (data/prices_daily.csv,
  adj_close, dernier cours de chaque semaine), plus les jours du sommet et
  du creux donnés par le chiffre pire_baisse du pipeline ;
- éventail de scénarios du portefeuille retenu (tools.scenarios.eventail_scenarios, par
  agents.serveur.scenarios_du_portefeuille), pour que la démonstration l'affiche sans serveur.

Aucun chiffre n'est écrit à la main : tout vient de ces fichiers.
"""

import csv
import datetime
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from agents.serveur import scenarios_du_portefeuille, scenarios_par_portefeuille  # noqa: E402
from agents.traduction import enregistrer_memoire, traduire_sortie  # noqa: E402
from tools.donnees import charger_prix, fichier_prix, univers as table_univers  # noqa: E402

SORTIES = RACINE / "agents" / "sorties"
UNIVERS = RACINE / "data" / "assets_universe.csv"
PRIX = RACINE / "data" / "prices_daily.csv"
DESTINATION = RACINE / "web" / "data" / "graphiques"
OUTIL = "web/scripts/graphiques.py"

# Actif visé par la demande de chaque persona (demande_analysee.symboles quand
# le pipeline l'a lu ; Amira demande « la crypto », lue ici comme le Bitcoin).
CIBLES = {"robert": "TSLA", "amira": "BTC-USD", "mateo": "TSLA"}

SECTEURS = {
    "Financials": "Finance",
    "Energy": "Énergie",
    "Industrials": "Industrie",
    "Utilities": "Services publics",
    "Consumer Staples": "Consommation de base",
    "Consumer Discretionary": "Consommation discrétionnaire",
    "Information Technology": "Technologies de l'information",
    "Communication Services": "Communications",
    "Health Care": "Santé",
    "Real Estate": "Immobilier",
    "Gold": "Or",
    "Crypto asset": "Crypto",
}


def secteur(ligne):
    s = ligne["sector"]
    if s.startswith("Broad market"):
        return "Actions, marché large (FNB)"
    if s.startswith("Bonds"):
        return "Obligations (FNB)"
    if s.startswith("Theme:"):
        return "FNB thématique"
    if s.startswith(INTERNATIONAL):
        return "Actions internationales (FNB)"
    return SECTEURS.get(s, s)


# Débuts de la colonne sector des FNB d'actions hors Amérique du Nord (data/univers_etendu.csv).
INTERNATIONAL = ("International developed", "Europe developed", "Emerging markets")


def zone(ligne):
    """Zone d'un actif. Un titre : son marché de cotation. Un FNB dont la colonne sector décrit
    un indice hors Amérique du Nord ou mondial : la zone de cet indice, pas celle de la bourse."""
    if ligne["asset_class"] == "crypto":
        return "Crypto, à part"
    if ligne["asset_class"] == "etf_commodity":
        return "Or, à part"
    s = ligne["sector"]
    if s.startswith("Europe developed"):
        return "Europe"
    if s.startswith("International developed"):
        return "International développé, à part"
    if s.startswith("Emerging markets"):
        return "Marchés émergents, à part"
    if s.startswith("Theme:") and "Global" in s:
        return "Monde (FNB thématique), à part"
    return "Canada" if ligne["market"] == "TSX" else "États-Unis"


REGLE_ZONE = ("market TSX = Canada, autres marchés = États-Unis ; un FNB dont l'indice (colonne sector) est "
              "européen, international, émergent ou mondial prend la zone de cet indice ; crypto et or à part")


def cle(texte):
    t = texte.lower()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ç", "c"), ("'", "")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def repartitions(persona, sortie, univers):
    chiffres = {}
    resultat = {}
    for ptf in sortie["portefeuilles"]:
        poids = {l["symbole"]: l["poids"] for l in ptf["lignes"]}
        pid = ptf["id"].lower()
        resultat[ptf["id"]] = {}
        for regroupement, fonction, colonne in (
            ("actif", lambda u: u["ticker"], "ticker"),
            ("secteur", secteur, "sector"),
            ("zone", zone, "market, asset_class"),
        ):
            groupes = OrderedDict()
            for symbole, p in sorted(poids.items(), key=lambda kv: -kv[1]):
                g = fonction(univers[symbole])
                groupes.setdefault(g, []).append(symbole)
            parts = []
            for g, symboles in sorted(groupes.items(), key=lambda kv: -sum(poids[s] for s in kv[1])):
                ident = f"rep_{pid}_{regroupement}_{cle(g)}"
                valeur = round(sum(poids[s] for s in symboles), 10)
                chiffres[ident] = {
                    "outil": f"{OUTIL} (repartition)",
                    "parametres": {
                        "portefeuille": ptf["id"],
                        "regroupement": regroupement,
                        "groupe": g,
                        "poids": {s: poids[s] for s in symboles},
                    },
                    "periode": {"debut": None, "fin": None, "observations": None},
                    "valeur": valeur,
                    "unite": "fraction du capital",
                    "formule": "somme des poids des lignes du groupe"
                    + (f" ({REGLE_ZONE})" if regroupement == "zone" else ""),
                    "sources": [
                        f"agents/sorties/{persona}.json (portefeuille {ptf['id']}, poids)",
                        f"data/assets_universe.csv ({colonne})",
                    ],
                    "details": {
                        "nature": "répartition du capital fictif, pas une mesure de marché",
                        "symboles": symboles,
                    },
                }
                parts.append({"libelle": g, "id": ident, "symboles": symboles})
            resultat[ptf["id"]][regroupement] = parts
    return resultat, chiffres


def cours(symbole, sortie, prix):
    ref = sortie["chiffres"][f"pb_{cle(symbole)}"]
    pic, creux = ref["details"]["date_pic"], ref["details"]["date_creux"]
    serie = prix[symbole]
    semaines = OrderedDict()
    for date, valeur in serie:
        a, s, _ = datetime.date.fromisoformat(date).isocalendar()
        semaines[(a, s)] = (date, valeur)
    points = dict(semaines.values())
    jours = dict(serie)
    points[pic] = jours[pic]
    points[creux] = jours[creux]
    return {
        "symbole": symbole,
        "id": cle(symbole),
        "points": sorted(points.items()),
        "date_pic": pic,
        "date_creux": creux,
        "reference": f"pb_{cle(symbole)}",
        "sources": ["data/prices_daily.csv (adj_close, dernier cours de chaque semaine)"],
        "devise": prix["_devise"][symbole],
    }


def tables_en_direct(univers):
    """Pour les analyses en direct (POST /analyse) : secteur et zone de chaque actif que le
    pipeline peut retenir, et son cours hebdomadaire ajusté (tools.donnees.charger_prix)."""
    prix = charger_prix(list(univers))
    sortie = {}
    for s, u in univers.items():
        serie = prix[s].dropna()
        semaines = OrderedDict()
        for date, valeur in serie.items():
            a, n, _ = date.isocalendar()
            semaines[(a, n)] = (date.date().isoformat(), float(valeur))
        sortie[s] = {
            "nom": u["name"],
            "classe": u["asset_class"],
            "secteur": secteur(u),
            "zone": zone(u),
            "devise": u["currency"],
            "source": f"data/{fichier_prix(s)}",
            "hebdo": [list(p) for p in semaines.values()],
        }
    return sortie


def lire_univers():
    """Univers de départ et univers étendu (tools.donnees), une fiche par symbole."""
    return {t: {"ticker": t, **{k: ("" if v is None else str(v)) for k, v in ligne.items()}}
            for t, ligne in table_univers(etendu=True).fillna("").to_dict("index").items()}


def main():
    univers = lire_univers()
    direct = tables_en_direct(univers)
    (DESTINATION.parent / "univers.json").write_text(json.dumps({
        "note": f"Calculé par {OUTIL} depuis data/assets_universe.csv et data/univers_etendu.csv (sector, market), "
                "data/prices_daily.csv et data/base/prix_etendus.csv (adj_close, dernier cours de chaque semaine). "
                + REGLE_ZONE + ".",
        "actifs": direct,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    print("web/data/univers.json", len(direct), "actifs")
    voulus = sorted(set(CIBLES.values()))
    large = charger_prix(voulus)
    prix = {s: [(d.date().isoformat(), float(v)) for d, v in large[s].dropna().items()] for s in voulus}
    prix["_devise"] = {s: univers[s]["currency"] for s in voulus}
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for persona, symbole in CIBLES.items():
        sortie = json.loads((SORTIES / f"{persona}.json").read_text(encoding="utf-8"))
        reps, chiffres = repartitions(persona, sortie, univers)
        donnees = {
            "note": f"Calculé par {OUTIL} depuis agents/sorties/{persona}.json, "
            "data/assets_universe.csv, data/univers_etendu.csv et les fichiers de cours.",
            "repartitions": reps,
            "cours": cours(symbole, sortie, prix) | {"nom": univers[symbole]["name"]},
            "chiffres": chiffres,
            "scenarios": scenarios_du_portefeuille(sortie),
            "scenarios_par_portefeuille": scenarios_par_portefeuille(sortie),
        }
        chemin = DESTINATION / f"{persona}.json"
        chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        # Option anglaise du site : les mêmes données, textes traduits (agents/traduction.py). Les textes
        # connus viennent de la mémoire agents/traductions/en.json ; un texte nouveau appelle le modèle,
        # et reste en français si le modèle ne répond pas. Aucun chiffre ne change.
        anglais = traduire_sortie(donnees | {"meta": {}}, "en")
        restes = anglais.pop("meta")["traduction"]["restes_en_francais"]
        (DESTINATION / "en").mkdir(exist_ok=True)
        (DESTINATION / "en" / f"{persona}.json").write_text(
            json.dumps(anglais, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if restes:
            print(f"  anglais : {restes} texte(s) resté(s) en français")
        print(chemin.relative_to(RACINE), len(chiffres), "parts,", len(donnees["cours"]["points"]), "points,",
              "scénarios" if donnees["scenarios"] else "sans scénarios")
    enregistrer_memoire()  # les traductions nouvelles servent aux prochaines fois, sans rappeler le modèle


if __name__ == "__main__":
    main()
