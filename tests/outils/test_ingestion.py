import shutil

import pandas as pd
import pytest

from tools.ingestion import (
    A_COMPLETER,
    DATA,
    ErreurIngestion,
    deviner_frequence,
    executer,
    lire_catalogue,
    nettoyer,
    panel_quotidien,
)

FICHIERS = ["catalogue.csv", "macro_rates.csv", "fx_usdcad_daily.csv", "sources_metadata.csv"]


@pytest.fixture
def data(tmp_path):
    """Copie de travail de data/ : les tests n'écrivent jamais dans le dépôt."""
    for nom in FICHIERS:
        shutil.copy(DATA / nom, tmp_path / nom)
    (tmp_path / "depot").mkdir()
    return tmp_path


def test_catalogue_de_depart_dix_series(data):
    r = executer(data, hors_ligne=True)
    assert r.erreurs == {}
    assert r.series["series_id"].nunique() == 10
    comptes = r.series.groupby("series_id").size()
    # Mêmes comptes que macro_rates.csv et fx_usdcad_daily.csv.
    assert comptes["DGS10"] == 1248
    assert comptes["CPIAUCSL"] == 59
    assert comptes["USDCAD"] == 1245
    assert (data / "base" / "series.csv").exists()
    assert (data / "base" / "panel_quotidien.csv").exists()
    assert (data / "base" / "rapport_qualite.txt").exists()


def test_date_disponible_applique_le_delai(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    ipc = r.series[r.series["series_id"] == "CPIAUCSL"]
    assert ((ipc["date_disponible"] - ipc["date"]).dt.days == 45).all()
    taux = r.series[r.series["series_id"] == "DGS10"]
    assert ((taux["date_disponible"] - taux["date"]).dt.days == 1).all()


def test_panel_ne_regarde_pas_le_futur(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    ipc = r.series[r.series["series_id"] == "CPIAUCSL"].set_index("date")["value"]
    # L'IPC de janvier 2024 n'est visible qu'à partir du 15 février 2024 (1er janvier + 45 jours).
    assert r.panel.at[pd.Timestamp("2024-02-14"), "CPIAUCSL"] == ipc[pd.Timestamp("2023-12-01")]
    assert r.panel.at[pd.Timestamp("2024-02-15"), "CPIAUCSL"] == ipc[pd.Timestamp("2024-01-01")]
    # Chaque jour, la valeur du panel est une observation déjà publiée.
    for jour in pd.to_datetime(["2022-06-15", "2023-03-01", "2025-09-30"]):
        publiees = r.series[(r.series["series_id"] == "UNRATE") & (r.series["date_disponible"] <= jour)]
        assert r.panel.at[jour, "UNRATE"] == publiees.sort_values("date")["value"].iloc[-1]


def test_panel_jours_ouvrables_sans_doublon(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    assert r.panel.index.is_unique
    assert (r.panel.index.dayofweek < 5).all()
    assert r.panel.shape[1] == 10


def test_fichier_depose_est_detecte_et_ajoute(data):
    (data / "depot" / "spreads.csv").write_text(
        "date,haut_rendement,note\n2024-01-31,3.5,a\n2024-02-29,3.2,b\n2024-03-31,3.1,c\n",
        encoding="utf-8",
    )
    r = executer(data, hors_ligne=True)
    assert r.ajoutees_au_catalogue == ["spreads_haut_rendement"]  # la colonne texte est ignorée
    cat = lire_catalogue(data / "catalogue.csv")
    ligne = cat[cat["series_id"] == "spreads_haut_rendement"].iloc[0]
    assert ligne["frequence"] == "mensuelle"
    assert ligne["source"] == A_COMPLETER
    assert "spreads_haut_rendement" in r.panel.columns
    assert any("à compléter" in l for l in r.rapport)
    meta = pd.read_csv(data / "sources_metadata.csv")
    assert meta["content"].str.startswith("spreads_haut_rendement :").sum() == 1
    # Relancer ne duplique rien.
    r2 = executer(data, hors_ligne=True)
    assert r2.ajoutees_au_catalogue == []
    meta = pd.read_csv(data / "sources_metadata.csv")
    assert meta["content"].str.startswith("spreads_haut_rendement :").sum() == 1


def test_serie_en_ligne_sans_copie_est_signalee_sans_bloquer(data):
    cat = pd.read_csv(data / "catalogue.csv", dtype=str, keep_default_na=False)
    cat.loc[len(cat)] = ["VIXCLS", "fred", "VIXCLS", "", "Indice VIX", "indice", "quotidienne", "1", "", ""]
    cat.to_csv(data / "catalogue.csv", index=False)
    r = executer(data, hors_ligne=True)
    assert "VIXCLS" in r.erreurs
    assert r.series["series_id"].nunique() == 10  # les autres séries passent quand même


def test_nettoyer_rejette_et_dedoublonne():
    brut = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-01", "2024-01-02", "pas une date", "2024-01-03"],
        "value": ["1.5", "1.0", "2.5", "3", "."],
    })
    df, stats = nettoyer(brut)
    assert stats == {"rejetees": 2, "doublons": 1}
    assert list(df["value"]) == [1.0, 2.5]
    assert df["date"].is_monotonic_increasing


def test_deviner_frequence():
    assert deviner_frequence(pd.Series(pd.bdate_range("2024-01-01", periods=30))) == "quotidienne"
    assert deviner_frequence(pd.Series(pd.date_range("2024-01-01", periods=12, freq="MS"))) == "mensuelle"
    assert deviner_frequence(pd.Series(pd.date_range("2024-01-01", periods=8, freq="QS"))) == "trimestrielle"


def test_catalogue_avec_identifiant_en_double(data):
    cat = pd.read_csv(data / "catalogue.csv", dtype=str, keep_default_na=False)
    cat = pd.concat([cat, cat.iloc[[0]]], ignore_index=True)
    cat.to_csv(data / "catalogue.csv", index=False)
    with pytest.raises(ErreurIngestion, match="en double"):
        executer(data, hors_ligne=True)


def test_panel_vide():
    vide = pd.DataFrame(columns=["date", "series_id", "value", "date_disponible"])
    assert panel_quotidien(vide).empty
