# Consignes de départ

## Avant de lancer les sessions

Les clés ne vont jamais dans un fichier du dépôt ni sur GitHub. Deux cas.

### Sessions cloud (Claude Code sur le dépôt GitHub)

Dans les réglages de l'environnement cloud utilisé par les sessions :

1. Variables d'environnement, au format `.env` :

   ```
   FRED_API_KEY=ta_cle_fred
   AWS_BEARER_TOKEN_BEDROCK=ta_cle_bedrock
   ```

2. Accès réseau « Limited », avec ces domaines autorisés en plus (un par ligne), ou « Full » :

   ```
   api.stlouisfed.org
   fred.stlouisfed.org
   www.bankofcanada.ca
   *.amazonaws.com
   ```

3. Démarrer une nouvelle session et lui demander :

   ```
   Lance pip install -r tools/requirements.txt strands-agents, puis python -m tools.verifier_cles et python -m tools.ingestion. Montre-moi les sorties sans rien corriger.
   ```

### Machine à soi (VPS ou portable)

```bash
git pull
pip install -r tools/requirements.txt strands-agents
cp .env.example .env          # puis coller les deux clés dans .env
python -m tools.verifier_cles
python -m tools.ingestion
```

### Résultat attendu

`verifier_cles` affiche trois fois `[OK]` : les clés, FRED, puis Bedrock avec un agent qui répond 51,9 % pour la volatilité de NVDA. Si Bedrock affiche ÉCHEC, montrer l'erreur exacte à l'équipe AWS sur place. La région et le modèle se règlent avec `AWS_REGION` et `BEDROCK_MODEL_ID`, au même endroit que les clés. En session cloud, `AWS_BEARER_TOKEN_BEDROCK` peut manquer si un secret réseau est enregistré pour `bedrock-runtime.<région>.amazonaws.com` : le proxy ajoute lui-même le jeton, et `verifier_cles` l'indique (« authentification par le proxy réseau »). Le secret vaut pour un seul hôte, donc pour la région de `AWS_REGION`.

## Les quatre consignes

Une session Claude Code par branche. Coller la consigne telle quelle.

### 1. Branche `agents`

```
Travaille sur la branche agents. Commence par te mettre à jour : git fetch origin && git merge origin/main. Lis CLAUDE.md, docs/contexte.md et tools/verifier_cles.py (un agent Strands qui marche avec notre clé). Les clés sont dans .env, chargées par tools.env.charger_env().

Étape 1. Écris le schéma du profil (champs de CLAUDE.md) et les trois scénarios de tests/scenarios/ (Amira, Mateo, Robert) avec, pour chacun, la demande piège et le comportement attendu.

Étape 2. Construis le pipeline avec Strands sur Bedrock, dans agents/ : orchestrateur, spécialiste marché et risque, constructeur (2 ou 3 portefeuilles simulés), gouvernance (rejet = retour au constructeur, 2 essais au plus), explication à trois niveaux. Les agents n'obtiennent un chiffre qu'en appelant une fonction de tools/, et chaque chiffre affiché garde sa référence d'appel. Fais passer le scénario Robert de bout en bout avant d'ajouter les spécialistes macro et ESG.

Étape 3. Le pipeline renvoie un JSON unique (profil, portefeuilles, contrôles de gouvernance, explications, limites) : écris son schéma dans docs/sortie-pipeline.md pour la branche interface.

Vocabulaire : « portefeuille simulé », « assistant », jamais « conseil ». Petits commits, pousse sur agents. Arrête-toi à la fin de chaque étape et montre-moi le résultat.
```

### 2. Branche `outils`

```
Travaille sur la branche outils. Commence par te mettre à jour : git fetch origin && git merge origin/main. Lis CLAUDE.md et docs/contexte.md. Les fonctions de la première étape existent déjà dans tools/ : garde leurs conventions (résultat avec référence d'appel, valeur brute non arrondie).

Écris, avec des tests pytest sur les vrais CSV : correlations, stats_portefeuille(poids), parts_du_risque(poids), sensibilite_taux(symbole, serie_taux), pente_courbe(pays), gain_de_rattrapage(perte), rendement_en_cad, verifier_contraintes(portefeuille, profil). Les séries macro se lisent dans data/base/series.csv et data/base/panel_quotidien.csv. Tes résultats doivent retrouver les exemples chiffrés de docs/contexte.md (par exemple : 60 % SPY, 30 % AGG, 10 % BTC donne 25,7 % du risque pour le Bitcoin).

Ne modifie pas tools/ingestion.py, tools/env.py ni tools/verifier_cles.py. Petits commits, pousse sur outils.
```

### 3. Branche `interface`

```
Travaille sur la branche interface. Commence par te mettre à jour : git fetch origin && git merge origin/main. Lis CLAUDE.md et docs/contexte.md. Construis dans web/ le site en Next.js, conçu à 390 px de large d'abord, sans aucun défilement dans un écran.

Étape 1. L'écran d'appel (l'assistant en haut, une carte en dessous, la saisie en bas), les six cartes (profil, répartition, risque, pourquoi, limites, vérifications), la barre d'étapes et le bouton « tout voir ». Données d'exemple dans un fichier JSON, avec les chiffres réels de docs/contexte.md. Accueil en texte, pas de voix.

Étape 2. Quand docs/sortie-pipeline.md existe sur la branche agents, branche les cartes sur ce format.

Étape 3, en dernier seulement : la voix avec ElevenLabs Agents, qui ne fait qu'afficher les cartes et mettre à jour le profil.

Une grand-mère doit s'y retrouver : une seule chose à la fois, gros boutons, phrases courtes. Vocabulaire : « portefeuille simulé », « assistant ». Petits commits, pousse sur interface. Montre-moi une capture à 390 px à la fin de l'étape 1.
```

### 4. Branche `donnees`

```
Travaille sur la branche donnees. Lis CLAUDE.md, docs/contexte.md et docs/ajouter-des-donnees.md.

Étape 1. Table ESG pour les 20 actions de data/assets_universe.csv, dans data/esg_actions.csv : secteur, activité liée aux énergies fossiles (oui/non), controverse environnementale ou sociale importante connue (oui/non/inconnu), une phrase de résumé, l'adresse de la source et sa date. Sources : rapports de durabilité des sociétés, dépôts SEDAR+ et SEC EDGAR, méthodologie d'exclusion du FNB ESGV. N'écris rien de mémoire : chaque ligne s'appuie sur une page que tu as ouverte. Si tu ne trouves pas, écris « inconnu ».

Étape 2. Composition des FNB SPY, QQQ, XIU.TO et ESGV depuis les sites des émetteurs, dans data/fnb_composition.csv (fnb, symbole détenu, poids, date), au moins pour les titres de notre univers.

Chaque fichier ajouté a sa ligne dans data/sources_metadata.csv. Petits commits, pousse sur donnees.
```
