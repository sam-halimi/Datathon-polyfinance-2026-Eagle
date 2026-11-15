"""Finnhub : fiche de société et nouvelles des actions américaines, en cache.

    python -m tools.nouvelles            # remplit le cache pour toutes les actions américaines

Offre gratuite de Finnhub : pas d'historique des cours, on ne l'appelle donc jamais pour ça (les
cours viennent de yfinance). Deux points d'accès seulement :
- `/stock/profile2` : fiche de société (nom, bourse, pays, secteur Finnhub, date d'introduction) ;
- `/company-news` : titres, source, date et lien des nouvelles d'une période.

Conditions de Finnhub (finnhub.io/terms-of-service) : offre « strictly for personal use », pas de
redistribution des données ni des résultats dérivés sans accord écrit. Les réponses restent donc dans
le cache local `data/cache/finnhub/` (ignoré par git) : le dépôt ne contient que ce code et
l'indicateur de couverture. Une nouvelle s'affiche avec sa source et son lien, comme un fait daté,
jamais comme un jugement de l'assistant.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from tools.api import get_json
from tools.trace import resultat

BASE = "https://finnhub.io/api/v1"
FRAICHEUR_NOUVELLES_H = 24
FRAICHEUR_FICHE_H = 24 * 7
SOURCE = "Finnhub (finnhub.io), offre gratuite, usage personnel"


def actions_americaines() -> list[str]:
    """Actions cotées en USD de l'univers de départ et de l'univers étendu."""
    from tools.env import RACINE

    symboles = []
    for f in ("assets_universe.csv", "univers_etendu.csv"):
        chemin = RACINE / "data" / f
        if chemin.exists():
            u = pd.read_csv(chemin, dtype=str, keep_default_na=False)
            symboles += u.loc[(u["asset_class"] == "equity") & (u["currency"] == "USD"), "ticker"].tolist()
    return symboles


def fiche_societe(symbole: str, session: Any = None) -> dict[str, Any]:
    """Fiche Finnhub d'une société, avec sa référence d'appel."""
    rep = get_json("finnhub", f"{BASE}/stock/profile2", {"symbol": symbole},
                   max_age_heures=FRAICHEUR_FICHE_H, session=session)
    d = rep["donnees"] or {}
    return resultat(
        outil="fiche_societe", parametres={"symbole": symbole},
        periode={"debut": None, "fin": rep["appele_le"][:10], "observations": 1 if d else 0},
        valeur=bool(d.get("name")), unite="booléen : True si Finnhub connaît la société",
        formule="réponse de GET /stock/profile2",
        sources=[f"{SOURCE}, appelé le {rep['appele_le']}"],
        details={k: d.get(k) for k in ("name", "ticker", "exchange", "country", "currency",
                                       "finnhubIndustry", "ipo", "weburl", "marketCapitalization")}
        | {"depuis_cache": rep["depuis_cache"]})


def nouvelles(symbole: str, jours: int = 30, fin: str | None = None, session: Any = None) -> dict[str, Any]:
    """Nouvelles d'une société sur les `jours` derniers jours (titre, source, date, lien)."""
    fin_d = date.fromisoformat(fin) if fin else date.today()
    debut = (fin_d - timedelta(days=jours)).isoformat()
    rep = get_json("finnhub", f"{BASE}/company-news", {"symbol": symbole, "from": debut, "to": fin_d.isoformat()},
                   max_age_heures=FRAICHEUR_NOUVELLES_H, session=session)
    articles = [{"date": pd.Timestamp(a["datetime"], unit="s").date().isoformat(), "titre": a.get("headline", ""),
                 "source": a.get("source", ""), "lien": a.get("url", "")}
                for a in (rep["donnees"] or []) if a.get("datetime")]
    articles.sort(key=lambda a: a["date"], reverse=True)
    return resultat(
        outil="nouvelles", parametres={"symbole": symbole, "debut": debut, "fin": fin_d.isoformat()},
        periode={"debut": debut, "fin": fin_d.isoformat(), "observations": len(articles)},
        valeur=len(articles), unite="nombre de nouvelles sur la période",
        formule="réponse de GET /company-news, triée par date",
        sources=[f"{SOURCE}, appelé le {rep['appele_le']}"],
        details={"articles": articles, "depuis_cache": rep["depuis_cache"],
                 "avertissement": "Titres de presse rapportés par Finnhub : des faits datés, pas un jugement."})


def remplir_cache(jours: int = 30) -> pd.DataFrame:
    """Une fiche et les nouvelles de chaque action américaine. Un échec est noté, pas comblé."""
    lignes = []
    for s in actions_americaines():
        ligne = {"symbole": s}
        for nom, f in (("fiche", lambda x: fiche_societe(x)), ("nouvelles", lambda x: nouvelles(x, jours))):
            try:
                r = f(s)
                ligne[nom] = r["valeur"]
            except Exception as e:  # noqa: BLE001 - noté dans la couverture
                ligne[nom] = f"échec : {e}"
        lignes.append(ligne)
    return pd.DataFrame(lignes)


if __name__ == "__main__":
    print(remplir_cache().to_string(index=False))
