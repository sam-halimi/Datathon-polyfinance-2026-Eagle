"""CoinGecko : capitalisation, volume et prix du jour de Bitcoin et d'Ether, en cache.

    python -m tools.crypto

Un seul point d'accès : `/coins/markets` (prix, capitalisation, volume sur 24 h, heure de mise à
jour). L'offre gratuite s'arrête à un an d'historique : l'historique long reste celui de
`data/prices_daily.csv` (BTC-USD, ETH-USD, de 2021 à 2026). On ne demande donc pas d'historique.

Conditions de CoinGecko (coingecko.com/en/api_terms, version du 5 septembre 2025) :
- mention obligatoire « Powered by CoinGecko » (clause 4.3), reprise dans chaque référence ;
- « We do not encourage caching or storage of Data » ; s'il y a un cache, le rafraîchir au moins
  toutes les 24 heures (clause 6.1.1). D'où FRAICHEUR_H = 24 et un cache local non versé.
"""

from __future__ import annotations

from typing import Any

from tools.api import get_json
from tools.trace import resultat

URL = "https://api.coingecko.com/api/v3/coins/markets"
IDENTIFIANTS = {"BTC-USD": "bitcoin", "ETH-USD": "ethereum"}
FRAICHEUR_H = 24
MENTION = "Powered by CoinGecko"
CHAMPS = {"prix": ("current_price", "USD"), "capitalisation": ("market_cap", "USD"),
          "volume_24h": ("total_volume", "USD sur 24 heures")}


def marche_crypto(symbole: str, mesure: str = "capitalisation", session: Any = None) -> dict[str, Any]:
    """Prix, capitalisation ou volume du jour d'une crypto de l'univers (BTC-USD, ETH-USD)."""
    if symbole not in IDENTIFIANTS:
        raise ValueError(f"{symbole} : seules {sorted(IDENTIFIANTS)} sont suivies sur CoinGecko")
    if mesure not in CHAMPS:
        raise ValueError(f"mesure inconnue {mesure!r}, choix : {sorted(CHAMPS)}")
    rep = get_json("coingecko", URL, {"vs_currency": "usd", "ids": ",".join(sorted(IDENTIFIANTS.values()))},
                   max_age_heures=FRAICHEUR_H, session=session)
    ligne = next((x for x in rep["donnees"] if x.get("id") == IDENTIFIANTS[symbole]), None)
    if ligne is None or ligne.get(CHAMPS[mesure][0]) is None:
        raise ValueError(f"CoinGecko n'a pas renvoyé {mesure} pour {symbole}")
    champ, unite = CHAMPS[mesure]
    jour = (ligne.get("last_updated") or rep["appele_le"])[:10]
    return resultat(
        outil="marche_crypto", parametres={"symbole": symbole, "mesure": mesure},
        periode={"debut": jour, "fin": jour, "observations": 1},
        valeur=float(ligne[champ]), unite=unite,
        formule=f"champ {champ} de GET /coins/markets (vs_currency=usd)",
        sources=[f"CoinGecko API, {MENTION}, appelé le {rep['appele_le']}"],
        details={"mis_a_jour_par_coingecko": ligne.get("last_updated"), "depuis_cache": rep["depuis_cache"],
                 "mention": MENTION,
                 "limite": "Valeur du jour seulement : l'historique long vient de data/prices_daily.csv."})


if __name__ == "__main__":
    for s in IDENTIFIANTS:
        for m in CHAMPS:
            r = marche_crypto(s, m)
            print(f"{s} {m} : reçu ({r['unite']}, mis à jour {r['details']['mis_a_jour_par_coingecko']})")
    print(MENTION)
