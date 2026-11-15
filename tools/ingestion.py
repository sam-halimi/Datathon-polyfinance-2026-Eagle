"""Ingestion des bases financières et macroéconomiques.

Trois façons d'ajouter une base, toutes dans `data/` :

1. Une série FRED : une ligne dans `catalogue.csv` (fournisseur `fred`, code de la série).
2. Une série de la Banque du Canada : une ligne (fournisseur `banque_du_canada`).
3. Un fichier CSV : le déposer dans `depot/`. Il est détecté tout seul et ses
   colonnes numériques sont ajoutées au catalogue.

Puis : `python -m tools.ingestion` (ajouter `--hors-ligne` pour ne rien télécharger).

Sorties dans `data/base/` :

- `series.csv` : toutes les séries au format long, avec `date_disponible`
  (date de l'observation + délai de publication).
- `panel_quotidien.csv` : une ligne par jour ouvrable, une colonne par série.
  Chaque valeur est la dernière qui était publiée ce jour-là : la table est
  utilisable telle quelle pour un modèle ou une simulation, sans regarder le futur.
- `rapport_qualite.txt` : ce qui a été lu, rejeté et signalé.

Les séries ajoutées reçoivent leur ligne dans `sources_metadata.csv`.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from tools.env import charger_env

DATA = Path(__file__).resolve().parent.parent / "data"
DEBUT = "2021-11-12"
FRED_API = "https://api.stlouisfed.org/fred/series/observations"
VARIABLE_CLE_FRED = "FRED_API_KEY"
A_COMPLETER = "À COMPLÉTER"
COLONNES_CATALOGUE = [
    "series_id", "fournisseur", "code", "colonne", "libelle", "unite",
    "frequence", "delai_publication_jours", "source", "url",
]
FOURNISSEURS = ("fichier", "fred", "banque_du_canada")
# Écart maximal attendu entre deux observations, en jours, avant de le signaler.
ECART_MAX = {"quotidienne": 7, "hebdomadaire": 14, "mensuelle": 45,
             "trimestrielle": 100, "annuelle": 400}
# Délais prudents par défaut pour un fichier déposé. À ajuster dans le catalogue.
DELAI_DEFAUT = {"quotidienne": 1, "hebdomadaire": 7, "mensuelle": 45,
                "trimestrielle": 60, "annuelle": 90}
NOMS_DATE = ("date", "dates", "observation_date", "time", "period", "periode")
CONDITIONS = {
    "fred": "FRED terms: https://fred.stlouisfed.org/legal/",
    "banque_du_canada": "Bank of Canada terms: https://www.bankofcanada.ca/terms/",
    "fichier": A_COMPLETER,
}


class ErreurIngestion(Exception):
    """Une série n'a pas pu être lue. Le message dit quoi corriger."""


@dataclass
class Resultat:
    series: pd.DataFrame
    panel: pd.DataFrame
    rapport: list[str]
    erreurs: dict[str, str] = field(default_factory=dict)
    ajoutees_au_catalogue: list[str] = field(default_factory=list)


# --- Lecture ---------------------------------------------------------------

def _telecharger(url: str) -> bytes:
    requete = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return reponse.read()


def _fred_api(code: str, debut: str, fin: str, cle: str, premiere_publication: bool = False) -> list[dict]:
    """Observations d'une série par l'API officielle de FRED (clé gratuite requise).

    Avec `premiere_publication`, FRED renvoie pour chaque observation sa première
    publication : `realtime_start` est alors la date où la valeur est sortie.
    La période réelle commence à `debut` et non en 1776 : FRED refuse plus de
    2 000 dates de révision par appel, et une série quotidienne en a une par jour.
    Une observation datée après `debut` ne peut pas avoir été publiée avant.

    Une erreur de FRED (HTTP 400 compris) remonte avec le message exact de FRED.
    """
    params = {"series_id": code, "api_key": cle, "file_type": "json",
              "observation_start": debut, "observation_end": fin}
    if premiere_publication:
        params |= {"realtime_start": debut, "realtime_end": "9999-12-31", "output_type": "4"}
    try:
        donnees = json.loads(_telecharger(f"{FRED_API}?{urllib.parse.urlencode(params)}"))
    except urllib.error.HTTPError as e:
        try:
            message = json.loads(e.read()).get("error_message", "")
        except Exception:
            message = ""
        raise ErreurIngestion(f"FRED HTTP {e.code} : {message or e.reason}".replace(cle, "<clé>")) from None
    if "observations" not in donnees:
        raise ErreurIngestion(f"FRED : {donnees.get('error_message', 'réponse inattendue')}".replace(cle, "<clé>"))
    return donnees["observations"]


def lire_fred(code: str, debut: str, fin: str) -> pd.DataFrame:
    """Série FRED. Avec la variable d'environnement FRED_API_KEY : API officielle et
    dates de publication réelles. Sans clé : export CSV public, sans dates de publication.

    Si les dates de publication manquent, `df.attrs["avertissement"]` dit pourquoi :
    l'ingestion l'écrit dans le rapport au lieu de l'avaler.
    """
    cle = os.environ.get(VARIABLE_CLE_FRED, "").strip()
    if not cle:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd={debut}&coed={fin}"
        df = pd.read_csv(io.BytesIO(_telecharger(url)))
        if df.shape[1] != 2:
            raise ErreurIngestion(f"FRED n'a pas renvoyé de série pour le code {code!r}.")
        df.columns = ["date", "value"]
        df.attrs["avertissement"] = (f"pas de {VARIABLE_CLE_FRED} : export CSV public, "
                                     "sans dates de publication, délai du catalogue appliqué")
        return df
    obs = _fred_api(code, debut, fin, cle)
    if not obs:
        raise ErreurIngestion(f"FRED n'a renvoyé aucune observation pour le code {code!r}.")
    df = pd.DataFrame({"date": [o["date"] for o in obs], "value": [o["value"] for o in obs]})
    try:
        sorties = {o["date"]: o["realtime_start"] for o in _fred_api(code, debut, fin, cle, True)}
        df["date_publication"] = df["date"].map(sorties)
    except Exception as e:  # le délai du catalogue s'applique, et le rapport le dit
        df.attrs["avertissement"] = (f"dates de publication indisponibles ({e}) : "
                                     "délai du catalogue appliqué")
    return df


def lire_banque_du_canada(code: str, debut: str, fin: str) -> pd.DataFrame:
    url = (f"https://www.bankofcanada.ca/valet/observations/{code}/json"
           f"?start_date={debut}&end_date={fin}")
    donnees = json.loads(_telecharger(url))
    lignes = [(o["d"], o[code].get("v")) for o in donnees.get("observations", []) if code in o]
    if not lignes:
        raise ErreurIngestion(f"La Banque du Canada n'a renvoyé aucune observation pour {code!r}.")
    return pd.DataFrame(lignes, columns=["date", "value"])


def _colonne_date(df: pd.DataFrame) -> str:
    for c in df.columns:
        if str(c).strip().lower() in NOMS_DATE:
            return c
    return df.columns[0]


def lire_fichier(chemin: Path, series_id: str, colonne: str = "") -> pd.DataFrame:
    """Lit une série dans un CSV large (une colonne par série) ou long (`series_id`, `value`)."""
    if not chemin.exists():
        raise ErreurIngestion(f"Fichier introuvable : {chemin}")
    df = pd.read_csv(chemin)
    col_date = _colonne_date(df)
    if colonne:
        if colonne not in df.columns:
            raise ErreurIngestion(f"Colonne {colonne!r} absente de {chemin.name}.")
        valeurs = df[colonne]
    elif {"series_id", "value"} <= set(df.columns):
        df = df[df["series_id"] == series_id]
        if df.empty:
            raise ErreurIngestion(f"Aucune ligne {series_id!r} dans {chemin.name}.")
        valeurs = df["value"]
    else:
        autres = [c for c in df.columns if c != col_date]
        if len(autres) != 1:
            raise ErreurIngestion(
                f"{chemin.name} a plusieurs colonnes : remplir `colonne` dans le catalogue.")
        valeurs = df[autres[0]]
    return pd.DataFrame({"date": df[col_date].values, "value": valeurs.values})


def nettoyer(brut: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Dates et nombres valides seulement, une valeur par date (la dernière), tri par date."""
    df = pd.DataFrame({
        "date": pd.to_datetime(brut["date"], errors="coerce"),
        "value": pd.to_numeric(brut["value"], errors="coerce"),
    })
    if "date_publication" in brut.columns:
        df["date_publication"] = pd.to_datetime(brut["date_publication"], errors="coerce").values
    avant = len(df)
    df = df.dropna(subset=["date", "value"])
    rejetees = avant - len(df)
    doublons = int(df.duplicated("date").sum())
    df = df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    return df, {"rejetees": rejetees, "doublons": doublons}


# --- Catalogue -------------------------------------------------------------

def lire_catalogue(chemin: Path) -> pd.DataFrame:
    cat = pd.read_csv(chemin, dtype=str, keep_default_na=False)
    manquantes = [c for c in COLONNES_CATALOGUE if c not in cat.columns]
    if manquantes:
        raise ErreurIngestion(f"Colonnes absentes de {chemin.name} : {manquantes}")
    if cat["series_id"].duplicated().any():
        doubles = sorted(cat.loc[cat["series_id"].duplicated(), "series_id"])
        raise ErreurIngestion(f"series_id en double dans {chemin.name} : {doubles}")
    return cat[COLONNES_CATALOGUE]


def deviner_frequence(dates: pd.Series) -> str:
    ecart = pd.Series(sorted(pd.to_datetime(dates, errors="coerce").dropna())).diff().dt.days.median()
    if pd.isna(ecart) or ecart <= 4:
        return "quotidienne"
    if ecart <= 10:
        return "hebdomadaire"
    if ecart <= 45:
        return "mensuelle"
    if ecart <= 100:
        return "trimestrielle"
    return "annuelle"


def decouvrir_depot(cat: pd.DataFrame, depot: Path) -> tuple[pd.DataFrame, list[str]]:
    """Ajoute au catalogue les colonnes numériques des CSV de `depot/` qui n'y sont pas."""
    nouvelles = []
    if not depot.is_dir():
        return cat, []
    for chemin in sorted(depot.glob("*.csv")):
        code = f"depot/{chemin.name}"
        if (cat["code"] == code).any():
            continue
        df = pd.read_csv(chemin)
        col_date = _colonne_date(df)
        frequence = deviner_frequence(df[col_date])
        for col in df.columns:
            if col == col_date or pd.to_numeric(df[col], errors="coerce").notna().sum() == 0:
                continue
            nouvelles.append({
                "series_id": f"{chemin.stem}_{col}".replace(" ", "_"),
                "fournisseur": "fichier", "code": code, "colonne": col, "libelle": str(col),
                "unite": A_COMPLETER, "frequence": frequence,
                "delai_publication_jours": str(DELAI_DEFAUT[frequence]),
                "source": A_COMPLETER, "url": A_COMPLETER,
            })
    if not nouvelles:
        return cat, []
    ajout = pd.DataFrame(nouvelles, columns=COLONNES_CATALOGUE)
    ajout = ajout[~ajout["series_id"].isin(cat["series_id"])]
    return pd.concat([cat, ajout], ignore_index=True), list(ajout["series_id"])


# --- Assemblage ------------------------------------------------------------

def _lire_serie(ligne: pd.Series, data: Path, brut: Path, hors_ligne: bool,
                fin: str) -> tuple[pd.DataFrame, str]:
    """Renvoie la série brute et une note (vide, ou origine de la copie utilisée)."""
    fournisseur, sid = ligne["fournisseur"], ligne["series_id"]
    if fournisseur == "fichier":
        return lire_fichier(data / ligne["code"], sid, ligne["colonne"]), ""
    if fournisseur not in FOURNISSEURS:
        raise ErreurIngestion(f"fournisseur inconnu {fournisseur!r} (attendu : {FOURNISSEURS})")
    copie = brut / f"{sid}.csv"
    if not hors_ligne:
        try:
            lecteur = lire_fred if fournisseur == "fred" else lire_banque_du_canada
            df = lecteur(ligne["code"], DEBUT, fin)
            brut.mkdir(parents=True, exist_ok=True)
            df.to_csv(copie, index=False)
            return df, df.attrs.get("avertissement", "")
        except Exception as e:  # réseau, code inconnu : on retombe sur la copie locale
            if not copie.exists():
                raise ErreurIngestion(f"téléchargement impossible ({e}) et aucune copie locale") from e
            return pd.read_csv(copie), f"téléchargement impossible ({e}), copie locale utilisée"
    if not copie.exists():
        raise ErreurIngestion("mode hors ligne et aucune copie locale : relancer sans --hors-ligne")
    return pd.read_csv(copie), "copie locale (hors ligne)"


def _texte_delai(df: pd.DataFrame, delai: int, reelles: int) -> str:
    if reelles < len(df):
        return f"délai {delai} j"
    jours = (df["date_disponible"] - df["date"]).dt.days
    return (f"délai réel {int(jours.min())} à {int(jours.max())} j, médiane {jours.median():g} j "
            f"(catalogue : {delai} j)")


def panel_quotidien(series: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par jour ouvrable, une colonne par série, sans regarder le futur.

    La valeur d'une série un jour J est sa dernière observation dont
    `date_disponible` est inférieure ou égale à J.
    """
    if series.empty:
        return pd.DataFrame()
    jours = pd.bdate_range(series["date"].min(), series["date"].max(), name="date")
    colonnes = {}
    for sid, g in series.groupby("series_id", sort=True):
        s = g.set_index("date_disponible")["value"].sort_index()
        s = s[~s.index.duplicated(keep="last")]
        colonnes[sid] = s.reindex(jours.union(s.index)).ffill().reindex(jours)
    return pd.DataFrame(colonnes, index=jours)


def _limites(ligne: pd.Series, n: int, reelles: int) -> str:
    delai = (f"délai de publication fixé à {ligne['delai_publication_jours']} jours dans "
             "data/catalogue.csv : valeur prudente, pas la date de publication exacte")
    if not reelles:
        return delai[0].upper() + delai[1:]
    texte = (f"date_disponible = date de première publication réelle (FRED, output_type=4) "
             f"pour {reelles} observations sur {n}")
    if reelles < n:
        texte += f" ; pour les autres, {delai}"
    return texte + (" ; valeurs = dernier millésime FRED : une révision postérieure à la première "
                    "publication est visible dès cette date")


def _maj_sources(chemin: Path, series: pd.DataFrame, cat: pd.DataFrame,
                 reelles: dict[str, int] | None = None) -> int:
    """Ajoute ou met à jour la ligne de chaque série ajoutée dans sources_metadata.csv."""
    if not chemin.exists():
        return 0
    meta = pd.read_csv(chemin, dtype=str, keep_default_na=False)
    aujourd_hui = date.today().isoformat()
    n = 0
    for _, ligne in cat.iterrows():
        sid, fournisseur = ligne["series_id"], ligne["fournisseur"]
        d_origine = fournisseur == "fichier" and not ligne["code"].startswith("depot/")
        g = series[series["series_id"] == sid]
        if d_origine or g.empty:
            continue
        url = ligne["url"]
        if not url and fournisseur == "fred":
            url = f"https://fred.stlouisfed.org/series/{ligne['code']}"
        if not url and fournisseur == "banque_du_canada":
            url = f"https://www.bankofcanada.ca/valet/observations/{ligne['code']}/json"
        source = ligne["source"] or {"fred": "FRED, Federal Reserve Bank of St. Louis",
                                     "banque_du_canada": "Bank of Canada Valet API"}.get(fournisseur, A_COMPLETER)
        nouvelle = {
            "file": "base/series.csv", "content": f"{sid} : {ligne['libelle']}",
            "source": source, "source_url": url or A_COMPLETER, "retrieved_on": aujourd_hui,
            "coverage": f"{g['date'].min().date()} to {g['date'].max().date()}",
            "frequency": ligne["frequence"],
            "processing": "tools/ingestion.py : dates et nombres valides, une valeur par date, "
                          "date_disponible = date de première publication si FRED la donne, sinon date + délai de publication",
            "limitations": _limites(ligne, len(g), (reelles or {}).get(sid, 0)),
            "terms_of_use": CONDITIONS.get(fournisseur, A_COMPLETER),
        }
        existe = (meta["file"] == "base/series.csv") & meta["content"].str.startswith(f"{sid} :")
        meta = meta[~existe]
        meta = pd.concat([meta, pd.DataFrame([nouvelle])], ignore_index=True)
        n += 1
    if n:  # ne pas réécrire le fichier des organisateurs s'il n'y a rien à ajouter
        meta.to_csv(chemin, index=False)
    return n


def executer(data: Path = DATA, hors_ligne: bool = False, fin: str | None = None,
             ecrire: bool = True) -> Resultat:
    """Lit le catalogue et le dépôt, nettoie, date et assemble toutes les séries."""
    fin = fin or date.today().isoformat()
    sortie, brut = data / "base", data / "base" / "brut"
    chemin_cat = data / "catalogue.csv"
    cat, ajoutees = decouvrir_depot(lire_catalogue(chemin_cat), data / "depot")

    morceaux, erreurs, publications = [], {}, {}
    rapport = [f"Ingestion du {date.today().isoformat()}, fenêtre {DEBUT} au {fin}.", ""]
    if ajoutees:
        rapport += [f"Nouvelles séries détectées dans depot/ et ajoutées au catalogue : {ajoutees}", ""]
    for _, ligne in cat.iterrows():
        sid = ligne["series_id"]
        try:
            delai = int(ligne["delai_publication_jours"] or 0)
            frequence = ligne["frequence"]
            if frequence not in ECART_MAX:
                raise ErreurIngestion(f"frequence inconnue {frequence!r} (attendu : {sorted(ECART_MAX)})")
            lu, note = _lire_serie(ligne, data, brut, hors_ligne, fin)
            df, stats = nettoyer(lu)
            if df.empty:
                raise ErreurIngestion("aucune observation valide")
        except Exception as e:
            erreurs[sid] = str(e)
            rapport.append(f"ERREUR  {sid} : {e}")
            continue
        df["series_id"] = sid
        df["date_disponible"] = df["date"] + pd.Timedelta(days=delai)
        reelles = 0
        if "date_publication" in df.columns:
            # Date de publication réelle quand FRED la donne et qu'elle est cohérente.
            ok = df["date_publication"].notna() & (df["date_publication"] >= df["date"])
            df.loc[ok, "date_disponible"] = df.loc[ok, "date_publication"]
            reelles = int(ok.sum())
        publications[sid] = reelles
        for champ in ("unite", "frequence", "libelle", "source"):
            df[champ] = ligne[champ]
        morceaux.append(df)

        alertes = [note] if note else []
        if reelles:
            alertes.append(f"dates de publication réelles pour {reelles} observations sur {len(df)}"
                           + (f", délai du catalogue pour les {len(df) - reelles} autres"
                              if reelles < len(df) else ""))
        elif ligne["fournisseur"] == "fred" and "dates de publication" not in note:
            alertes.append("aucune date de publication réelle : délai du catalogue appliqué")
        if stats["rejetees"]:
            alertes.append(f"{stats['rejetees']} lignes rejetées (date ou nombre illisible)")
        if stats["doublons"]:
            alertes.append(f"{stats['doublons']} dates en double (dernière valeur gardée)")
        ecart = df["date"].diff().dt.days.max()
        if pd.notna(ecart) and ecart > ECART_MAX[frequence]:
            alertes.append(f"trou de {int(ecart)} jours pour une série {frequence}")
        if df["value"].nunique() == 1:
            alertes.append("valeur constante")
        if A_COMPLETER in (ligne["source"], ligne["unite"], ligne["url"]):
            alertes.append("source, unité ou adresse à compléter dans data/catalogue.csv")
        rapport.append(f"OK      {sid} : {len(df)} observations, {df['date'].min().date()} au "
                       f"{df['date'].max().date()}, {_texte_delai(df, delai, reelles)}"
                       + ("".join(f"\n        ! {a}" for a in alertes)))

    colonnes = ["date", "series_id", "value", "date_disponible", "unite", "frequence", "libelle", "source"]
    series = (pd.concat(morceaux, ignore_index=True)[colonnes] if morceaux
              else pd.DataFrame(columns=colonnes))
    series = series.sort_values(["series_id", "date"]).reset_index(drop=True)
    panel = panel_quotidien(series)
    rapport += ["", f"{series['series_id'].nunique()} séries, {len(series)} observations, "
                    f"panel de {panel.shape[0]} jours sur {panel.shape[1]} colonnes, {len(erreurs)} erreur(s)."]

    if ecrire:
        sortie.mkdir(parents=True, exist_ok=True)
        series.to_csv(sortie / "series.csv", index=False, date_format="%Y-%m-%d")
        panel.to_csv(sortie / "panel_quotidien.csv", date_format="%Y-%m-%d")
        (sortie / "rapport_qualite.txt").write_text("\n".join(rapport) + "\n", encoding="utf-8")
        if ajoutees:
            cat.to_csv(chemin_cat, index=False)
        _maj_sources(data / "sources_metadata.csv", series, cat, publications)
    return Resultat(series, panel, rapport, erreurs, ajoutees)


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--hors-ligne", action="store_true",
                           help="ne rien télécharger : fichiers locaux et copies déjà enregistrées")
    analyseur.add_argument("--fin", default=None, help="dernière date demandée, AAAA-MM-JJ (défaut : aujourd'hui)")
    args = analyseur.parse_args()
    charger_env()  # clés du fichier .env à la racine, s'il existe
    try:
        resultat = executer(hors_ligne=args.hors_ligne, fin=args.fin)
    except ErreurIngestion as e:
        print(f"ERREUR : {e}")
        return 1
    print("\n".join(resultat.rapport))
    return 1 if resultat.erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
