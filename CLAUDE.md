# AlphaForge AI — Datathon PolyFinances 2026

Le produit s'appelle **Eagle** (AlphaForge AI est le nom du défi). Son assistant est un aigle.

Assistant agentique qui propose des portefeuilles **simulés** adaptés à un profil d'investisseur et explique chaque choix, ses sources et ses limites. L'énoncé complet est dans `docs/enonce.txt` : en cas de doute, il fait foi.

## Règles non négociables

- Simulation uniquement. Aucune transaction réelle.
- Jamais « conseil » ni « conseiller » : on dit « portefeuille simulé » et « assistant ».
- Aucun chiffre ne sort d'un modèle. Tout chiffre vient d'une fonction de `tools/` et garde la référence de l'appel qui l'a produit (nom de l'outil, paramètres, période).
- Pas de prédiction de rendement futur. Les données passées décrivent, elles ne promettent rien.
- Seule projection admise : l'éventail de scénarios de `tools/scenarios.py`, toujours affiché avec le titre « Scénarios, pas une prévision », ses hypothèses et son avertissement.
- Chaque explication distingue faits, hypothèses et limites. Pas de justification inventée.
- Une donnée macro mensuelle ne s'utilise pas avant sa date de publication.
- Toute donnée ajoutée a sa ligne dans `data/sources_metadata.csv` (source, URL, date, traitement, limites, conditions d'utilisation).
- Un symbole boursier ne vient jamais de la mémoire d'un modèle : il vient d'une table sourcée et doit passer `build_dataset.py`.

## Grille du jury

| Critère | Poids |
| --- | --- |
| Qualité, pertinence et innovation | 20 % |
| Intelligence agentique et explicabilité | 20 % |
| Analyse et traitement des données | 20 % |
| Intégration AWS | 15 % |
| Présentation, valeur business | 15 % |
| UX/UI | 10 % |

Le rendement des portefeuilles ne compte pas. Simple, focalisé et vérifiable vaut mieux que beaucoup d'agents.

## Pipeline

1. **Accueil** : 6 à 8 questions, puis un récapitulatif que l'utilisateur valide. Sortie : un profil structuré.
2. **Orchestrateur** : lit le profil, transmet aux spécialistes les contraintes et, s'il y en a, un thème avec son plafond.
3. **Spécialistes** (chacun son domaine, pas de débat) : marché et risque, macro et taux, ESG et qualité.
4. **Constructeur** : 2 ou 3 portefeuilles simulés.
5. **Gouvernance** : vérifie chaque portefeuille contre le profil. Rejet = retour au constructeur, 2 essais au plus. Les contrôles sont affichés.
6. **Explication** : trois niveaux (une phrase, le pourquoi chiffré, le calcul avec la formule), plus les limites.

Le pipeline ne se modifie pas tout seul. On l'améliore avec les tests d'acceptation.

## Profil

`horizon_annees`, `objectif`, `tolerance_risque` (faible, modéré, élevé), `connaissance` (débutant, intermédiaire, avancé), `preferences`, `exclusions`, `centres_interet`, `capital_fictif`, `devise`.

Le thème tiré de `centres_interet` est une inclinaison plafonnée (10 % par défaut, paramètre), sur actions et FNB seulement. Pas d'options ni de dérivés.

## Outils Python (`tools/`)

Tous testés avec pytest sur les vrais CSV.

- `charger_prix`, `convertir_cad`, `aligner_calendriers`
- `rendements`, `volatilite`, `pire_baisse`, `correlations`
- `stats_portefeuille(poids)`, `parts_du_risque(poids)`
- `sensibilite_taux(symbole, serie_taux)`, `pente_courbe(pays)`
- `gain_de_rattrapage(perte)`, `rendement_en_cad`
- `verifier_contraintes(portefeuille, profil)`

## Pièges des données (`data/`)

- Prix dans la devise de cotation : `.TO` en CAD, le reste en USD. Conversion avec `fx_usdcad_daily.csv`, dernier taux reporté les jours fériés canadiens.
- Calendriers non alignés : TSX, marchés américains, crypto 7 jours sur 7.
- `adj_close` pour les rendements. Les fractionnements sont déjà appliqués, ne pas les réappliquer.
- IPC américain = indice, IPC canadien = variation annuelle.
- Biais du survivant : l'univers a été choisi en 2026.
- Aucune donnée ESG, de composition de FNB ni de fondamentaux : à ajouter et à documenter.

## Ajouter des données

- Une base s'ajoute par une ligne dans `data/catalogue.csv` (FRED, Banque du Canada) ou par un CSV déposé dans `data/depot/`. Puis `python -m tools.ingestion`. Mode d'emploi : `docs/ajouter-des-donnees.md`.
- Les agents et le machine learning lisent `data/base/panel_quotidien.csv` : une ligne par jour ouvrable, chaque valeur étant la dernière publiée ce jour-là.
- Machine learning descriptif seulement (régimes macro, groupes d'actifs, sensibilités). Pas de prédiction de rendement.
- Lire `data/base/rapport_qualite.txt` après chaque ajout. Un trou dans les données se signale, il ne se comble pas en silence.

## Tests d'acceptation (`tests/scenarios/`)

- **Amira** (26 ans, risque élevé, 15 ans et plus) demande 100 % crypto et techno : le système plafonne et garde une diversification.
- **Mateo** (41 ans, modéré, 8 à 12 ans, ESG) : le système écarte ou signale les titres controversés avec une source, et dit quand l'information manque.
- **Robert** (59 ans, faible à modéré, 3 à 5 ans) veut une grosse position sur un titre très médiatisé : le système relève la tension avec son profil et n'acquiesce pas.

À relancer après chaque changement du pipeline.

## Interface

- Mobile d'abord : conçue à 390 px de large, puis adaptée au bureau.
- Aucun défilement dans un écran. Une seule chose à la fois.
- Écran d'appel : l'assistant en haut, une carte en dessous, le micro en bas. Bouton « Démarrer l'appel » obligatoire (le navigateur exige un geste pour l'audio) et site en HTTPS (exigé pour le micro).
- Six cartes : profil, répartition, risque, pourquoi, limites, vérifications. Le contenu vient du pipeline, jamais de la voix.
- Bouton « tout voir » en fin de parcours : toutes les cartes sur un écran.
- Barre d'étapes : Profil, Analyse, Proposition, Vérification, Explication.
- Repli en texte si le micro ne marche pas.

## Technique (à confirmer avec les règles officielles et les accès fournis)

- Agents : Strands Agents sur Amazon Bedrock, déployés sur AgentCore Runtime.
- Voix : ElevenLabs Agents, pour la voix seulement. Trois outils : mettre à jour le profil, lancer l'analyse, afficher une carte.
- Front : Next.js, hébergé sur AWS.
- Clés : uniquement celles de l'environnement cloud « Sam » de Claude Code, pour toutes les sessions. Variables : `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION` (Bedrock, signature SigV4), `BEDROCK_AUTH=identifiants` (impose ce mode), `FRED_API_KEY`. Finnhub et CoinGecko passent par les secrets réseau de ce même environnement. Rien d'autre : pas de fichier `.env`, pas de jeton `AWS_BEARER_TOKEN_BEDROCK`, pas de secret réseau sur `bedrock-runtime` (il remplacerait la signature). Jamais affichées ni poussées. Vérification : `python -m tools.verifier_cles`.

## Branches

- `outils` : `tools/`, `data/`, tests.
- `agents` : pipeline, AWS, scénarios.
- `interface` : site, cartes, voix.
- `donnees` : table ESG, composition des FNB.

Les consignes de chaque branche sont dans `docs/consignes-de-depart.md`. Une branche par personne, fusion dans `main` par petites demandes de tirage. Personne ne touche au dossier d'un autre sans prévenir.
