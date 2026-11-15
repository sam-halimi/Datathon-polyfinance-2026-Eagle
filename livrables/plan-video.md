# Plan de la vidéo de démonstration (5 minutes)

Enregistrement d'écran avec voix. À enregistrer pendant que le compte AWS tourne. Dire « portefeuille simulé » et « assistant », jamais « conseil ».

## Avant d'enregistrer

- Le site tourne (`cd web && npm run dev`), fenêtre du navigateur à la largeur d'un téléphone.
- Un terminal ouvert à la racine du dépôt, police agrandie.
- `python -m tools.verifier_cles` affiche trois `[OK]`.
- Notifications coupées.

## Déroulé

| Temps | À l'écran | À dire |
| --- | --- | --- |
| 0:00 à 0:30 | Titre, puis l'écran de départ du site | Le problème : un outil qui dit oui à tout est dangereux. Robert, 59 ans, veut 40 % sur Tesla. Notre assistant sait dire non, et le prouver. |
| 0:30 à 1:00 | Schéma du pipeline (`docs/` ou diapositive) | Sept agents, un rôle chacun. Deux règles : le code calcule, le modèle explique ; la gouvernance est en code et ne se discute pas. Tout tourne sur Amazon Bedrock avec Strands. |
| 1:00 à 1:30 | Terminal : `python -m agents.pipeline robert` | Le pipeline tourne pour de vrai sur Bedrock. Environ une minute, une centaine d'appels d'outils. Pendant ce temps, on passe à l'interface. |
| 1:30 à 3:00 | Site, persona Robert : barre d'étapes, carte répartition, carte vérifications, carte pourquoi | Tesla est gardé, mais à 5 % au lieu de 40 %. L'alerte « demande hors profil ». Toucher la pire baisse de Tesla : l'outil, la période, la formule, le fichier. Montrer les trois niveaux d'explication. À 5 % du capital, Tesla porte déjà 54 % du risque. |
| 3:00 à 4:00 | Site, persona Amira, puis Mateo | Amira : le risque est permis mais plafonné, crypto à 8 %, huit lignes. Mateo : aucune action fossile, Tesla écarté pour controverses sourcées, et l'assistant signale ce qu'il ne sait pas sur le contenu du fonds ESG. |
| 4:00 à 4:30 | Carte limites, puis `data/sources_metadata.csv` | Faits, hypothèses, limites, séparés. Chaque source est documentée. Aucune donnée n'est utilisée avant sa date de publication. |
| 4:30 à 5:00 | Terminal : `python -m pytest -q`, puis retour au titre | 239 tests, dont les attendus des trois personas vérifiés sur les vraies sorties. Ce qui reste à faire : le déploiement sur AgentCore et la voix. Simulation uniquement. |

## Les trois phrases à ne pas rater

1. « Aucun chiffre ne sort du modèle : c'est vérifié par la machine. »
2. « Chaque chiffre se touche et montre son calcul. »
3. « L'assistant ne dit pas oui à Robert : il lui montre pourquoi. »
