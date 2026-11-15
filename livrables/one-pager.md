# AlphaForge AI — l'assistant qui sait dire non, et le prouver

Équipe 37, Datathon PolyFinances 2026. Simulation uniquement, aucun conseil en placement.

## Le problème

Un outil d'investissement qui dit oui à tout est dangereux. Robert, 59 ans, proche de la retraite, veut mettre 40 % de son capital sur Tesla parce que tout le monde en parle. La bonne réponse n'est ni « oui », ni un refus sec : c'est de lui montrer, chiffres à l'appui, pourquoi sa demande contredit son propre profil, et ce qui lui convient à la place.

## Notre approche

Une chaîne de sept agents, chacun avec un seul rôle : un orchestrateur, trois spécialistes (marché et risque, macro et taux, ESG), un constructeur, une gouvernance et un agent d'explication. Les agents tournent sur Amazon Bedrock avec Strands Agents.

Deux règles tiennent l'ensemble :

- **Le code calcule, le modèle explique.** Aucun texte écrit par un modèle ne contient de chiffre. C'est vérifié par la machine, pas laissé à la bonne volonté du modèle.
- **La gouvernance ne se discute pas.** Elle est en code : un portefeuille qui dépasse les limites du profil retourne au constructeur.

## Ce qui est original

**Chaque chiffre se touche.** Dans l'interface, un chiffre touché montre son calcul : l'outil, ses paramètres, la période, la formule, le fichier source. L'utilisateur peut tout vérifier.

**Trois niveaux d'explication** : une phrase, le pourquoi chiffré, le calcul complet. Le niveau ouvert dépend de l'expérience de l'utilisateur.

## Résultats sur les trois personas

| Persona | Demande | Réponse de la solution |
| --- | --- | --- |
| Robert | 40 % sur Tesla | Tesla plafonné à 5 %, avec une alerte : à 5 % du capital, il porte déjà 54 % du risque |
| Amira | 100 % crypto et techno | Crypto à 8 %, thème techno à 10 %, huit lignes diversifiées |
| Mateo | Sans pétrolières, « Tesla c'est vert » | Aucune action fossile, Tesla écarté pour controverses sourcées, alerte sur le contenu du fonds ESG |

## Données

Prix quotidiens de 31 actifs sur cinq ans, taux et inflation (Banque du Canada, FRED avec dates de publication réelles), table ESG sourcée de 20 actions, composition de quatre FNB. Chaque source est documentée, et aucune donnée n'est utilisée avant sa date de publication.

## Bénéfices pour l'utilisateur

- Il comprend **pourquoi**, dans son vocabulaire.
- Il peut **vérifier** chaque chiffre lui-même.
- Il voit les **limites** : ce qui est un fait, ce qui est une hypothèse, ce que les données ne disent pas.
- Il n'est jamais poussé vers un risque qui contredit ses propres objectifs.

Validation : 239 tests automatiques, dont les attendus des trois personas vérifiés sur les vraies sorties du pipeline.
