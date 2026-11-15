"""Cours de l'univers étendu (yfinance) : `python -m tools.cours`

Les 31 actifs de départ restent dans `data/prices_daily.csv`, qu'on ne touche pas : les tests
reposent sur cet instantané. Les nouveaux actifs viennent de `data/univers_etendu.csv`, une table
sourcée (page ou fichier de l'émetteur, URL et date sur chaque ligne). Aucun symbole de mémoire.

Le téléchargement et les contrôles sont ceux de `data/build_dataset.py` (`build_prices`, `check`) :
même fenêtre (START, END), même format (`adj_close` ajusté par Yahoo, fractionnements déjà
appliqués, à ne pas réappliquer), mêmes refus (doublons, symbole manquant, prix invalide).

Sorties dans `data/base/` :
- `prix_etendus.csv` : colonnes de `prices_daily.csv`, plus `telecharge_le` ;
- `actions_etendues.csv` : dividendes et fractionnements, pour information ;
- `rapport_prix_etendus.txt` : avertissements de `check` (trous, historique court, gros mouvements).

Cache : le téléchargement brut est gardé dans `data/cache/yfinance/` ; relancer ne rappelle pas
Yahoo tant que la liste des symboles et la fenêtre ne changent pas (`--rafraichir` pour forcer).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from tools.trace import periode_de, resultat

RACINE = Path(__file__).resolve().parents[1]
DATA = RACINE / "data"
SORTIE = DATA / "base" / "prix_etendus.csv"
CACHE = DATA / "cache" / "yfinance"
FICHIER_UNIVERS_ETENDU = "data/univers_etendu.csv"
COLONNES_UNIVERS = ["ticker", "name", "asset_class", "market", "currency", "sector"]


def build_dataset():
    """Le module data/build_dataset.py, importé tel quel (il n'est pas dans un paquet)."""
    spec = importlib.util.spec_from_file_location("build_dataset", DATA / "build_dataset.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def univers_etendu() -> pd.DataFrame:
    u = pd.read_csv(DATA / "univers_etendu.csv", dtype=str, keep_default_na=False)
    manque = [c for c in ["source_url", "source_extrait", "consulte_le"] if (u[c] == "").any()]
    if manque:
        raise ValueError(f"{FICHIER_UNIVERS_ETENDU} : source incomplète ({manque}) : un symbole sans source est refusé")
    deja = set(pd.read_csv(DATA / "assets_universe.csv")["ticker"]) & set(u["ticker"])
    if deja:
        raise ValueError(f"déjà dans assets_universe.csv : {sorted(deja)}")
    if u["ticker"].duplicated().any():
        raise ValueError("symbole en double dans univers_etendu.csv")
    return u


def _cle_cache(tickers: list[str], debut: str, fin: str) -> Path:
    h = hashlib.sha256(json.dumps([sorted(tickers), debut, fin]).encode()).hexdigest()[:16]
    return CACHE / h


def telecharger(rafraichir: bool = False, bd=None,
                construire: Callable[[pd.DataFrame], tuple[pd.DataFrame, pd.DataFrame]] | None = None) -> dict[str, Any]:
    """Télécharge, contrôle et écrit les cours de l'univers étendu. Renvoie un résumé.

    `bd` et `construire` se remplacent dans les tests (réponse simulée de yfinance).
    """
    bd = bd or build_dataset()
    u = univers_etendu()
    univ = u[COLONNES_UNIVERS].copy()
    univ.insert(0, "asset_id", [f"E{i:02d}" for i in range(1, len(univ) + 1)])

    dossier = _cle_cache(univ["ticker"].tolist(), bd.START, bd.END)
    if dossier.exists() and not rafraichir:
        prices = pd.read_csv(dossier / "prix.csv", dtype={"date": str})
        actions = pd.read_csv(dossier / "actions.csv", dtype={"ex_date": str})
        meta = json.loads((dossier / "meta.json").read_text(encoding="utf-8"))
    else:
        prices, actions = (construire or bd.build_prices)(univ)
        prices["date"] = prices["date"].astype(str)
        actions["ex_date"] = actions["ex_date"].astype(str)
        meta = {"telecharge_le": date.today().isoformat(), "debut": bd.START, "fin": bd.END,
                "symboles": univ["ticker"].tolist(), "source": "Yahoo Finance via yfinance (build_dataset.build_prices)"}
        dossier.mkdir(parents=True, exist_ok=True)
        prices.to_csv(dossier / "prix.csv", index=False)
        actions.to_csv(dossier / "actions.csv", index=False)
        (dossier / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # Contrôles de build_dataset.py. fx et macro sont ceux du dépôt : check les exige, ils ne changent pas.
    fx = pd.read_csv(DATA / "fx_usdcad_daily.csv")
    macro = pd.read_csv(DATA / "macro_rates.csv")
    avertissements = bd.check(univ, prices.assign(date=pd.to_datetime(prices["date"]).dt.date),
                              actions, fx, macro)

    prices = prices.assign(telecharge_le=meta["telecharge_le"]).sort_values(["ticker", "date"])
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(SORTIE, index=False)
    actions.to_csv(DATA / "base" / "actions_etendues.csv", index=False)
    lignes = [f"Cours de l'univers étendu, téléchargés le {meta['telecharge_le']} (fenêtre {meta['debut']} au {meta['fin']}).",
              f"{len(prices)} lignes, {prices['ticker'].nunique()} symboles.", ""]
    lignes += [f"- {a}" for a in avertissements] or ["Aucun avertissement de check()."]
    (DATA / "base" / "rapport_prix_etendus.txt").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return {"lignes": len(prices), "symboles": prices["ticker"].nunique(), "avertissements": avertissements,
            "telecharge_le": meta["telecharge_le"]}


def charger_prix_etendus(symboles: str | list[str] | None = None, colonne: str = "adj_close") -> pd.DataFrame:
    """Prix de l'univers étendu en tableau large (dates x symboles), sans remplissage."""
    p = pd.read_csv(SORTIE, parse_dates=["date"])
    if symboles is not None:
        symboles = [symboles] if isinstance(symboles, str) else list(symboles)
        inconnus = sorted(set(symboles) - set(p["ticker"]))
        if inconnus:
            raise ValueError(f"symboles absents de {SORTIE.name} : {inconnus}")
        p = p[p["ticker"].isin(symboles)]
    return p.pivot(index="date", columns="ticker", values=colonne).sort_index()


def couverture_cours(symbole: str) -> dict[str, Any]:
    """Période couverte par les cours d'un symbole de l'univers étendu, avec sa référence."""
    px = charger_prix_etendus(symbole)[symbole].dropna()
    brut = pd.read_csv(SORTIE, usecols=["ticker", "telecharge_le"])
    return resultat(
        outil="couverture_cours", parametres={"symbole": symbole}, periode=periode_de(px.index),
        valeur=int(len(px)), unite="nombre de jours avec un prix",
        formule="lignes de data/base/prix_etendus.csv pour ce symbole",
        sources=["data/base/prix_etendus.csv (adj_close)", FICHIER_UNIVERS_ETENDU],
        details={"telecharge_le": brut.loc[brut["ticker"] == symbole, "telecharge_le"].iloc[0]})


if __name__ == "__main__":
    r = telecharger(rafraichir="--rafraichir" in sys.argv)
    print(f"{r['lignes']} lignes, {r['symboles']} symboles, téléchargés le {r['telecharge_le']}")
    for a in r["avertissements"]:
        print("  -", a)
