# Déploiement sur AWS

Eagle tourne sur le compte AWS de l'atelier, en `us-east-1` (seule région ouverte au rôle `WSParticipantRole`).

| Quoi | Service | Adresse |
| --- | --- | --- |
| Site | S3 (compartiment privé) + CloudFront, HTTPS | `https://d1ah12vrfzso9b.cloudfront.net` |
| API (`agents/serveur.py`) | AWS Lambda `eagle-api`, adresse de fonction HTTPS | `https://mchhm2dabjrbsfncikiw7i4qfa0hopli.lambda-url.us-east-1.on.aws` |
| Modèle des agents | Amazon Bedrock, appelé avec le rôle IAM `eagle-lambda` (aucune clé) | |
| Comptes | Amazon Cognito, groupe d'utilisateurs `eagle-comptes`, client `eagle-site` | identifiant et mot de passe, sans adresse courriel |

Pas de nom de domaine acheté : Route 53 est exclu du compte de l'atelier. L'adresse CloudFront est en HTTPS, ce qu'exige le micro du navigateur.

## Déployer

Depuis la racine du dépôt, avec des identifiants AWS du compte (variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) :

```bash
python -m deploiement.deployer tout
```

`api` ou `site` ne déploient qu'une partie. Le script peut être relancé : il met à jour ce qui existe au lieu de le dupliquer.

- **API** : installe les dépendances Python pour Lambda (Python 3.13, x86_64), y ajoute `agents/`, `tools/`, `data/` et `tests/scenarios/`, dépose le zip dans `s3://eagle-deploiement-<compte>`, puis crée ou met à jour la fonction `eagle-api` (15 minutes, 2 Go). Le point d'entrée est `agents/lambda_eagle.py`, qui réutilise l'aiguillage de `agents/serveur.py`. La concurrence est plafonnée à 5 pour limiter le coût d'appels répétés à `/analyse`.
- **Site** : exporte `web/` en pages statiques (`EAGLE_EXPORT=1`, `NEXT_PUBLIC_API_URL` = adresse de l'API), dépose `web/out` dans `s3://eagle-site-<compte>` (privé) et le sert par CloudFront avec un contrôle d'accès d'origine. Une fonction CloudFront (`eagle-index`) sert `/rapport/` depuis `/rapport/index.html`.

Les sorties de démonstration (`agents/sorties/`) sont intégrées au site et à l'API au moment du déploiement : après une régénération, redéployer les deux.

Avant l'export, le script relance `python web/scripts/graphiques.py` : les tables du site (secteur, zone, cours de tous les actifs, éventails des démonstrations) suivent toujours `data/` et `agents/sorties/`. Il fournit aussi l'identifiant de l'agent vocal à l'export (`NEXT_PUBLIC_ELEVENLABS_AGENT_ID`, par défaut l'agent Eagle de `docs/agent-elevenlabs.md`) : la voix est active sur le site déployé.

## Comptes

- Le script crée (ou retrouve) le groupe Cognito `eagle-comptes` et son client `eagle-site`, les donne à la fonction (`EAGLE_COGNITO_GROUPE`, `EAGLE_COGNITO_CLIENT`) et limite le rôle `eagle-lambda` à quatre actions sur ce groupe : créer un compte, fixer son mot de passe, connecter, retirer un compte à moitié créé.
- Règle du mot de passe : au moins 8 caractères, dont une minuscule et un chiffre. Jeton d'accès valable 8 heures.
- `/analyse`, `/scenarios` et `/actif` exigent le jeton : l'analyse, qui appelle Bedrock, n'est plus ouverte à tous. `/sante` et `/demonstration/<persona>` restent ouvertes.
- Aucune donnée personnelle n'est demandée : un pseudonyme suffit comme identifiant. Eagle ne stocke ni le mot de passe ni le profil ; le profil vit dans le navigateur le temps de la séance.
- Supprimer un compte : console Cognito, ou `aws cognito-idp admin-delete-user --user-pool-id <groupe> --username <identifiant>`.

## Pannes passagères de Bedrock

Le 16 novembre 2026, entre 0 h 27 et 0 h 35 UTC, Bedrock a répondu « serviceUnavailableException » au milieu des réponses : toutes les analyses échouaient en « erreur 500 », y compris après « Relancer ». Depuis (`agents/resistance.py`) : réponses non diffusées, reprises de botocore, puis modèle de secours (`us.anthropic.claude-sonnet-4-6`, puis `global.anthropic.claude-sonnet-4-5-20250929-v1:0`), trois tours. Si tout échoue, l'API répond 503 avec une phrase claire et le site garde le profil. `meta.modele` de la sortie nomme le modèle qui a réellement répondu.

## Une seule adresse, une seule branche

- **L'adresse à donner au jury est celle de CloudFront.** Le projet Vercel `alphaforge-polyfinances` date du début du dimanche (dernier envoi à 19 h 37 UTC le 15 novembre) : plus rien n'y est déployé, il montre une ancienne version et n'appelle pas l'API AWS. Ne pas le partager.
- **On déploie depuis une branche qui contient `main`.** Le premier déploiement était parti de `agents-eagle`, qui n'avait pas encore la direction artistique fusionnée dans `main` : le site en ligne et le site local ne se ressemblaient pas. Avant de déployer : `git fetch origin && git merge origin/main`, puis les tests.

## Vérifié le 16 novembre 2026 (version déployée depuis `claude/festive-euler-nsxfvo`, à jour de `main` et de `donnees`)

- `GET /sante`, `GET /demonstration/robert` (7 étapes, éventail de scénarios), `GET /actif` sur un actif de thème (ARTY) : 200.
- Analyse complète d'un profil saisi à l'écran du site CloudFront (revenu, dividendes, Canada, sans tabac, immobilier et santé) : 200 en 119 s, sept agents, deux thèmes, neuf diapositives sans chiffre absent ni erreur dans la console.
- Site servi : direction artistique Graphite, identifiant de l'agent vocal et adresse de l'API AWS présents ; aucune trace de `localhost`.
- Voix, sur le site CloudFront : appel réel avec un micro simulé qui lit deux réponses parlées en français. L'agent transcrit, appelle `noter_profil` et le profil se remplit à l'écran (horizon, objectif). Dans ce test la liaison WebRTC était bloquée : la reprise par WebSocket a pris le relais.
- Questions sur un actif : SPY pour Amira (compatible), Tesla (à plafonner) et bitcoin (hors profil) pour Robert.
- Démonstrations Robert, Amira et Mateo à 1440 × 900, Mateo à 1280 × 720, Robert à 390 × 844 : aucun contenu hors écran, aucun défilement horizontal.
- « Exporter le dossier » pour une analyse en direct : `/rapport/?source=analyse` s'ouvre avec le bon profil.

### Ajouts du 16 novembre, après l'essai de l'équipe

- Comptes, sur le site CloudFront : présentation, création d'un compte (refus d'un mot de passe faible, d'une confirmation différente, d'un identifiant déjà pris), connexion, mauvais mot de passe, déconnexion, profil conservé après le mode d'emploi. `POST /analyse` sans jeton : 401.
- Analyse complète avec un compte : 200 en 129 s, neuf diapositives, aucun chiffre absent.
- Voix, hésitation : à « je ne sais pas, que me suggérez-vous ? », l'agent explique les quatre objectifs et pose une question sur la situation de la personne.
- Voix, lancement : profil rempli à l'écran, « lancez l'analyse » dit à voix haute, puis deux phrases prononcées pendant que l'outil travaille. Une seule analyse lancée, aucune annulation, présentation affichée après 138 s.
- Curseur de connaissance : écart de 0 px entre le pouce et chaque chiffre, à 1440 × 900 et 1280 × 720. Douze thèmes sur douze avec une illustration de la charte, aucun libellé qui déborde. Montant saisi au dollar près repris dans le profil.
- Présentation et compte à 390 × 844 et 1280 × 600 : boutons atteignables, aucun débordement horizontal.

Non vérifié : un appel vocal complet par une personne (huit questions, analyse, neuf diapositives lues) et un vrai téléphone ; les essais sont faits dans un navigateur piloté.

## Limites

- La création de compte est ouverte à tous (aucune validation par courriel) : le compte limite l'accès à l'analyse, il ne prouve pas l'identité de la personne. La concurrence plafonnée borne le coût.
- La voix (ElevenLabs) demande un micro et un geste (« Démarrer l'appel »). La liaison part en WebRTC et reprend par WebSocket si le réseau bloque l'UDP. Sans micro, l'échange se fait par écrit.
- Un appel vocal est limité à 30 minutes par l'agent ElevenLabs (réglage `max_duration_seconds`, relevé de 600 à 1800 s).
- Sur Lambda, il n'y a ni clé ni cache Finnhub : le critère « sociétés établies » (ancienneté de cotation) répond « information manquante » pour les actions, avec sa raison. Les autres critères ne dépendent que de `data/`.
- Le compte de l'atelier et tout ce qui y est déployé sont supprimés à l'expiration du compte. Le code reste sur GitHub et se redéploie par la commande ci-dessus.
