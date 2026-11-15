"""Couverture des données par actif : `python -m tools.couverture`

Écrit `data/base/couverture.csv` : une ligne par actif (univers de départ et univers étendu), une
colonne par domaine (cours, fondamentaux, nouvelles, ESG, composition) valant « oui », « non » ou
« partiel », avec la source. Chaque valeur est lue dans les fichiers ou le cache, jamais supposée.
Un trou s'écrit, il ne se comble pas.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from tools.env import RACINE

DATA = RACINE / "data"
SORTIE = DATA / "base" / "couverture.csv"
DOMAINES = ("cours", "fondamentaux", "nouvelles", "esg", "composition")


def _univers() -> pd.DataFrame:
    a = pd.read_csv(DATA / "assets_universe.csv", dtype=str)[["ticker", "asset_class", "currency"]].assign(univers="départ")
    e = pd.read_csv(DATA / "univers_etendu.csv", dtype=str)[["ticker", "asset_class", "currency"]].assign(univers="étendu")
    return pd.concat([a, e], ignore_index=True)


def _cours(u: pd.DataFrame) -> dict[str, tuple[str, str]]:
    sortie = {}
    for fichier, univers in (("prices_daily.csv", "départ"), ("base/prix_etendus.csv", "étendu")):
        chemin = DATA / fichier
        if not chemin.exists():
            continue
        p = pd.read_csv(chemin, usecols=["date", "ticker"])
        debut, fin = p["date"].min(), p["date"].max()
        for t, g in p.groupby("ticker"):
            complet = g["date"].min() == debut and g["date"].max() == fin
            sortie[t] = ("oui" if complet else "partiel",
                         f"data/{fichier} (Yahoo Finance) : {g['date'].min()} au {g['date'].max()}")
    return sortie


def _nouvelles() -> dict[str, tuple[str, str]]:
    """Lit le cache local de Finnhub sans rien appeler."""
    from tools.api import lire_cache
    from tools.nouvelles import BASE, actions_americaines

    sortie = {}
    cache = DATA / "cache" / "finnhub"
    for s in actions_americaines():
        trouve = None
        if cache.exists():
            import json

            for f in cache.glob("*.json"):
                e = json.loads(f.read_text(encoding="utf-8"))
                if e["url"] == f"{BASE}/company-news" and e["params"].get("symbol") == s:
                    trouve = e
        if trouve is None:
            sortie[s] = ("non", "Finnhub : cache local vide pour ce symbole (lancer python -m tools.nouvelles)")
        else:
            n = len(trouve["donnees"] or [])
            sortie[s] = ("oui" if n else "non",
                         f"Finnhub /company-news, {n} nouvelles du {trouve['params']['from']} au {trouve['params']['to']} "
                         f"(cache local du {trouve['appele_le'][:10]}, non versé)")
    _ = lire_cache
    return sortie


def construire() -> pd.DataFrame:
    u = _univers()
    cours = _cours(u)
    nouvelles = _nouvelles()
    esg = pd.read_csv(DATA / "esg_actions.csv", dtype=str, keep_default_na=False).set_index("ticker")
    fnb = pd.read_csv(DATA / "fnb_composition.csv", dtype=str, keep_default_na=False)
    poids_fnb = fnb.assign(poids=fnb["poids"].astype(float)).groupby("fnb")["poids"].sum()
    lignes = []
    for _, r in u.iterrows():
        t, classe = r["ticker"], r["asset_class"]
        ligne = {"ticker": t, "univers": r["univers"], "classe": classe}
        ligne["cours"], ligne["cours_source"] = cours.get(t, ("non", "aucun fichier de cours"))
        ligne["fondamentaux"] = "non"
        ligne["fondamentaux_source"] = (
            "SEC EDGAR pas encore branché (étape reportée) : aucune donnée" if classe == "equity"
            else "ne s'applique pas à un FNB ou à une crypto")
        if t in nouvelles:
            ligne["nouvelles"], ligne["nouvelles_source"] = nouvelles[t]
        else:
            ligne["nouvelles"] = "non"
            ligne["nouvelles_source"] = ("Finnhub non appelé pour les actions canadiennes" if classe == "equity"
                                         else "ne s'applique pas : nouvelles par société seulement")
        if t in esg.index:
            inconnu = "inconnu" in (esg.at[t, "activite_fossile"], esg.at[t, "controverse"])
            ligne["esg"] = "partiel" if inconnu else "oui"
            ligne["esg_source"] = f"data/esg_actions.csv (sources consultées le {esg.at[t, 'consulte_le']})"
        elif t in poids_fnb.index:
            ligne["esg"] = "partiel"
            ligne["esg_source"] = "à travers data/fnb_composition.csv : seuls les titres de la table ESG sont jugés"
        else:
            ligne["esg"] = "non"
            ligne["esg_source"] = "absent de data/esg_actions.csv"
        if classe.startswith("etf"):
            if t in poids_fnb.index:
                complet = poids_fnb[t] > 0.9
                d = fnb.loc[fnb["fnb"] == t, "date"].max()
                ligne["composition"] = "oui" if complet else "partiel"
                ligne["composition_source"] = (f"data/fnb_composition.csv au {d}"
                                               + ("" if complet else " (titres de l'univers seulement)"))
            else:
                ligne["composition"] = "non"
                ligne["composition_source"] = "absent de data/fnb_composition.csv"
        else:
            ligne["composition"] = "non"
            ligne["composition_source"] = "ne s'applique pas : pas un FNB"
        lignes.append(ligne)
    df = pd.DataFrame(lignes)
    df["notes"] = df.apply(lambda r: ("prix, capitalisation et volume du jour : CoinGecko via tools/crypto.py "
                                      "(cache local de 24 h, non versé)") if r["classe"] == "crypto" else "", axis=1)
    df["etabli_le"] = date.today().isoformat()
    return df


if __name__ == "__main__":
    df = construire()
    df.to_csv(SORTIE, index=False)
    print(df[["ticker", "univers", *DOMAINES]].to_string(index=False))
