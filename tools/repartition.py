"""Répartition d'un portefeuille simulé : marché de cotation, FNB, ancienneté de cotation.

Chiffres pour les préférences « Canada », « États-Unis », « FNB indiciels » et « sociétés établies ».
Chaque fonction renvoie la référence d'appel habituelle (`tools/trace.py`).

- Marché : colonne `market` de `data/assets_universe.csv` et `data/univers_etendu.csv`. TSX = Canada ;
  NASDAQ, NYSE, NYSE Arca, Cboe BZX et « U.S. (…) » = États-Unis. Une crypto n'est cotée sur aucun
  des deux marchés.
- FNB : `asset_class` commençant par `etf_` (FNB d'actions, d'obligations, d'or).
- Ancienneté de cotation : date d'introduction (`ipo`) de la fiche Finnhub `/stock/profile2`, mise
  en cache par `tools/nouvelles.py`. Pour une action du TSX, Finnhub refuse le symbole `.TO` dans
  l'offre gratuite : on interroge le symbole sans suffixe et on n'accepte la fiche que si son nom
  correspond à celui de notre table (le même symbole peut désigner une autre société : CNR chez Finnhub
  est Core Natural Resources, pas le CN). Sinon : information manquante.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from tools.donnees import univers
from tools.trace import resultat

SOURCE_UNIVERS = ["data/assets_universe.csv", "data/univers_etendu.csv"]
MARCHES = {"Canada": ("TSX",), "États-Unis": ("NASDAQ", "NYSE", "NYSE Arca", "Cboe BZX")}
ANNEES_ETABLIE = 10
"""Une société est « établie » si elle est cotée depuis au moins 10 ans (hypothèse de l'équipe)."""


def pays_du_marche(marche: str) -> str | None:
    if marche in MARCHES["Canada"]:
        return "Canada"
    if marche in MARCHES["États-Unis"] or marche.startswith("U.S."):
        return "États-Unis"
    return None


def part_par_marche(poids: dict[str, float], pays: str) -> dict[str, Any]:
    """Part du capital cotée sur le marché d'un pays (« Canada » ou « États-Unis »)."""
    if pays not in MARCHES:
        raise ValueError(f"pays inconnu {pays!r}, choix : {sorted(MARCHES)}")
    t = univers(etendu=True)
    lignes = {s: t.at[s, "market"] for s in poids if s in t.index}
    retenues = {s: w for s, w in poids.items() if s in lignes and pays_du_marche(lignes[s]) == pays}
    return resultat(
        outil="part_par_marche", parametres={"poids": dict(poids), "pays": pays},
        periode={"debut": None, "fin": None, "observations": len(poids)},
        valeur=float(sum(retenues.values())), unite="fraction du capital",
        formule=f"Σ poids des lignes cotées sur {', '.join(MARCHES[pays])}"
                + (" ou « U.S. (…) »" if pays == "États-Unis" else ""),
        sources=[f"{f} (market)" for f in SOURCE_UNIVERS],
        details={"lignes": retenues, "marches": lignes})


def part_fnb(poids: dict[str, float]) -> dict[str, Any]:
    """Part du capital en FNB (FNB d'actions, d'obligations et d'or)."""
    t = univers(etendu=True)
    fnb = {s: w for s, w in poids.items() if s in t.index and str(t.at[s, "asset_class"]).startswith("etf_")}
    return resultat(
        outil="part_fnb", parametres={"poids": dict(poids)},
        periode={"debut": None, "fin": None, "observations": len(poids)},
        valeur=float(sum(fnb.values())), unite="fraction du capital",
        formule="Σ poids des lignes dont asset_class commence par etf_",
        sources=[f"{f} (asset_class)" for f in SOURCE_UNIVERS], details={"lignes": fnb})


def _norm(texte: str) -> str:
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _meme_societe(nom_table: str, nom_finnhub: str) -> bool:
    """Les deux premiers mots significatifs du nom de notre table se retrouvent dans le nom Finnhub."""
    vides = {"the", "inc", "corp", "co", "ltd", "of", "and", "class", "a"}
    mots = [m for m in _norm(nom_table).split() if m not in vides][:2]
    autres = _norm(nom_finnhub).split()
    # Pas de correspondance approchée : « Exxonmobil Holdings Corp » (introduite en 2026 après une
    # restructuration) n'est pas « Exxon Mobil » ; accepter sa date ferait d'Exxon une société récente.
    return bool(mots) and all(m in autres for m in mots)


def anciennete_cotation(symbole: str, date_reference: str | None = None, session: Any = None) -> dict[str, Any]:
    """Années de cotation à `date_reference` (défaut : aujourd'hui), d'après la date d'introduction Finnhub.

    `valeur` None (information manquante) si la fiche n'existe pas, ne correspond pas ou n'a pas de date.
    """
    from tools.nouvelles import fiche_societe

    t = univers(etendu=True)
    ref = date.fromisoformat(date_reference) if date_reference else date.today()
    base = {"outil": "anciennete_cotation", "parametres": {"symbole": symbole, "date_reference": ref.isoformat()},
            "periode": {"debut": None, "fin": ref.isoformat(), "observations": 1},
            "unite": "années de cotation", "formule": "(date de référence − date d'introduction en bourse) en années"}
    if symbole not in t.index or t.at[symbole, "asset_class"] != "equity":
        return resultat(**base, valeur=None, sources=SOURCE_UNIVERS,
                        details={"statut": "information manquante", "raison": "pas une action de l'univers"})
    interroge = symbole.removesuffix(".TO")
    try:
        f = fiche_societe(interroge, session=session)
    except Exception as e:  # noqa: BLE001 - un refus de l'API est un trou, pas une erreur du pipeline
        return resultat(**base, valeur=None, sources=["Finnhub /stock/profile2"],
                        details={"statut": "information manquante", "raison": f"fiche Finnhub indisponible : {e}"})
    d = f["details"]
    nom_ok = _meme_societe(t.at[symbole, "name"], d.get("name") or "")
    bourse_ok = True  # la même société a la même date d'introduction, quelle que soit la bourse interrogée
    if not (f["valeur"] and d.get("ipo") and nom_ok and bourse_ok):
        raison = ("fiche Finnhub sans date d'introduction" if f["valeur"] and nom_ok and bourse_ok else
                  f"la fiche Finnhub de {interroge} ({d.get('name')}, {d.get('exchange')}) ne correspond pas à "
                  f"{t.at[symbole, 'name']} ({t.at[symbole, 'market']})")
        return resultat(**base, valeur=None, sources=f["sources"],
                        details={"statut": "information manquante", "raison": raison, "symbole_interroge": interroge})
    ipo = date.fromisoformat(d["ipo"])
    return resultat(**base, valeur=(ref - ipo).days / 365.25, sources=f["sources"],
                    details={"statut": "connu", "ipo": d["ipo"], "nom_finnhub": d.get("name"),
                             "bourse_finnhub": d.get("exchange"), "symbole_interroge": interroge})


def part_societes_etablies(poids: dict[str, float], annees: float = ANNEES_ETABLIE,
                           date_reference: str | None = None, session: Any = None) -> dict[str, Any]:
    """Part du capital en actions détenues en direct cotées depuis moins de `annees` ans, ou d'ancienneté inconnue.

    `valeur` = part récente + part inconnue (0 = toutes les actions détenues en direct sont établies).
    Les FNB, l'or et la crypto ne sont pas des sociétés : ils ne comptent pas.
    """
    t = univers(etendu=True)
    lignes, recente, inconnue, etablie = {}, 0.0, 0.0, 0.0
    for s, w in poids.items():
        if s not in t.index or t.at[s, "asset_class"] != "equity":
            continue
        a = anciennete_cotation(s, date_reference, session=session)
        lignes[s] = {"poids": w, "annees": a["valeur"], "ipo": a["details"].get("ipo"), "statut": a["details"]["statut"]}
        if a["valeur"] is None:
            inconnue += w
        elif a["valeur"] < annees:
            recente += w
        else:
            etablie += w
    return resultat(
        outil="part_societes_etablies", parametres={"poids": dict(poids), "annees": annees},
        periode={"debut": None, "fin": date_reference or date.today().isoformat(), "observations": len(lignes)},
        valeur=recente + inconnue, unite="fraction du capital en actions récentes ou d'ancienneté inconnue",
        formule=f"Σ poids des actions détenues en direct cotées depuis moins de {annees:g} ans ou sans date connue",
        sources=["Finnhub /stock/profile2 (ipo), cache de tools/nouvelles.py", *SOURCE_UNIVERS],
        details={"lignes": lignes, "part_recente": recente, "part_inconnue": inconnue, "part_etablie": etablie,
                 "regle": f"une société est établie si elle est cotée depuis au moins {annees:g} ans (hypothèse de l'équipe)"})
