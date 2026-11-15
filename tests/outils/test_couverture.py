"""data/base/couverture.csv : un actif par ligne, oui/non/partiel avec une source, aucun trou comblé."""

import pandas as pd

from tools.couverture import DATA, DOMAINES, SORTIE


def test_un_actif_par_ligne_et_trois_valeurs():
    c = pd.read_csv(SORTIE, dtype=str, keep_default_na=False)
    attendus = set(pd.read_csv(DATA / "assets_universe.csv")["ticker"]) | set(pd.read_csv(DATA / "univers_etendu.csv")["ticker"])
    assert set(c["ticker"]) == attendus and c["ticker"].is_unique
    for d in DOMAINES:
        assert set(c[d]) <= {"oui", "non", "partiel"}, d
        assert (c[f"{d}_source"].str.len() > 0).all(), d


def test_trous_ecrits_et_non_combles():
    c = pd.read_csv(SORTIE, dtype=str, keep_default_na=False).set_index("ticker")
    assert (c["fondamentaux"] == "non").all()  # SEC EDGAR pas encore branché
    assert c.at["NXT", "cours"] == "partiel"  # historique depuis 2023
    assert c.at["ESGV", "composition"] == "partiel" and c.at["SPY", "composition"] == "oui"
    assert c.at["RY.TO", "nouvelles"] == "non"
