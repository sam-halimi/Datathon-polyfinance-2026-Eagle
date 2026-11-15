# Contexte du projet

État au samedi 14 novembre 2026, 16 h. Ce fichier résume les décisions prises et ce qui a déjà été vérifié sur les données. `CLAUDE.md` contient les règles, ce fichier contient le pourquoi.

## Ce que le jury regarde

Trois personas servent de tests. Chacun vérifie une chose précise :

- **Amira** : le système accepte le risque sans tout accepter, et garde une diversification.
- **Mateo** : le système tient compte d'autre chose que le rendement et le risque (ESG, controverses).
- **Robert** : le système conteste une demande incohérente avec le profil au lieu d'acquiescer.

Le rendement des portefeuilles ne compte pas. Ce qui compte : une démarche agentique simple et vérifiable, et des explications fidèles aux données et aux actions observables.

## Décisions prises

1. **Pas de pipeline qui se réécrit tout seul.** L'apprentissage par l'erreur passe par l'agent de gouvernance (en direct, 2 essais au plus) et par les scénarios de test relancés après chaque changement (pendant le développement).
2. **Pas de débat entre agents.** Chaque spécialiste a son domaine, l'orchestrateur assemble.
3. **Aucun chiffre ne sort d'un modèle.** Tout est calculé dans `tools/` et chaque chiffre affiché renvoie à l'appel qui l'a produit. C'est le mécanisme d'explicabilité.
4. **L'orchestrateur adapte l'univers au profil.** Un centre d'intérêt (par exemple le jeu vidéo) devient un thème plafonné, sur actions et FNB. Les symboles viennent d'une table sourcée. Le système affiche le point faible du thème (par exemple sa corrélation avec la techno).
5. **Explications à trois niveaux**, ouverts au clic : une phrase, le pourquoi chiffré, le calcul avec la formule et les chiffres du portefeuille. Le niveau par défaut dépend de la connaissance déclarée.
6. **Interface en appel vocal**, mobile d'abord : l'assistant parle, une carte s'affiche à la fois. La voix choisit la carte, jamais son contenu. Repli en texte.
7. **Le cerveau reste sur AWS** (15 % de la note). La voix peut passer par ElevenLabs, pour la voix seulement.
8. **Vocabulaire** : « portefeuille simulé », « assistant ». Jamais « conseil » ni « conseiller ».

## Données vérifiées

Contrôle fait avec `analyses/controle_donnees.py` : 40 049 lignes de prix, 31 actifs, aucun doublon, aucune valeur manquante, du 12 novembre 2021 au 12 novembre 2026.

Calculs sur `adj_close` (dividendes inclus), dans la devise de cotation, sans conversion. Volatilité annualisée sur 252 jours (365 pour les cryptos). Les fonctions de `tools/` doivent retrouver ces chiffres.

| Actif | Lignes | Rendement annualisé | Volatilité | Pire baisse |
| --- | --- | --- | --- | --- |
| AAPL | 1255 | 19,4 % | 28,2 % | −33,4 % |
| AGG | 1255 | −0,3 % | 6,2 % | −17,2 % |
| AMZN | 1255 | 8,7 % | 36,7 % | −55,7 % |
| ATD.TO | 1255 | 11,4 % | 24,1 % | −22,2 % |
| BTC-USD | 1827 | 2,1 % | 50,8 % | −75,9 % |
| CNQ.TO | 1255 | 28,7 % | 30,7 % | −33,1 % |
| CNR.TO | 1255 | 4,4 % | 19,9 % | −27,2 % |
| CSU.TO | 1255 | 10,0 % | 30,5 % | −56,4 % |
| ENB.TO | 1255 | 12,8 % | 16,1 % | −21,4 % |
| ESGV | 1255 | 10,0 % | 18,7 % | −28,8 % |
| ETH-USD | 1827 | −15,4 % | 68,5 % | −78,7 % |
| FTS.TO | 1255 | 12,7 % | 14,7 % | −24,0 % |
| GLD | 1255 | 15,3 % | 19,2 % | −28,4 % |
| GOOGL | 1255 | 15,2 % | 32,6 % | −44,3 % |
| JNJ | 1255 | 14,6 % | 18,1 % | −18,4 % |
| JPM | 1255 | 18,4 % | 24,4 % | −37,9 % |
| MFC.TO | 1255 | 26,0 % | 21,6 % | −21,0 % |
| MSFT | 1255 | 10,1 % | 28,5 % | −37,1 % |
| NVDA | 1255 | 40,6 % | 51,9 % | −66,3 % |
| PG | 1255 | 5,5 % | 18,5 % | −23,8 % |
| QQQ | 1255 | 12,4 % | 23,4 % | −35,1 % |
| RY.TO | 1255 | 21,0 % | 15,5 % | −21,2 % |
| SHOP.TO | 1255 | 0,0 % | 64,4 % | −83,5 % |
| SPY | 1255 | 11,6 % | 17,3 % | −24,5 % |
| TD.TO | 1255 | 18,5 % | 17,7 % | −26,1 % |
| TLT | 1255 | −8,3 % | 15,6 % | −43,7 % |
| TSLA | 1255 | 2,9 % | 59,6 % | −73,0 % |
| XBB.TO | 1255 | 0,7 % | 6,6 % | −15,5 % |
| XIU.TO | 1255 | 13,7 % | 13,1 % | −16,4 % |
| XOM | 1255 | 25,6 % | 26,7 % | −20,5 % |
| ZST.TO | 1255 | 3,4 % | 0,6 % | −0,4 % |

Deux constats à intégrer dans le produit :

- **Les obligations n'ont pas protégé sur cette fenêtre.** TLT, AGG et XBB.TO ont connu de fortes baisses. Seul ZST.TO est stable. Important pour Robert, qui veut préserver son capital.
- **Les deux IPC ne sont pas comparables tels quels.** `CPIAUCSL` est un indice, `STATIC_TOTALCPICHANGE` une variation annuelle.

## Exemples d'explication déjà calculés

Produits par `analyses/exemples_explications.py`. Ils servent de modèle pour le niveau 3 des explications.

| Fiche | Formule | Exemple sur nos données |
| --- | --- | --- |
| Taux et obligations | variation de prix ≈ −duration × variation du taux | TLT : −14,3 % par point de hausse du 10 ans américain (R² 0,83). AGG : −5,9 % (R² 0,92). Le 10 ans est passé de 1,58 % à 5,10 % |
| Part du risque | poids × contribution à la variance | 60 % SPY, 30 % AGG, 10 % BTC : volatilité 13,9 %. Le Bitcoin pèse 10 % du capital et 25,7 % du risque |
| Diversification | variance du portefeuille avec les corrélations | AGG et SPY : 0,22. BTC et SPY : 0,42. BTC et AGG : 0,09 |
| Perte et rattrapage | gain nécessaire = perte / (1 − perte) | Après −73 % (TSLA), il faut +270 % pour revenir |
| Thème et concentration | corrélation avec un indice | NVDA et QQQ : 0,78. MSFT et QQQ : 0,71 |
| Pente de la courbe | taux 10 ans − taux 2 ans | États-Unis : négative 541 jours sur 1 249, minimum −1,08 point le 3 juillet 2023. Canada : négative 549 jours sur 1 245, minimum −1,32 point le 30 juin 2023 |

Les chiffres de taux viennent de l'instantané `data/base/` (FRED en direct jusqu'au 12 novembre 2026, prix des organisateurs). Les R² sont calculés sur les jours communs aux prix et au taux, comme dans `tools/macro.py`. Si on relance l'ingestion, ces chiffres et les tests qui les vérifient sont à mettre à jour ensemble.

## Données à ajouter

Par ordre de priorité, chacune liée à un persona :

1. **ESG (Mateo)** : une table pour les 20 actions, avec source et date, tirée des rapports de durabilité des sociétés et de la méthodologie d'exclusion d'ESGV.
2. **Composition des FNB (Amira)** : SPY et QQQ détiennent déjà NVDA, AAPL et MSFT. La concentration réelle se calcule en transparence.
3. **Titres thématiques** : à ajouter dans `UNIVERSE` de `data/build_dataset.py`, qui échoue si un symbole ne renvoie aucun prix.
4. **Fondamentaux et nouvelles datées (Robert)** : SEC EDGAR et SEDAR+, s'il reste du temps.

Chaque ajout a sa ligne dans `data/sources_metadata.csv`.

## Compte AWS de l'équipe

Source : courriel d'AWS du 13 novembre et aide-mémoire de l'atelier AWS. Le code d'accès n'est pas dans le dépôt.

- Un seul compte pour l'équipe 37, partagé à trois, ouvert depuis le samedi 14 novembre à 11 h 30.
- Tous les services sont inclus, sauf l'achat de noms de domaine Route 53 et les instances avec gros GPU.
- Le compte expire lundi 16 novembre en fin de journée, puis il est supprimé avec toutes ses données. Le code reste sur GitHub, et la vidéo de démonstration s'enregistre pendant que le compte tourne.
- Une seule personne déploie, pour ne pas s'écraser.
- Démarrage conseillé par AWS : `pip install strands-agents` et une clé API Bedrock dans `AWS_BEARER_TOKEN_BEDROCK`.
- Services présentés à l'atelier : Bedrock, Knowledge Bases, Guardrails, AgentCore, AgentCore Code Interpreter, Strands Agents, Kiro. Guardrails peut servir à bloquer ce qui ressemble à du conseil, Knowledge Bases aux documents ESG.
- Rappel de l'atelier, identique à notre règle : le code calcule, le modèle explique, chaque chiffre cite sa source.

Paliers d'intégration AWS, du minimum au plus complet :

1. Les agents appellent leur modèle par Bedrock.
2. Les agents sont déployés sur AWS (AgentCore).
3. Le site et les données sont aussi sur AWS, avec Guardrails.

## Clés

Dans `.env` à la racine (modèle : `.env.example`), jamais poussé. Vérification en une commande : `python -m tools.verifier_cles`.

## Questions ouvertes

- Heure limite exacte de remise.
- Comment le jury évalue l'intégration AWS, et s'il teste le prototype après l'expiration du compte.
- Règles techniques officielles : imposent-elles une infrastructure ?
- Français pris en charge par la solution de voix retenue.

## Références techniques

- Strands Agents sur Bedrock AgentCore : https://builder.aws.com/content/38cDEEgvvceQFmLXCDepzSq50yu/multi-agent-customer-service-on-amazon-bedrock-agentcore
- Schémas multi-agents de Strands : https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/
- ElevenLabs Agents, outils côté client : https://elevenlabs.io/docs/eleven-agents/customization/tools/client-tools
- Amazon Nova 2.5 Sonic (voix sur Bedrock) : https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-5-sonic.md
