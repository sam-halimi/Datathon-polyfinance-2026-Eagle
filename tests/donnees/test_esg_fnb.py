"""Contrôles des tables ajoutées par la branche donnees.

- data/esg_actions.csv : une ligne par action de l'univers, chaque valeur sourcée.
- data/esg_sources.csv : les extraits des pages ouvertes qui appuient chaque valeur.
- data/fnb_composition.csv : composition de SPY, QQQ, XIU.TO et ESGV, tirée des émetteurs.
"""
from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).resolve().parents[2] / "data"
VALEURS = {"oui", "non", "inconnu"}
FNB = {"SPY", "QQQ", "XIU.TO", "ESGV"}


@pytest.fixture(scope="module")
def univers():
    return pd.read_csv(DATA / "assets_universe.csv")


@pytest.fixture(scope="module")
def esg():
    return pd.read_csv(DATA / "esg_actions.csv", dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def preuves():
    return pd.read_csv(DATA / "esg_sources.csv", dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def fnb():
    # keep_default_na=False : « NA » est le symbole de la Banque Nationale dans XIU.
    f = pd.read_csv(DATA / "fnb_composition.csv", dtype=str, keep_default_na=False)
    f["poids"] = f["poids"].astype(float)
    return f


# --- Table ESG -------------------------------------------------------------

def test_esg_une_ligne_par_action_de_l_univers(esg, univers):
    actions = set(univers.loc[univers["asset_class"] == "equity", "ticker"])
    assert len(actions) == 20
    assert esg["ticker"].is_unique
    assert set(esg["ticker"]) == actions


def test_esg_valeurs_permises(esg):
    assert set(esg["activite_fossile"]) <= VALEURS
    assert set(esg["controverse"]) <= VALEURS


@pytest.mark.parametrize("champ", ["fossile", "controverse"])
def test_esg_toute_valeur_connue_a_sa_source_et_sa_date(esg, champ):
    colonne = "activite_fossile" if champ == "fossile" else "controverse"
    connues = esg[esg[colonne] != "inconnu"]
    assert connues[f"source_{champ}_url"].str.startswith("https://").all()
    dates = pd.to_datetime(connues[f"source_{champ}_date"], format="mixed")
    consulte = pd.to_datetime(connues["consulte_le"])
    assert (dates <= consulte).all(), "une source ne peut pas être datée après sa consultation"


def test_esg_chaque_valeur_connue_a_un_extrait(esg, preuves):
    for champ, colonne in [("fossile", "activite_fossile"), ("controverse", "controverse")]:
        connues = esg.loc[esg[colonne] != "inconnu", "ticker"]
        appuyees = set(preuves.loc[preuves["champ"] == champ, "ticker"])
        manquants = set(connues) - appuyees
        assert not manquants, f"{champ} sans extrait : {sorted(manquants)}"
    assert (preuves["extrait"].str.len() > 0).all()
    assert preuves["url"].str.startswith("https://").all()


def test_esg_resume_present_et_vocabulaire(esg):
    assert (esg["resume"].str.len() > 20).all()
    textes = " ".join(esg["resume"]) + " ".join(esg["precision_fossile"]) + " ".join(esg["resume_controverse"])
    assert "conseil" not in textes.lower()


def test_esg_secteur_identique_a_l_univers(esg, univers):
    ref = univers.set_index("ticker")["sector"]
    assert (esg.set_index("ticker")["secteur"] == ref.loc[esg["ticker"]]).all()


# --- Composition des FNB ---------------------------------------------------

def test_fnb_les_quatre_fonds(fnb):
    assert set(fnb["fnb"]) == FNB
    assert not fnb.duplicated(["fnb", "symbole_detenu"]).any()


def test_fnb_poids_en_fraction(fnb):
    titres = fnb
    assert ((titres["poids"] > -0.05) & (titres["poids"] < 0.25)).all()
    sommes = titres.groupby("fnb")["poids"].sum()
    assert (sommes < 1.05).all(), sommes


def test_fnb_date_et_source(fnb):
    assert pd.to_datetime(fnb["date"]).max() <= pd.Timestamp("2026-11-15")
    assert fnb["source_url"].str.startswith("https://").all()


def test_fnb_symboles_de_l_univers_existent(fnb, univers):
    """Dans XIU.TO, un titre canadien de l'univers s'écrit comme dans l'univers (RY.TO, pas RY).

    Les FNB américains gardent la cotation américaine : QQQ détient SHOP (Nasdaq, USD),
    la même société que SHOP.TO mais une autre cotation et une autre devise.
    """
    tickers = set(univers["ticker"])
    racines = {t.removesuffix(".TO"): t for t in tickers if t.endswith(".TO")}
    for s in fnb.loc[fnb["fnb"] == "XIU.TO", "symbole_detenu"]:
        assert s not in racines, f"{s} doit s'écrire {racines[s]}"


def test_fnb_xiu_ne_detient_que_des_titres_canadiens_de_l_univers(fnb, univers):
    us = set(univers.loc[(univers["asset_class"] == "equity") & (univers["currency"] == "USD"), "ticker"])
    xiu = set(fnb.loc[fnb["fnb"] == "XIU.TO", "symbole_detenu"])
    assert not (xiu & us)


def test_fnb_complets_pour_spy_qqq_xiu(fnb):
    sommes = fnb.groupby("fnb")["poids"].sum()
    for f in ["SPY", "QQQ", "XIU.TO"]:
        assert sommes[f] == pytest.approx(1.0, abs=0.005), f


def test_esgv_coherent_avec_la_table_esg(esg, fnb):
    esgv = set(fnb.loc[fnb["fnb"] == "ESGV", "symbole_detenu"])
    for _, r in esg.iterrows():
        if r["ticker"].endswith(".TO"):
            assert r["retenu_par_esgv"] == "sans objet"
        else:
            assert r["retenu_par_esgv"] == ("oui" if r["ticker"] in esgv else "non"), r["ticker"]


def test_esgv_exclut_les_titres_fossiles_americains(esg):
    us = esg[~esg["ticker"].str.endswith(".TO")]
    assert (us.loc[us["activite_fossile"] == "oui", "retenu_par_esgv"] == "non").all()


# --- Traçabilité -----------------------------------------------------------

def test_metadonnees_pour_chaque_fichier_ajoute():
    meta = pd.read_csv(DATA / "sources_metadata.csv", dtype=str, keep_default_na=False)
    for fichier in ["esg_actions.csv", "esg_sources.csv", "fnb_composition.csv"]:
        lignes = meta[meta["file"] == fichier]
        assert len(lignes) >= 1, fichier
        for col in ["source", "source_url", "retrieved_on", "processing", "limitations", "terms_of_use"]:
            assert (lignes[col].str.len() > 0).all(), (fichier, col)
