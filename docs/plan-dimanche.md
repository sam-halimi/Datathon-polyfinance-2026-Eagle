# Plan du dimanche 15 novembre

État au dimanche 11 h 45. Le travail des quatre branches est réuni et testé ensemble (211 tests au vert) ; une fois la demande de fusion « Intégration du dimanche » validée, `main` le contient. Le pipeline d'agents n'existe pas encore : c'est la priorité absolue.

## Ce qui est prêt

| Brique | Où | État |
| --- | --- | --- |
| Outils de calcul | `tools/` | Fonctions testées sur les vrais CSV, chacune avec sa référence d'appel |
| Contrôles de gouvernance | `tools/gouvernance.py` | `verifier_contraintes` rejette les demandes piège de Robert et d'Amira |
| Données macro | `data/base/` | FRED en direct avec dates de publication réelles, panel sans regard vers le futur |
| ESG et FNB | `data/esg_actions.csv`, `data/fnb_composition.csv` | 20 actions sourcées, composition de SPY, QQQ, XIU.TO, 9 lignes d'ESGV |
| Profil et scénarios | `agents/profil.py`, `tests/scenarios/` | Schéma validé, trois scénarios avec contrôles automatiques |
| Bedrock | `tools/bedrock.py`, `agents/modele.py` | `creer_agent` répond par Bedrock dans le cloud (secret réseau) |
| Interface | `web/` | Parcours complet à 390 px sur des données d'exemple |

## Ce qui manque, par ordre de priorité

1. **Le pipeline** (`agents/`) : orchestrateur, spécialistes, constructeur, gouvernance, explication. Scénario Robert de bout en bout d'abord.
2. **Le format de sortie** (`docs/sortie-pipeline.md`) : l'interface l'attend pour remplacer l'exemple. Point de départ : `web/lib/types.ts`.
3. **Le branchement interface et pipeline** : tant qu'il n'est pas fait, n'importe quelles réponses donnent le portefeuille d'exemple.
4. **Les livrables** : vidéo de démonstration, documentation technique, one pager, README du dépôt.
5. **Le déploiement sur AWS** (AgentCore, site) : seulement si les quatre premiers points sont faits.

## Décisions prises pour avancer

- **Une seule table de limites.** `agents/profil.py::contraintes(profil)` fait foi pour les poids (par titre, crypto, part risquée, par secteur, nombre de lignes). `tools/gouvernance.py` garde ses seuils de volatilité et de pire baisse, et doit recevoir les limites de poids du profil au lieu d'utiliser les siennes (aujourd'hui le plafond par secteur diffère : 20 % et 30 % côté profil, 25 % et 35 % côté outils).
- **Robert est « avancé ».** L'énoncé dit « Expérience en investissement : avancée ». Son explication s'ouvre donc au niveau 3. Le scénario le notait « débutant » : corrigé.
- **Instantané des données.** Les tests et `docs/contexte.md` suivent `data/base/` tel qu'il est dans le dépôt (FRED jusqu'au 12 novembre 2026). On ne relance pas l'ingestion aujourd'hui, sinon les chiffres attendus bougent.
- **Regard à travers les FNB.** `verifier_contraintes` ne voit pas encore ce que contient un FNB. À brancher sur `data/fnb_composition.csv` et `data/esg_actions.csv` (lire avec `keep_default_na=False`, le symbole `NA` de la Banque Nationale sinon disparaît).
- **Sources ESG.** Les extraits de `data/esg_sources.csv` passés par un outil de résumé ne se citent pas mot pour mot. L'agent cite le résumé et l'adresse de la source.

## Compte AWS

Il est supprimé lundi 16 novembre avec toutes ses données. La vidéo de démonstration s'enregistre pendant qu'il tourne.

## Consignes du jour

### Session `agents`

```
Travaille sur la branche agents. Mets-toi à jour : git fetch origin && git merge origin/main. Lis docs/plan-dimanche.md, CLAUDE.md et docs/donnees-esg-fnb.md.

1. Construis le pipeline dans agents/ avec creer_agent : orchestrateur, spécialiste marché et risque, constructeur (2 ou 3 portefeuilles simulés), gouvernance (tools.gouvernance.verifier_contraintes, 2 essais au plus), explication à trois niveaux. Fais passer le scénario Robert de bout en bout, sur Bedrock pour de vrai, et montre-moi la sortie.
2. Applique la décision « une seule table de limites » du plan : la gouvernance reçoit les limites de contraintes(profil).
3. Écris docs/sortie-pipeline.md (format JSON de la sortie) en partant de web/lib/types.ts, puis pousse sur agents tout de suite pour débloquer l'interface.
4. Ajoute les spécialistes macro et ESG (data/esg_actions.csv, data/fnb_composition.csv), puis fais passer Amira et Mateo.

Chaque chiffre vient de tools/ avec sa référence. « Portefeuille simulé », « assistant », jamais « conseil ». Petits commits, pousse sur agents après chaque étape, sans attendre mon feu vert entre les étapes 1, 2 et 3.
```

### Session `interface`

```
Travaille sur la branche interface. Mets-toi à jour : git fetch origin && git merge origin/main. Lis docs/plan-dimanche.md.

1. Corrige l'exemple : Robert a une expérience « avancée » (énoncé), et les chiffres de taux suivent docs/contexte.md mis à jour.
2. Dès que docs/sortie-pipeline.md existe sur origin/agents (vérifie avec git fetch), branche les six cartes sur ce format : l'interface lit un fichier JSON produit par le pipeline pour chacun des trois personas, et la pastille « Exemple » disparaît quand la donnée vient du pipeline.
3. Ajoute un écran de choix du persona pour la démonstration (Amira, Mateo, Robert), en plus du parcours libre.

Pas de voix tant que ces trois points ne sont pas faits. Petits commits, pousse sur interface.
```

### Session `outils`

```
Travaille sur la branche outils. Mets-toi à jour : git fetch origin && git merge origin/main. Lis docs/plan-dimanche.md et docs/donnees-esg-fnb.md.

Branche data/fnb_composition.csv et data/esg_actions.csv dans tools/gouvernance.py : exposition réelle à un titre ou à un secteur à travers les FNB détenus, et contrôle « énergies fossiles » et « controverses » pour un profil comme Mateo, avec le statut « information manquante » quand la table ne sait pas. verifier_contraintes accepte les limites de poids fournies par agents/profil.py::contraintes(profil). Tests sur les trois personas. Petits commits, pousse sur outils, puis ouvre une demande de fusion vers main.
```

### Session `livrables` (nouvelle)

```
Crée la branche livrables à partir de origin/main. Lis docs/enonce.txt (section « Livrables attendus » et grille), CLAUDE.md, docs/contexte.md et docs/plan-dimanche.md.

Écris dans livrables/ : la documentation technique (méthodes et justification, sources et traitements, mécanisme d'explicabilité avec un exemple réel reliant une conclusion à sa référence d'appel, validations, limites, améliorations), le one pager (une page), et le plan minuté de la vidéo de démonstration de cinq minutes (Robert puis Amira). Mets à jour le README du dépôt : dépendances, sources de données, configuration, démarrage, reproduction. N'invente aucun résultat : ce qui n'existe pas encore dans le dépôt est marqué « à compléter » avec le fichier attendu. Pousse sur livrables.
```
