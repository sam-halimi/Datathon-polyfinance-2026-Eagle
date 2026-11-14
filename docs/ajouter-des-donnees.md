# Ajouter une base de données

Tout se passe dans `data/`. Après chaque ajout :

```bash
python -m tools.ingestion
```

Ajouter `--hors-ligne` pour ne rien télécharger (fichiers locaux et copies déjà enregistrées).

## Trois façons d'ajouter

### 1. Déposer un fichier

Mettre un CSV dans `data/depot/`, avec une colonne `date` et une colonne par série. C'est tout : chaque colonne numérique devient une série, ajoutée toute seule à `data/catalogue.csv`.

Ensuite, compléter dans le catalogue les cases marquées `À COMPLÉTER` : unité, source, adresse. Le rapport les rappelle tant qu'elles sont vides.

### 2. Une série FRED

Une ligne dans `data/catalogue.csv`. Exemple pour l'indice VIX :

```
VIXCLS,fred,VIXCLS,,Indice de volatilité VIX,indice,quotidienne,1,,
```

Le code est celui de la page de la série sur fred.stlouisfed.org. Si le code n'existe pas, l'ingestion le dit et continue avec les autres.

#### Avec une clé FRED (recommandé)

Créer une clé gratuite sur fred.stlouisfed.org (compte, puis « API Keys ») et la mettre dans la variable d'environnement `FRED_API_KEY`. Jamais dans un fichier du dépôt : `.env` est ignoré par git.

```bash
export FRED_API_KEY=ta_cle
python -m tools.ingestion
```

Avec la clé, l'ingestion passe par l'API officielle et récupère la date de première publication de chaque observation. `date_disponible` devient alors la vraie date de sortie, et non plus `date + délai`. Le rapport indique pour combien d'observations. Sans clé, l'export public de FRED est utilisé et le délai du catalogue s'applique.

FRED n'est pas du temps réel au sens d'un flux en direct : les séries les plus rapides sont quotidiennes. « À jour » veut dire relancer l'ingestion, à la main ou par une tâche planifiée.

Pour mettre à jour les cinq séries américaines de départ au lieu de lire le fichier des organisateurs, remplacer dans le catalogue `fichier` par `fred` et `macro_rates.csv` par le code de la série (`DFF`, `DGS2`, `DGS10`, `CPIAUCSL`, `UNRATE`).

### 3. Une série de la Banque du Canada

Même principe, fournisseur `banque_du_canada`, avec le code de l'API Valet.

## Colonnes du catalogue

| Colonne | Contenu |
| --- | --- |
| `series_id` | Nom de la série dans nos tables, unique |
| `fournisseur` | `fichier`, `fred` ou `banque_du_canada` |
| `code` | Chemin du fichier dans `data/`, ou code de la série chez le fournisseur |
| `colonne` | Colonne à lire dans un fichier large. Vide pour un fichier long (`date, series_id, value`) |
| `libelle`, `unite` | Ce qui s'affiche à l'utilisateur |
| `frequence` | `quotidienne`, `hebdomadaire`, `mensuelle`, `trimestrielle`, `annuelle` |
| `delai_publication_jours` | Nombre de jours entre la date de l'observation et sa publication |
| `source`, `url` | D'où vient la donnée |

## Le délai de publication

Une donnée mensuelle est datée du mois qu'elle décrit, mais publiée plusieurs semaines après. L'ingestion calcule `date_disponible = date + délai`, et le panel n'utilise une valeur qu'à partir de cette date. C'est ce qui empêche une simulation de voir le futur.

Les délais du catalogue de départ (45 jours pour l'IPC américain, 40 pour le chômage américain, 55 pour l'IPC canadien, 1 pour les séries quotidiennes) sont des valeurs prudentes, pas les dates de publication exactes. À ajuster si on trouve le calendrier officiel.

## Ce qui sort, dans `data/base/`

| Fichier | Contenu | Pour qui |
| --- | --- | --- |
| `series.csv` | Toutes les séries au format long, avec `date_disponible` | Agents macro, explications |
| `panel_quotidien.csv` | Une ligne par jour ouvrable, une colonne par série, sans regarder le futur | Machine learning, simulations |
| `rapport_qualite.txt` | Lignes rejetées, doublons, trous, sources à compléter | À lire après chaque ajout |

Chaque série ajoutée reçoit sa ligne dans `data/sources_metadata.csv`, comme l'exige l'énoncé.

## Ce que le contrôle a déjà trouvé

Octobre 2025 manque dans l'IPC américain (`CPIAUCSL`) et le chômage américain (`UNRATE`) : 59 observations au lieu de 60. Le trou est dans les données d'origine. Il ne faut pas le combler en silence : le panel garde la valeur de septembre jusqu'à la publication de novembre, et l'explication doit le dire si elle cite ces séries sur cette période.

## Pour le machine learning

`panel_quotidien.csv` est la table d'entrée : une ligne par jour, toutes les séries alignées, chaque valeur étant la dernière connue ce jour-là.

L'énoncé ne demande pas de prédire les rendements et rappelle que les performances passées ne garantissent rien. Les usages qui tiennent face au jury sont descriptifs : regrouper les périodes en régimes macro (taux en hausse, inflation élevée), regrouper les actifs qui bougent ensemble, mesurer la sensibilité d'un actif à une série. Chaque résultat passe par une fonction de `tools/` avec sa référence d'appel.
