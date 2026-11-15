"""Données des graphiques de l'interface, calculées depuis les fichiers du dépôt.

    python web/scripts/graphiques.py          (depuis la racine du dépôt)

Écrit web/data/graphiques/<persona>.json pour robert, amira et mateo :

- répartitions des portefeuilles (par actif, par secteur, par zone), à partir
  des poids de agents/sorties/<persona>.json et de data/assets_universe.csv
  (colonnes sector et market). Chaque part est un chiffre avec sa référence,
  au même format que la table « chiffres » du pipeline ;
- cours hebdomadaire de l'actif visé par la demande (data/prices_daily.csv,
  adj_close, dernier cours de chaque semaine), plus les jours du sommet et
  du creux donnés par le chiffre pire_baisse du pipeline.

Aucun chiffre n'est écrit à la main : tout vient de ces fichiers.
"""

import csv
import datetime
import json
import re
from collections import OrderedDict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
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
    "Gold": "Or",
    "Crypto asset": "Crypto",
}


def secteur(ligne):
    s = ligne["sector"]
    if s.startswith("Broad market"):
        return "Actions, marché large (FNB)"
    if s.startswith("Bonds"):
        return "Obligations (FNB)"
    return SECTEURS.get(s, s)


def zone(ligne):
    if ligne["asset_class"] == "crypto":
        return "Crypto, à part"
    if ligne["asset_class"] == "etf_commodity":
        return "Or, à part"
    return "Canada" if ligne["market"] == "TSX" else "États-Unis"


REGLE_ZONE = "market TSX = Canada, autres marchés = États-Unis ; crypto et or à part"


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
    """Pour les analyses en direct (POST /analyse) : secteur et zone de chaque
    actif de l'univers, et son cours hebdomadaire ajusté."""
    tous = {s: [] for s in univers}
    with PRIX.open(encoding="utf-8") as f:
        for l in csv.DictReader(f):
            if l["ticker"] in tous and l["adj_close"]:
                tous[l["ticker"]].append((l["date"], float(l["adj_close"]), l["currency"]))
    sortie = {}
    for s, u in univers.items():
        semaines = OrderedDict()
        jours = {}
        for date, valeur, devise in sorted(tous[s]):
            a, n, _ = datetime.date.fromisoformat(date).isocalendar()
            semaines[(a, n)] = (date, valeur)
            jours[date] = valeur
        sortie[s] = {
            "nom": u["name"],
            "classe": u["asset_class"],
            "secteur": secteur(u),
            "zone": zone(u),
            "devise": tous[s][0][2] if tous[s] else u["currency"],
            "hebdo": [list(p) for p in semaines.values()],
            "jours": jours,
        }
    return sortie


def main():
    univers = {l["ticker"]: l for l in csv.DictReader(UNIVERS.open(encoding="utf-8"))}
    direct = tables_en_direct(univers)
    for s, d in direct.items():
        d.pop("jours")
    (DESTINATION.parent / "univers.json").write_text(json.dumps({
        "note": f"Calculé par {OUTIL} depuis data/assets_universe.csv (sector, market) et data/prices_daily.csv "
                "(adj_close, dernier cours de chaque semaine). " + REGLE_ZONE + ".",
        "actifs": direct,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    voulus = set(CIBLES.values())
    prix = {s: [] for s in voulus}
    devises = {}
    with PRIX.open(encoding="utf-8") as f:
        for l in csv.DictReader(f):
            if l["ticker"] in voulus and l["adj_close"]:
                prix[l["ticker"]].append((l["date"], float(l["adj_close"])))
                devises[l["ticker"]] = l["currency"]
    for s in prix.values():
        s.sort()
    prix["_devise"] = devises
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for persona, symbole in CIBLES.items():
        sortie = json.loads((SORTIES / f"{persona}.json").read_text(encoding="utf-8"))
        reps, chiffres = repartitions(persona, sortie, univers)
        donnees = {
            "note": f"Calculé par {OUTIL} depuis agents/sorties/{persona}.json, "
            "data/assets_universe.csv et data/prices_daily.csv.",
            "repartitions": reps,
            "cours": cours(symbole, sortie, prix) | {"nom": univers[symbole]["name"]},
            "chiffres": chiffres,
        }
        chemin = DESTINATION / f"{persona}.json"
        chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(chemin.relative_to(RACINE), len(chiffres), "parts,", len(donnees["cours"]["points"]), "points")


if __name__ == "__main__":
    main()
