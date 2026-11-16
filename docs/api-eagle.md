# Serveur local d'Eagle

L'interface parle à un petit serveur Python, lancé sur la machine où les clés fonctionnent.

```bash
python -m agents.serveur        # http://localhost:8000
```

| Route | Rôle | Clés |
| --- | --- | --- |
| `GET /sante` | Vérifie que le serveur répond | Non |
| `GET /actif?symbole=tesla&tolerance=faible&horizon=3` | Fiche d'un actif face à un profil : statut (`compatible`, `à plafonner`, `hors profil`, `inconnu`), titre, raisons chiffrées, références des chiffres | Non |
| `POST /scenarios` avec `{"poids": {...}, "horizon_annees": 8, "capital": 50000}` | Éventail de scénarios d'un portefeuille | Non |
| `GET /demonstration/robert` (ou `amira`, `mateo`) | Sortie enregistrée d'un persona, avec son éventail | Non |
| `POST /analyse` avec `{"profil": {...}, "demande": "...", "prenom": "..."}` | Pipeline complet sur Bedrock pour n'importe quel profil, environ une minute | Oui |
| `GET /progression?id=<suivi>` | Où en est l'analyse lancée avec `"suivi": "<id>"` dans le corps de `POST /analyse` (un identifiant choisi par l'appelant, 8 à 64 lettres, chiffres ou tirets) : `phase` (`analyse`, `traduction`, `terminee`, `echec`), `agent` en cours, `essai`, `faits` (ce que les agents ont fini), `ecoule`. Identifiant inconnu : `{"connu": false}` | Non |

Option anglaise : `langue=en` (paramètre d'adresse en GET, champ `"langue": "en"` du corps en POST) renvoie les mêmes données avec leurs textes traduits (`agents/traduction.py`).

Le profil suit le schéma de `python -m agents.profil`. Le curseur de connaissance d'Eagle s'envoie dans `connaissance_niveau` (1 à 5) ; `connaissance` peut alors être omise, elle en découle (1-2 débutant, 3 intermédiaire, 4-5 avancé). Tout autre champ inconnu est refusé (400). La réponse de `/analyse` suit `docs/sortie-pipeline.md`, avec un champ `scenarios` en plus.

## Le champ `scenarios`

Référence complète de `tools.scenarios.eventail_scenarios`. Dans `valeur` : `annees` (0 à l'horizon) et cinq séries de même longueur, `p10`, `p25`, `p50`, `p75`, `p90`, en valeur du portefeuille simulé.

À afficher : la médiane (`p50`) en trait, les bandes `p25` à `p75` et `p10` à `p90` en aplats, le titre « Scénarios, pas une prévision », puis `details.avertissement` et `details.hypotheses` sous le graphique.

## Erreurs

Une requête mal formée renvoie le code 400 avec `{"erreur": "..."}`. Un échec du pipeline renvoie 500 ; le détail s'affiche dans le terminal du serveur.
