"""Exemples chiffrés pour les explications à trois niveaux.

Usage : python analyses/exemples_explications.py [prices_daily.csv] [macro_rates.csv]

1. Sensibilité des FNB obligataires au taux 10 ans américain (régression).
2. Part du risque par actif dans un portefeuille 60 % SPY, 30 % AGG, 10 % BTC.
3. Corrélation de MSFT et NVDA avec QQQ.
4. Pente de la courbe 10 ans - 2 ans, États-Unis et Canada.

Calculs en devise de cotation, sur les jours communs aux séries utilisées.
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
    m = pd.read_csv(macro_csv, parse_dates=["date"])
    px = p.pivot(index="date", columns="ticker", values="adj_close")

    def serie(sid: str) -> pd.Series:
        return m[m.series_id == sid].set_index("date")["value"]

    print("1. Sensibilité au taux 10 ans américain")
    taux = serie("DGS10")
    for t in ["TLT", "AGG"]:
        df = pd.DataFrame({"r": px[t].dropna().pct_change(), "dy": taux.diff()}).dropna()
        pente = np.polyfit(df.dy, df.r, 1)[0]
        r2 = np.corrcoef(df.dy, df.r)[0, 1] ** 2
        print(f"   {t} : {pente * 100:.1f} % par point de taux, R2 {r2:.2f}, {len(df)} jours")
    print(f"   10 ans : {taux.iloc[0]} % au début, {taux.iloc[-1]} % à la fin, "
          f"maximum {taux.max()} % le {taux.idxmax().date()}")

    print("\n2. Part du risque, 60 % SPY / 30 % AGG / 10 % BTC")
    actifs = ["SPY", "AGG", "BTC-USD"]
    poids = np.array([0.6, 0.3, 0.1])
    r = px[actifs].dropna().pct_change().dropna()
    cov = r.cov().values * 252
    vol = np.sqrt(poids @ cov @ poids)
    parts = poids * (cov @ poids) / vol ** 2
    print(f"   volatilité du portefeuille : {vol * 100:.1f} %")
    for a, w, part in zip(actifs, poids, parts):
        print(f"   {a} : {w * 100:.0f} % du capital, {part * 100:.1f} % du risque")
    print("   corrélations :")
    print(r.corr().round(2).to_string())

    print("\n3. Corrélation avec QQQ")
    r2 = px[["MSFT", "NVDA", "QQQ", "SPY"]].dropna().pct_change().dropna()
    print(r2.corr().round(2)["QQQ"].to_string())

    print("\n4. Pente 10 ans - 2 ans")
    for long, court, pays in [("DGS10", "DGS2", "États-Unis"),
                              ("BD.CDN.10YR.DQ.YLD", "BD.CDN.2YR.DQ.YLD", "Canada")]:
        s = (serie(long) - serie(court)).dropna()
        print(f"   {pays} : minimum {s.min():.2f} le {s.idxmin().date()}, "
              f"dernière {s.iloc[-1]:.2f}, négative {(s < 0).sum()} jours sur {len(s)}")


if __name__ == "__main__":
    main()
