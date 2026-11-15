import io
import json
import shutil
import urllib.error

import pandas as pd
import pytest

from tools.ingestion import (
    A_COMPLETER,
    DATA,
    DEBUT,
    ErreurIngestion,
    deviner_frequence,
    executer,
    lire_catalogue,
    nettoyer,
    panel_quotidien,
)

FICHIERS = ["catalogue.csv", "macro_rates.csv", "fx_usdcad_daily.csv", "sources_metadata.csv"]
SERIES_FRED = ["DFF", "DGS2", "DGS10", "CPIAUCSL", "UNRATE"]


@pytest.fixture
def data(tmp_path):
    """Copie de travail de data/ : les tests n'écrivent jamais dans le dépôt."""
    for nom in FICHIERS:
        shutil.copy(DATA / nom, tmp_path / nom)
    (tmp_path / "depot").mkdir()
    # Copies FRED gardées dans le dépôt : le mode hors ligne marche sans réseau.
    shutil.copytree(DATA / "base" / "brut", tmp_path / "base" / "brut")
    return tmp_path


def test_catalogue_de_depart_dix_series(data):
    r = executer(data, hors_ligne=True)
    assert r.erreurs == {}
    assert r.series["series_id"].nunique() == 10
    comptes = r.series.groupby("series_id").size()
    # Mêmes comptes que macro_rates.csv et fx_usdcad_daily.csv.
    assert comptes["DGS10"] == 1249  # copie FRED du 2026-11-15
    assert comptes["CPIAUCSL"] == 59
    assert comptes["USDCAD"] == 1245
    assert (data / "base" / "series.csv").exists()
    assert (data / "base" / "panel_quotidien.csv").exists()
    assert (data / "base" / "rapport_qualite.txt").exists()


def test_catalogue_lit_les_cinq_series_americaines_sur_fred():
    cat = lire_catalogue(DATA / "catalogue.csv").set_index("series_id")
    for sid in SERIES_FRED:
        assert cat.at[sid, "fournisseur"] == "fred" and cat.at[sid, "code"] == sid
        copie = pd.read_csv(DATA / "base" / "brut" / f"{sid}.csv")
        assert list(copie.columns) == ["date", "value", "date_publication"]
        assert copie["date_publication"].notna().all()


def test_date_disponible_applique_le_delai_aux_fichiers(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    ipc_ca = r.series[r.series["series_id"] == "STATIC_TOTALCPICHANGE"]
    assert ((ipc_ca["date_disponible"] - ipc_ca["date"]).dt.days == 55).all()
    taux = r.series[r.series["series_id"] == "BD.CDN.10YR.DQ.YLD"]
    assert ((taux["date_disponible"] - taux["date"]).dt.days == 1).all()


def test_date_disponible_fred_est_la_premiere_publication(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    ipc = r.series[r.series["series_id"] == "CPIAUCSL"].set_index("date")["date_disponible"]
    # IPC de janvier 2024 publié par le BLS le 13 février 2024 (et non 1er janvier + 45 jours).
    assert ipc[pd.Timestamp("2024-01-01")] == pd.Timestamp("2024-02-13")
    # Taux du jeudi 28 mars 2024 publié le vendredi 29.
    taux = r.series[r.series["series_id"] == "DGS10"].set_index("date")["date_disponible"]
    assert taux[pd.Timestamp("2024-03-28")] == pd.Timestamp("2024-03-29")
    for sid in SERIES_FRED:
        g = r.series[r.series["series_id"] == sid]
        assert (g["date_disponible"] > g["date"]).all()
    rapport = "\n".join(r.rapport)
    assert "dates de publication réelles pour 59 observations sur 59" in rapport
    assert "délai réel 37 à 53 j" in rapport  # IPC américain


def test_panel_ne_regarde_pas_le_futur(data):
    r = executer(data, hors_ligne=True, ecrire=False)
    ipc = r.series[r.series["series_id"] == "CPIAUCSL"].set_index("date")["value"]
    # L'IPC de janvier 2024 n'est visible qu'à partir du 13 février 2024, jour de sa publication.
    assert r.panel.at[pd.Timestamp("2024-02-12"), "CPIAUCSL"] == ipc[pd.Timestamp("2023-12-01")]
    assert r.panel.at[pd.Timestamp("2024-02-13"), "CPIAUCSL"] == ipc[pd.Timestamp("2024-01-01")]
    ipc_ca = r.series[r.series["series_id"] == "STATIC_TOTALCPICHANGE"].set_index("date")["value"]
    # IPC canadien de janvier 2024 : 1er janvier + 55 jours = 25 février (dimanche), visible le 26.
    assert r.panel.at[pd.Timestamp("2024-02-23"), "STATIC_TOTALCPICHANGE"] == ipc_ca[pd.Timestamp("2023-12-01")]
    assert r.panel.at[pd.Timestamp("2024-02-26"), "STATIC_TOTALCPICHANGE"] == ipc_ca[pd.Timestamp("2024-01-01")]
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


# --- API officielle de FRED (réponses simulées, aucun appel réseau) ---------

def _ajouter_serie_fred(data):
    cat = pd.read_csv(data / "catalogue.csv", dtype=str, keep_default_na=False)
    cat.loc[len(cat)] = ["VIXCLS", "fred", "VIXCLS", "", "Indice VIX", "indice", "quotidienne", "1", "", ""]
    cat.to_csv(data / "catalogue.csv", index=False)


def _faux_fred(publication_en_panne=None):
    """FRED simulé pour VIXCLS. Les autres séries échouent : la copie locale prend le relais.

    `publication_en_panne` : None, ou l'exception levée par l'appel output_type=4.
    """
    valeurs = [{"realtime_start": "2026-11-14", "realtime_end": "2026-11-14", "date": d, "value": v}
               for d, v in [("2026-11-09", "17.5"), ("2026-11-10", "18.25"), ("2026-11-11", "."), ("2026-11-12", "19.0")]]
    sorties = [{"realtime_start": s, "realtime_end": "9999-12-31", "date": d, "value": "0"}
               for d, s in [("2026-11-09", "2026-11-10"), ("2026-11-10", "2026-11-12"), ("2026-11-12", "2026-11-13")]]
    appels = []

    def telecharger(url):
        if "series_id=VIXCLS" not in url:
            raise OSError("hors du test")
        appels.append(url)
        if "output_type=4" in url:
            if publication_en_panne is not None:
                raise publication_en_panne
            return json.dumps({"observations": sorties}).encode()
        return json.dumps({"observations": valeurs}).encode()

    return telecharger, appels


def _erreur_http_fred(message):
    corps = json.dumps({"error_code": 400, "error_message": message}).encode()
    return urllib.error.HTTPError("https://api.stlouisfed.org/...", 400, "Bad Request", {}, io.BytesIO(corps))


def test_fred_avec_cle_utilise_les_dates_de_publication_reelles(data, monkeypatch):
    _ajouter_serie_fred(data)
    telecharger, appels = _faux_fred()
    monkeypatch.setenv("FRED_API_KEY", "cle-secrete-de-test")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    r = executer(data)
    assert r.erreurs == {}
    vix = r.series[r.series["series_id"] == "VIXCLS"].set_index("date")
    assert len(vix) == 3  # la valeur "." est rejetée
    # Publiée le 12 et non le 11 : la date réelle remplace le délai d'un jour du catalogue.
    assert vix.at[pd.Timestamp("2026-11-10"), "date_disponible"] == pd.Timestamp("2026-11-12")
    assert vix.at[pd.Timestamp("2026-11-09"), "value"] == 17.5
    assert all("api.stlouisfed.org" in u for u in appels) and len(appels) == 2
    # Période réelle bornée au début de la fenêtre : 1776 dépasse la limite de FRED.
    assert f"realtime_start={DEBUT}" in appels[1] and "1776" not in appels[1]
    # La clé ne sort ni dans le rapport ni dans les fichiers écrits.
    assert "cle-secrete-de-test" not in "\n".join(r.rapport)
    for f in (data / "base").rglob("*"):
        if f.is_file():
            assert "cle-secrete-de-test" not in f.read_text(encoding="utf-8")
    assert (data / "base" / "brut" / "VIXCLS.csv").exists()  # copie locale pour le mode hors ligne
    assert executer(data, hors_ligne=True).erreurs == {}


def test_fred_avec_cle_sans_dates_de_publication_retombe_sur_le_delai(data, monkeypatch):
    _ajouter_serie_fred(data)
    telecharger, _ = _faux_fred(publication_en_panne=OSError("panne simulée"))
    monkeypatch.setenv("FRED_API_KEY", "cle-secrete-de-test")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    r = executer(data, ecrire=False)
    vix = r.series[r.series["series_id"] == "VIXCLS"]
    assert ((vix["date_disponible"] - vix["date"]).dt.days == 1).all()
    # L'échec n'est plus silencieux : il est dans le rapport, sur la ligne de la série.
    bloc = "\n".join(r.rapport).split("OK      VIXCLS")[1].split("\nOK")[0]
    assert "dates de publication indisponibles (panne simulée)" in bloc


def test_fred_erreur_de_premiere_publication_donne_le_message_exact(data, monkeypatch):
    _ajouter_serie_fred(data)
    message = ("Bad Request.  There are 5149 vintage dates in the specified real-time period: "
               "1776-07-04 to 9999-12-31.  This exceeds the maximum number of vintage dates "
               "allowed for this file type (2000).")
    telecharger, _ = _faux_fred(publication_en_panne=_erreur_http_fred(message))
    monkeypatch.setenv("FRED_API_KEY", "cle-secrete-de-test")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    r = executer(data, ecrire=False)
    assert r.erreurs == {}  # la série passe, avec le délai du catalogue
    rapport = "\n".join(r.rapport)
    assert f"FRED HTTP 400 : {message}" in rapport
    assert "cle-secrete-de-test" not in rapport


def test_fred_erreur_http_sur_les_valeurs_est_une_erreur_lisible(data, monkeypatch):
    _ajouter_serie_fred(data)

    def telecharger(url):
        raise _erreur_http_fred("Bad Request.  The series does not exist.")

    monkeypatch.setenv("FRED_API_KEY", "cle-secrete-de-test")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    r = executer(data, ecrire=False)
    assert r.erreurs["VIXCLS"].endswith("FRED HTTP 400 : Bad Request.  The series does not exist.) "
                                        "et aucune copie locale")
    # Les cinq séries FRED du catalogue retombent sur leur copie locale, et le rapport le dit.
    assert r.series["series_id"].nunique() == 10
    assert sum("copie locale utilisée" in l for l in r.rapport) == 5


def test_fred_sans_cle_utilise_l_export_csv(data, monkeypatch):
    _ajouter_serie_fred(data)
    appels = []

    def telecharger(url):
        if "id=VIXCLS" not in url:
            raise OSError("hors du test")
        appels.append(url)
        return b"observation_date,VIXCLS\n2026-11-09,17.5\n2026-11-10,18.25\n"

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    r = executer(data, ecrire=False)
    assert r.erreurs == {}
    assert (r.series["series_id"] == "VIXCLS").sum() == 2
    assert "fredgraph.csv" in appels[0]
    assert any("pas de FRED_API_KEY" in l for l in r.rapport)


def test_fred_cle_refusee_est_signalee(data, monkeypatch):
    _ajouter_serie_fred(data)
    monkeypatch.setenv("FRED_API_KEY", "mauvaise-cle")
    monkeypatch.setattr("tools.ingestion._telecharger",
                        lambda url: json.dumps({"error_code": 400, "error_message": "Bad Request."}).encode())
    r = executer(data, ecrire=False)
    assert "VIXCLS" in r.erreurs and "Bad Request" in r.erreurs["VIXCLS"]
    assert "mauvaise-cle" not in r.erreurs["VIXCLS"]
    assert r.series["series_id"].nunique() == 10
