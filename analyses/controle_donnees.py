"""Contrôle du jeu de données de départ.

Usage : python analyses/controle_donnees.py [prices_daily.csv] [macro_rates.csv]

Affiche, par actif : nombre de lignes, rendement annualisé, volatilité annualisée,
pire baisse et plus grand mouvement sur un jour. Calculs sur adj_close, dans la
devise de cotation, sans conversion ni alignement de calendrier.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    prix_csv = sys.argv[1] if len(sys.argv) > 1 else DATA / "prices_daily.csv"
    macro_csv = sys.argv[2] if len(sys.argv) > 2 else DATA / "macro_rates.csv"
    p = pd.read_csv(prix_csv, parse_dates=["date"])
    m = pd.read_csv(macro_csv)

    print("lignes de prix :", len(p), "| actifs :", p.ticker.nunique(),
          "|", p.date.min().date(), "au", p.date.max().date())
    print("doublons :", int(p.duplicated(["date", "ticker"]).sum()),
          "| valeurs manquantes :", int(p.isna().sum().sum()))

    lignes = []
    for t, g in p.sort_values("date").groupby("ticker"):
        g = g.set_index("date")
        r = g.adj_close.pct_change().dropna()
        annees = (g.index[-1] - g.index[0]).days / 365.25
        rendement = (g.adj_close.iloc[-1] / g.adj_close.iloc[0]) ** (1 / annees) - 1
        jours = 365 if t.endswith("-USD") else 252
        vol = r.std() * np.sqrt(jours)
        pire = (g.adj_close / g.adj_close.cummax() - 1).min()
        lignes.append((t, len(g), round(rendement * 100, 1), round(vol * 100, 1),
                       round(pire * 100, 1), round(r.abs().max() * 100, 1)))
    cols = ["actif", "lignes", "rend_annuel_%", "vol_%", "pire_baisse_%", "max_1j_%"]
    print(pd.DataFrame(lignes, columns=cols).to_string(index=False))

    print("\nlignes macro :", len(m))
    print(m.groupby("series_id").agg(n=("value", "size"), debut=("date", "min"),
                                     fin=("date", "max"), derniere=("value", "last")).to_string())


if __name__ == "__main__":
    main()
