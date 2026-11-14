# AlphaForge AI — Datathon PolyFinances 2026

Assistant agentique qui propose des portefeuilles simulés adaptés à un profil d'investisseur et explique chaque choix. Simulation uniquement, aucun conseil en placement.

## Par où commencer

1. Lire `CLAUDE.md` : règles de l'énoncé, pipeline, outils, interface.
2. Lire `docs/contexte.md` : décisions prises, chiffres déjà vérifiés, questions ouvertes.
3. Prendre sa branche et coller sa consigne de `docs/consignes-de-depart.md` dans Claude Code.

## Arborescence

| Dossier | Contenu |
| --- | --- |
| `CLAUDE.md` | Contexte lu par Claude Code à chaque session |
| `docs/` | Énoncé officiel, contexte, consignes de départ |
| `data/` | Jeu de données de départ, `build_dataset.py`, sources |
| `analyses/` | Scripts de contrôle déjà exécutés sur les données |
| `tools/` | Fonctions de calcul Python (à écrire) |
| `tests/scenarios/` | Tests d'acceptation par persona (à écrire) |

## Branches

- `outils` : `tools/`, `data/`, tests
- `agents` : pipeline, AWS, scénarios
- `interface` : site, cartes, voix

Fusion dans `main` par petites demandes de tirage.

## Vérifier les données

```bash
python analyses/controle_donnees.py
python analyses/exemples_explications.py
```
