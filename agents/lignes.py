"""Lignes d'un portefeuille simulé : détail sourcé (par le code) et justification (par le constructeur).

- `detail_ligne` ajoute secteur, pays de cotation, devise, repères des chiffres et sources, depuis
  les tables de data/. Rien n'y vient d'un modèle.
- `controle_justifications` est un contrôle de gouvernance : une ligne sans justification liée au
  profil, sans repère chiffré, ou sans candidat écarté comparé, rejette le portefeuille.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from agents.journal import REPERE, Journal
from agents.profil import Profil
from tools import esg as esg_outils
from tools.donnees import univers

RACINE = Path(__file__).resolve().parents[1]
FICHIER_FONDAMENTAUX = RACINE / "data" / "fondamentaux.csv"
PAYS_PAR_MARCHE = {"TSX": "Canada", "NASDAQ": "États-Unis", "NYSE": "États-Unis", "NYSE Arca": "États-Unis",
                   "Cboe BZX": "États-Unis", "Crypto (24/7)": "sans pays, cotation continue"}
CRITERES = ("horizon", "objectif", "tolerance", "preferences", "exclusions", "centres_interet", "capital", "demande")


@lru_cache(maxsize=1)
def _metadonnees() -> pd.DataFrame:
    return pd.read_csv(RACINE / "data" / "sources_metadata.csv")


def _meta(fichier: str) -> dict[str, Any]:
    m = _metadonnees()
    ligne = m[m["file"] == fichier]
    if ligne.empty:
        return {"url": None, "date": None}
    r = ligne.iloc[0]
    url = r["source_url"] if isinstance(r["source_url"], str) else None
    return {"url": url, "date": r["retrieved_on"] if isinstance(r["retrieved_on"], str) else None,
            "source": r["source"] if isinstance(r["source"], str) else None}


FICHIER_COUVERTURE = RACINE / "data" / "base" / "couverture.csv"


def pays(symbole: str) -> str:
    marche = str(univers(etendu=True).at[symbole, "market"])
    if marche in PAYS_PAR_MARCHE:
        return PAYS_PAR_MARCHE[marche]
    return "États-Unis" if marche.startswith("U.S.") else "inconnu"


@lru_cache(maxsize=1)
def _couverture() -> pd.DataFrame | None:
    if not FICHIER_COUVERTURE.is_file():
        return None
    return pd.read_csv(FICHIER_COUVERTURE, dtype=str, keep_default_na=False).set_index("ticker")


def fondamentaux(symbole: str) -> dict[str, Any]:
    """Statut des fondamentaux d'une action : « information manquante » tant que data/fondamentaux.csv n'existe pas."""
    present = FICHIER_FONDAMENTAUX.is_file()
    cv = _couverture()
    note = cv.at[symbole, "fondamentaux_source"] if cv is not None and symbole in cv.index else None
    return {"statut": "fichier présent, non branché" if present else "information manquante",
            "fichier": "data/fondamentaux.csv", "couverture": note,
            "source_couverture": "data/base/couverture.csv" if note else None}


def sources_ligne(symbole: str, devise_profil: str) -> list[dict[str, Any]]:
    """D'où vient chaque information d'une ligne : fichier, adresse, date, objet."""
    table = univers(etendu=True)
    classe, devise = table.at[symbole, "asset_class"], table.at[symbole, "currency"]
    if table.at[symbole, "univers"] == "étendu":
        e = _meta("univers_etendu.csv")
        sources = [
            {"fichier": "data/univers_etendu.csv", "url": table.at[symbole, "source_url"] or e["url"],
             "date": table.at[symbole, "source_date"] or table.at[symbole, "consulte_le"] or e["date"],
             "objet": f"nom, classe, secteur, marché et devise ({table.at[symbole, 'regle']})"},
            {"fichier": "data/base/prix_etendus.csv",
             **{k: v for k, v in _meta("base/prix_etendus.csv").items() if k != "source"},
             "objet": "prix quotidiens ajustés (adj_close) : volatilité, pire baisse, part du risque"},
        ]
    else:
        u = _meta("assets_universe.csv")
        sources = [
            {"fichier": "data/assets_universe.csv", "url": u["url"], "date": u["date"],
             "objet": "nom, classe, secteur, marché et devise (table des organisateurs)"},
            {"fichier": "data/prices_daily.csv", **{k: v for k, v in _meta("prices_daily.csv").items() if k != "source"},
             "objet": "prix quotidiens ajustés (adj_close) : volatilité, pire baisse, part du risque"},
        ]
    if devise == "USD" and devise_profil == "CAD":
        sources.append({"fichier": "data/fx_usdcad_daily.csv",
                        **{k: v for k, v in _meta("fx_usdcad_daily.csv").items() if k != "source"},
                        "objet": "conversion USD vers CAD (Banque du Canada)"})
    if classe == "equity":
        f = esg_outils.fiche_esg(symbole)
        if f["statut"] == "connu":
            sources.append({"fichier": esg_outils.FICHIER_ESG, "url": f["source_controverse_url"],
                            "date": f["source_controverse_date"], "objet": f"controverse : « {f['controverse']} »"})
            sources.append({"fichier": esg_outils.FICHIER_ESG, "url": f["source_fossile_url"],
                            "date": f["source_fossile_date"], "objet": f"activité fossile : « {f['activite_fossile']} »"})
        else:
            sources.append({"fichier": esg_outils.FICHIER_ESG, "url": None, "date": None,
                            "objet": "ESG : information manquante"})
        fd = fondamentaux(symbole)
        sources.append({"fichier": fd["fichier"], "url": None, "date": None,
                        "objet": f"fondamentaux (bénéfices, dette, dividendes) : {fd['statut']}"
                                 + (f" ; data/base/couverture.csv : {fd['couverture']}" if fd["couverture"] else "")})
    if classe == "etf_equity":
        c = esg_outils.composition()
        lignes = c[c["fnb"] == symbole]
        if lignes.empty:
            sources.append({"fichier": esg_outils.FICHIER_FNB, "url": None, "date": None,
                            "objet": "composition du FNB : information manquante"})
        else:
            sources.append({"fichier": esg_outils.FICHIER_FNB, "url": lignes["source_url"].iloc[0],
                            "date": lignes["date"].max(), "objet": f"composition du FNB ({len(lignes)} lignes)"})
    return sources


def detail_ligne(symbole: str, devise_profil: str, ids: dict[str, str]) -> dict[str, Any]:
    """Secteur, pays, devise, repères des chiffres et sources d'une ligne."""
    table = univers(etendu=True)
    return {"secteur": table.at[symbole, "sector"], "pays": pays(symbole), "devise": table.at[symbole, "currency"],
            "chiffres": ids, "sources": sources_ligne(symbole, devise_profil)}


def criteres_valides(profil: Profil, demande: dict[str, Any]) -> set[str]:
    """Critères du profil auxquels une ligne peut se rattacher : ceux que la personne a vraiment."""
    valides = {"horizon", "objectif", "tolerance", "capital"}
    if profil.preferences:
        valides.add("preferences")
    if profil.exclusions:
        valides.add("exclusions")
    if profil.centres_interet:
        valides.add("centres_interet")
    if demande.get("symboles") or demande.get("classes"):
        valides.add("demande")
    return valides


def problemes_ligne(ligne: Any, profil: Profil, demande: dict[str, Any], candidats: list[str],
                    journal: Journal) -> list[str]:
    """Ce qui manque à la justification d'une ligne proposée (vide si elle est complète)."""
    s = ligne.symbole
    problemes = []
    if ligne.critere_profil not in criteres_valides(profil, demande):
        problemes.append(f"critère « {ligne.critere_profil} » absent de ce profil")
    for nom, texte in (("pourquoi", ligne.pourquoi), ("raison_plutot_que", ligne.raison_plutot_que)):
        if not (texte or "").strip():
            problemes.append(f"{nom} vide")
            continue
        problemes += [f"{nom} : {e}" for e in journal.verifier_texte(texte)]
        if not REPERE.findall(texte):
            problemes.append(f"{nom} sans repère chiffré {{id}}")
    if not ligne.plutot_que or ligne.plutot_que == s or ligne.plutot_que not in univers(etendu=True).index:
        problemes.append("plutot_que doit nommer un autre actif de l'univers")
    elif ligne.plutot_que not in candidats and ligne.plutot_que not in {d["symbole"] for d in demande.get("symboles", [])}:
        problemes.append(f"plutot_que {ligne.plutot_que} n'est pas un candidat de ce profil")
    return problemes


def controle_justifications(lignes: list[Any], profil: Profil, demande: dict[str, Any], candidats: list[str],
                            journal: Journal) -> dict[str, Any]:
    """Contrôle de gouvernance : chaque ligne justifiée par rapport au profil. Bloquant."""
    fautes = {l.symbole: problemes_ligne(l, profil, demande, candidats, journal) for l in lignes if l.poids > 0}
    fautes = {s: p for s, p in fautes.items() if p}
    message = ("Lignes sans justification complète liée au profil : "
               + " ; ".join(f"{s} ({', '.join(p)})" for s, p in fautes.items()) + "." if fautes
               else "Chaque ligne a un rôle, un critère du profil, une raison chiffrée et un candidat écarté comparé.")
    return {"controle": "justification_lignes", "statut": "non conforme" if fautes else "conforme",
            "bloquant": bool(fautes), "message": message, "actifs": sorted(fautes),
            "source": "agents/lignes.py"}
