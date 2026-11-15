# AlphaForge AI — Datathon PolyFinances 2026, équipe 37

Un assistant agentique qui propose des portefeuilles **simulés** adaptés à un profil d'investisseur, relève les demandes qui contredisent ce profil et explique chaque choix. Chaque chiffre affiché renvoie à son calcul.

Simulation uniquement : aucun conseil en placement, aucune transaction réelle.

## Livrables

| Livrable | Où |
| --- | --- |
| Documentation technique | [`livrables/documentation-technique.md`](livrables/documentation-technique.md) |
| One pager | [`livrables/one-pager.md`](livrables/one-pager.md) |
| Plan de la vidéo de démonstration | [`livrables/plan-video.md`](livrables/plan-video.md) |
| Prototype | `agents/` (pipeline), `tools/` (calculs), `web/` (interface) |

## Ce que contient le dépôt

| Dossier | Contenu |
| --- | --- |
| `agents/` | Pipeline d'agents (Strands Agents sur Amazon Bedrock), profil, gouvernance, journal des chiffres. `agents/sorties/` : sorties réelles pour Robert, Amira et Mateo |
| `tools/` | Fonctions de calcul testées (rendement, volatilité, pire baisse, corrélations, parts du risque, sensibilité aux taux, contrôles), ingestion des données |
| `web/` | Interface Next.js, conçue pour téléphone |
| `data/` | Jeu de départ des organisateurs, données ajoutées (macro, ESG, composition des FNB), `sources_metadata.csv` |
| `tests/` | 239 tests automatiques, dont les scénarios d'acceptation des trois personas |
| `docs/` | Énoncé, contexte et décisions, format de sortie du pipeline, ajout de données |
| `analyses/` | Scripts de contrôle indépendants des données |

## Dépendances

- Python 3.10 ou plus récent
- Node.js 20 ou plus récent, pour l'interface

```bash
pip install -r tools/requirements.txt strands-agents pydantic
```

## Sources de données

Prix : Yahoo Finance (jeu de départ). Change et taux canadiens : Banque du Canada. Taux, inflation et chômage américains : FRED. ESG : dépôts SEC EDGAR et pages officielles de régulateurs. Composition des FNB : sites des émetteurs et formulaire SEC.

Le détail de chaque fichier (source, adresse, date, traitement, limites, conditions d'utilisation) est dans [`data/sources_metadata.csv`](data/sources_metadata.csv). Pour ajouter une base : [`docs/ajouter-des-donnees.md`](docs/ajouter-des-donnees.md).

## Configuration

Deux clés, jamais dans le dépôt :

```bash
cp .env.example .env    # puis coller FRED_API_KEY et AWS_BEARER_TOKEN_BEDROCK
python -m tools.verifier_cles
```

La commande doit afficher trois `[OK]` : les clés, FRED, puis Bedrock avec un agent qui retrouve un chiffre connu. Région Bedrock utilisée : `us-east-1`.

## Démarrage

**Sans aucune clé** : les tests et l'interface fonctionnent avec les données et les sorties déjà dans le dépôt.

```bash
python -m pytest -q                 # 239 tests
cd web && npm install && npm run dev  # http://localhost:3000
```

**Avec les clés** : relancer le pipeline sur Bedrock.

```bash
python -m agents.pipeline robert amira mateo   # écrit agents/sorties/*.json, environ une minute par persona
```

## Reproduire les données

```bash
python data/build_dataset.py     # jeu de départ (script des organisateurs)
python -m tools.ingestion        # séries macro : data/base/series.csv et panel_quotidien.csv
python analyses/controle_donnees.py
```

Les tests et `docs/contexte.md` suivent les données telles qu'elles sont dans le dépôt (FRED jusqu'au 12 novembre 2026). Relancer l'ingestion plus tard fait bouger ces chiffres.

## Comment ça marche, en bref

1. **Accueil** : huit questions, puis un récapitulatif à valider.
2. **Orchestrateur** : lit la demande et fixe les limites du profil.
3. **Spécialistes** : marché et risque, macro et taux, ESG.
4. **Constructeur** : deux ou trois portefeuilles simulés.
5. **Gouvernance** : contrôles en code. Un rejet retourne au constructeur, deux essais au plus.
6. **Explication** : trois niveaux, plus les faits, les hypothèses et les limites.

Règle tenue par la machine : aucun texte écrit par un modèle ne contient de chiffre. Les textes portent des repères, et chaque repère renvoie à l'appel d'outil qui a produit la valeur. Format complet : [`docs/sortie-pipeline.md`](docs/sortie-pipeline.md).
