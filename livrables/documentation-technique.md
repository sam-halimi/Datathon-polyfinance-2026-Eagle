# AlphaForge AI — Documentation technique

Équipe 37, Datathon PolyFinances 2026. Simulation uniquement : aucun conseil en placement, aucune transaction réelle.

## 1. Ce que fait la solution

Un assistant recueille le profil d'un investisseur, puis une chaîne d'agents propose deux ou trois portefeuilles simulés, les vérifie contre le profil et explique le résultat en trois niveaux de détail. Chaque chiffre affiché se touche et montre son calcul : l'outil, ses paramètres, la période, la formule et le fichier source.

La question traitée : que répondre à un investisseur dont la demande ne correspond pas à son profil ? Les trois personas de l'énoncé posent chacun une demande piège, et la solution doit la relever au lieu d'acquiescer.

Les personas sont des cas de test, pas le produit. Le pipeline accepte n'importe quel profil : `python -m agents.pipeline chemin/profil.json`.

## 2. Méthodes et technologies

| Choix | Justification |
| --- | --- |
| Agents écrits avec Strands Agents, modèles appelés par Amazon Bedrock | Cadre recommandé à l'atelier AWS. Modèle par défaut de Strands, région `us-east-1` (au test du 14 novembre : `global.anthropic.claude-sonnet-4-6`). |
| Calculs en Python (`tools/`), jamais par le modèle | Un modèle de langage calcule mal. Le code calcule, le modèle explique. |
| Gouvernance sans modèle | Un contrôle se calcule, il ne se discute pas. Le résultat est le même à chaque exécution. |
| Pipeline fixe, peu d'agents | L'énoncé demande une approche simple, focalisée et vérifiable. |
| Sorties structurées validées par schéma (pydantic) | L'interface lit un format stable, documenté dans `docs/sortie-pipeline.md`. |

### Le pipeline (`agents/pipeline.py`)

1. **Orchestrateur** (modèle) : lit la demande, retrouve les symboles dans la table sourcée, fixe le thème plafonné et l'univers des candidats.
2. **Spécialistes** : marché et risque, macro et taux, ESG et qualité. Chacun mesure avec `tools/`, puis un modèle rédige les constats.
3. **Constructeur** (modèle) : deux ou trois portefeuilles simulés.
4. **Gouvernance** (code) : vérifie chaque portefeuille contre le profil. Un rejet retourne au constructeur, deux essais au plus. Tous les contrôles sont affichés.
5. **Explication** (modèle) : trois niveaux, plus les faits, les hypothèses et les limites.

Le pipeline ne se modifie pas lui-même. Il s'améliore avec les scénarios de test (section 6).

## 3. Données, actifs et traitements

| Donnée | Source | Contenu |
| --- | --- | --- |
| Prix quotidiens | Yahoo Finance, jeu de départ des organisateurs | 31 actifs, 40 049 lignes, du 12 novembre 2021 au 12 novembre 2026 |
| Change USD/CAD | Banque du Canada | Taux quotidien |
| Taux et macro | Banque du Canada, FRED (API officielle) | 9 séries. Pour FRED, date réelle de première publication de chaque observation |
| ESG | Dépôts SEC EDGAR, pages officielles de régulateurs, règlement de l'indice suivi par ESGV | 20 actions : activité fossile, controverse documentée, résumé, adresse et date de la source |
| Composition des FNB | State Street, Invesco, BlackRock, formulaire SEC pour ESGV | SPY (505 lignes), QQQ (105), XIU.TO (65), ESGV (9 titres de notre univers) |

Chaque fichier a sa ligne dans `data/sources_metadata.csv` : source, adresse, date, traitement, limites, conditions d'utilisation.

**Traitements**

- Rendements sur `adj_close` (dividendes et fractionnements inclus), dans la devise de cotation ou convertis en CAD.
- Calendriers alignés sur les jours où tous les actifs d'un calcul cotent. Dernier taux de change reporté les jours fériés canadiens.
- Aucune donnée macro n'est utilisée avant sa publication : `data/base/panel_quotidien.csv` donne, pour chaque jour, la dernière valeur déjà publiée ce jour-là.
- Un trou dans les données est signalé et non comblé. Octobre 2025 manque dans l'IPC et le chômage américains.
- Ajout d'une base : une ligne dans `data/catalogue.csv` ou un fichier déposé dans `data/depot/`, puis `python -m tools.ingestion` (`docs/ajouter-des-donnees.md`).

**Hypothèses du projet**

Les limites par tolérance au risque sont des choix de l'équipe, pas des normes. Elles sont affichées comme telles.

| Tolérance | Par titre | Crypto | Part risquée | Par secteur | Volatilité max | Pire baisse max |
| --- | --- | --- | --- | --- | --- | --- |
| Faible | 5 % | 0 % | 40 % | 15 % | 8 % | −15 % |
| Modéré | 10 % | 5 % | 70 % | 20 % | 14 % | −25 % |
| Élevé | 15 % | 10 % | 90 % | 30 % | 22 % | −40 % |

S'y ajoutent : cinq lignes au moins, aucune crypto sous cinq ans d'horizon, un thème d'intérêt plafonné à 10 %. Quand l'utilisateur hésite entre deux niveaux de risque ou donne une fourchette d'horizon, le plus prudent est retenu et le récapitulatif le dit.

## 4. Mécanisme d'explicabilité

**La règle : aucun texte écrit par un modèle ne contient de chiffre.**

Les agents n'écrivent jamais un nombre. Ils appellent un outil de `tools/` par un journal (`agents/journal.py`), qui garde la référence complète de l'appel sous un identifiant. Leurs textes portent des repères comme `{pb_tsla}`, que l'interface remplace par la valeur. La règle est vérifiée mécaniquement : un texte avec un chiffre écrit en dur ou un repère inconnu est renvoyé une fois au modèle, puis retiré s'il est encore faux.

**Exemple réel, scénario Robert** (`agents/sorties/robert.json`)

Robert, 59 ans, risque faible, horizon de trois ans, demande : « Je veux mettre 40 % de mon capital sur Tesla. »

- **Niveau 1, une phrase** : « La demande dépasse largement les limites du profil : le plafond par titre individuel est `{lim_max_titre_individuel}`, et Tesla est l'actif le plus risqué du portefeuille simulé avec une volatilité de `{vol_tsla}` et une pire baisse observée de `{pb_tsla}`. »
- **Niveau 2, le pourquoi chiffré** : Tesla est gardé à 5 % du capital, et porte déjà 54,1 % du risque du portefeuille. Après une baisse de 73,0 %, il faut un gain de 270 % pour revenir au point de départ.
- **Niveau 3, le calcul** : la formule de la part du risque, les poids, la période et les fichiers sources.

Ce que l'utilisateur voit en touchant `{pb_tsla}` :

| Champ | Valeur |
| --- | --- |
| Outil | `pire_baisse` |
| Paramètres | symbole TSLA, devise de cotation |
| Période | du 12 novembre 2021 au 12 novembre 2026, 1 255 observations |
| Formule | minimum sur la fenêtre de (prix / plus haut atteint jusque-là − 1) |
| Source | `prices_daily.csv` (`adj_close`) |
| Détails | sommet le 3 janvier 2022, creux le 3 janvier 2023 |
| Valeur | −73,0 % |

Sont aussi visibles : ce que chaque agent a fait, dans l'ordre (`etapes`), chaque appel d'outil (`journal.appels`) et chaque contrôle de gouvernance avec sa mesure et son seuil. Le raisonnement interne du modèle n'est pas exposé.

## 5. Résultats sur les trois personas

Sorties réelles produites sur Bedrock le 15 novembre 2026.

| Persona | Demande piège | Ce que fait la solution | Portefeuille simulé retenu |
| --- | --- | --- | --- |
| Robert | 40 % sur Tesla | Tesla plafonné à 5 %, alerte « demande hors profil », aucune crypto | Volatilité 4,4 %, pire baisse −6,4 % |
| Amira | 100 % crypto et techno | Crypto à 8 % (plafond 10 %), thème techno à 10 %, huit lignes | Volatilité 16,4 %, pire baisse −25,5 %. Le Bitcoin pèse 8 % du capital et 15,2 % du risque |
| Mateo | Sans pétrolières ni controverses, « Tesla c'est vert » | Aucune action fossile en direct, Tesla écarté pour controverses documentées, alerte sur le contenu d'ESGV | Volatilité 8,6 %, pire baisse −16,2 % |

Chaque exécution demande entre 93 et 120 appels d'outils et dure de 46 à 79 secondes. Aucun texte n'a dû être retiré pour chiffre écrit en dur.

## 6. Validations

- **239 tests automatiques** (`pytest`), sur les vrais fichiers de données.
- **Outils** : chaque fonction retrouve des valeurs calculées indépendamment (`analyses/`), et renvoie une référence complète, sérialisable.
- **Scénarios d'acceptation** (`tests/scenarios/`) : pour chaque persona, cinq à sept attendus écrits pour être vérifiés par la machine, appliqués aux vraies sorties du pipeline (`test_bout_en_bout.py`). Les tests ne rappellent pas le modèle : ils vérifient ce qu'il a produit.
- **Règles du projet** vérifiées sur chaque sortie : pas de chiffre hors table, vocabulaire (« portefeuille simulé », jamais « conseil »), symboles tous présents dans l'univers.
- **Pas de regard vers le futur** : un test vérifie qu'une donnée mensuelle n'apparaît dans le panel qu'à partir de sa date de publication.
- **Connexion aux services** : `python -m tools.verifier_cles` contrôle FRED et Bedrock avec un agent qui doit retrouver un chiffre connu.

## 7. Limites

- **Cinq ans d'historique**, sur un univers choisi en 2026 parmi des titres aujourd'hui importants (biais du survivant). Les mesures décrivent le passé et ne prédisent rien.
- **Limites par tolérance** : hypothèses de l'équipe.
- **ESG** : « non » veut dire aucune controverse dans le dernier dépôt annuel, pas l'absence de toute controverse. Certains extraits de source sont passés par un outil de résumé et ne se citent pas mot pour mot.
- **ESGV** : seules neuf lignes de sa composition sont connues, lues dans un formulaire SEC. Le regard à travers ce fonds est donc partiel, et la solution le signale.
- **Thème** : le plafond porte sur les titres détenus en direct. L'exposition à la technologie à travers QQQ ou SPY n'est pas plafonnée.
- **Rééquilibrage quotidien** supposé dans les mesures de portefeuille.
- **Interface** : elle affiche les sorties enregistrées des trois personas. Le questionnaire libre ne lance pas encore le pipeline en direct : pour un autre profil, la commande ci-dessus s'utilise depuis un terminal.
- **Accueil en texte** : la voix n'a pas été réalisée.
- **AWS** : les modèles tournent sur Bedrock. Le pipeline n'est pas déployé sur AgentCore.

## 8. Améliorations envisagées

- Déployer le pipeline sur AgentCore et héberger le site sur AWS.
- Guardrails Bedrock comme seconde barrière contre tout ce qui ressemble à du conseil.
- Knowledge Bases pour interroger directement les rapports de durabilité.
- Plafonner un thème en regardant à travers les FNB.
- Accueil vocal, où la voix ne fait qu'afficher les cartes déjà calculées.
- Régimes macro descriptifs à partir du panel quotidien.
