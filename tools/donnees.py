"""Lecture des CSV de data/ : univers, prix, taux de change.

Deux univers sourcés : celui de départ (`assets_universe.csv`, cours dans `prices_daily.csv`) et
l'univers étendu (`univers_etendu.csv`, cours dans `base/prix_etendus.csv`, ajoutés par API).
Sans argument, `univers()` et `charger_prix()` ne rendent que l'univers de départ, comme avant ;
un symbole étendu demandé explicitement est reconnu partout (devise, classe, prix).

Les prix restent dans la devise de cotation (`.TO` en CAD, le reste en USD).
Aucun remplissage ni alignement ici : une case vide veut dire que le marché de
l'actif n'a pas coté ce jour-là. L'alignement se fait dans `calendriers.py`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
FICHIER_PRIX = "prices_daily.csv"
FICHIER_UNIVERS = "assets_universe.csv"
FICHIER_FX = "fx_usdcad_daily.csv"
FICHIER_UNIVERS_ETENDU = "univers_etendu.csv"
FICHIER_PRIX_ETENDUS = "base/prix_etendus.csv"
COLONNES_PRIX = ("open", "high", "low", "close", "adj_close", "volume")


class SymboleInconnu(KeyError):
    """Symbole absent des deux tables sourcées (assets_universe.csv, univers_etendu.csv)."""


@lru_cache(maxsize=None)
def _lire_prix() -> pd.DataFrame:
    depart = pd.read_csv(DATA / FICHIER_PRIX, parse_dates=["date"])
    if not (DATA / FICHIER_PRIX_ETENDUS).is_file():
        return depart
    etendus = pd.read_csv(DATA / FICHIER_PRIX_ETENDUS, parse_dates=["date"])
    etendus = etendus[[c for c in depart.columns if c in etendus.columns]]
    return pd.concat([depart, etendus[~etendus["ticker"].isin(set(depart["ticker"]))]], ignore_index=True)


@lru_cache(maxsize=None)
def _lire_univers() -> pd.DataFrame:
    return pd.read_csv(DATA / FICHIER_UNIVERS).set_index("ticker")


@lru_cache(maxsize=None)
def _lire_univers_complet() -> pd.DataFrame:
    """Les deux univers, avec une colonne `univers` (« départ » ou « étendu »)."""
    depart = _lire_univers().assign(univers="départ")
    if not (DATA / FICHIER_UNIVERS_ETENDU).is_file():
        return depart
    etendu = pd.read_csv(DATA / FICHIER_UNIVERS_ETENDU, dtype=str, keep_default_na=False).set_index("ticker")
    etendu = etendu[~etendu.index.isin(depart.index)].assign(univers="étendu")
    return pd.concat([depart, etendu])


@lru_cache(maxsize=None)
def _lire_fx() -> pd.DataFrame:
    return pd.read_csv(DATA / FICHIER_FX, parse_dates=["date"]).set_index("date").sort_index()


def univers(etendu: bool = False) -> pd.DataFrame:
    """Table des actifs, indexée par symbole (copie). `etendu=True` ajoute l'univers étendu."""
    return (_lire_univers_complet() if etendu else _lire_univers()).copy()


def verifier_symboles(symboles: list[str]) -> None:
    """Lève SymboleInconnu si un symbole n'est dans aucune des deux tables sourcées."""
    inconnus = [s for s in symboles if s not in _lire_univers_complet().index]
    if inconnus:
        raise SymboleInconnu(
            f"Symboles absents de {FICHIER_UNIVERS} et de {FICHIER_UNIVERS_ETENDU} : {inconnus}. "
            "Un symbole doit venir d'une table sourcée et passer build_dataset.py ou tools/cours.py."
        )


def fichier_univers(symbole: str) -> str:
    """Table sourcée d'où vient le symbole."""
    verifier_symboles([symbole])
    return FICHIER_UNIVERS if symbole in _lire_univers().index else FICHIER_UNIVERS_ETENDU


def fichier_prix(symbole: str) -> str:
    """Fichier de cours du symbole : prices_daily.csv (départ) ou base/prix_etendus.csv (étendu)."""
    return FICHIER_PRIX if fichier_univers(symbole) == FICHIER_UNIVERS else FICHIER_PRIX_ETENDUS


def sources_prix(symboles: list[str]) -> list[str]:
    """Fichiers de cours d'une liste de symboles, dans l'ordre, sans doublon."""
    return list(dict.fromkeys(f"{fichier_prix(s)} (adj_close)" for s in symboles))


def devise(symbole: str) -> str:
    verifier_symboles([symbole])
    return str(_lire_univers_complet().at[symbole, "currency"])


def classe_actif(symbole: str) -> str:
    verifier_symboles([symbole])
    return str(_lire_univers_complet().at[symbole, "asset_class"])


def jours_par_an(symbole: str) -> int:
    """252 jours de bourse, 365 pour les cryptos (cotées 7 jours sur 7)."""
    return 365 if classe_actif(symbole) == "crypto" else 252


def charger_prix(
    symboles: str | list[str] | None = None,
    debut: str | None = None,
    fin: str | None = None,
    colonne: str = "adj_close",
) -> pd.DataFrame:
    """Prix quotidiens en format large : une ligne par date, une colonne par symbole.

    - `colonne` : `adj_close` par défaut (dividendes et fractionnements inclus).
      Les fractionnements sont déjà appliqués : ne pas les réappliquer.
    - Devise de cotation, sans conversion.
    - Union des calendriers : NaN quand un actif n'a pas coté ce jour-là.
    - `debut` et `fin` sont inclusifs (format AAAA-MM-JJ).
    """
    if colonne not in COLONNES_PRIX:
        raise ValueError(f"colonne doit être l'une de {COLONNES_PRIX}")
    if symboles is None:
        symboles = sorted(_lire_univers().index)
    elif isinstance(symboles, str):
        symboles = [symboles]
    symboles = list(symboles)
    verifier_symboles(symboles)

    p = _lire_prix()
    p = p[p["ticker"].isin(symboles)]
    if debut is not None:
        p = p[p["date"] >= pd.Timestamp(debut)]
    if fin is not None:
        p = p[p["date"] <= pd.Timestamp(fin)]
    large = p.pivot(index="date", columns="ticker", values=colonne).sort_index()
    large = large.reindex(columns=symboles)
    large.columns.name = None
    return large


def taux_change() -> pd.DataFrame:
    """Taux USD/CAD de la Banque du Canada (jours ouvrables canadiens), copie."""
    return _lire_fx().copy()
