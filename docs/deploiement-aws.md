# Déploiement sur AWS

Eagle tourne sur le compte AWS de l'atelier, en `us-east-1` (seule région ouverte au rôle `WSParticipantRole`).

| Quoi | Service | Adresse |
| --- | --- | --- |
| Site | S3 (compartiment privé) + CloudFront, HTTPS | `https://d1ah12vrfzso9b.cloudfront.net` |
| API (`agents/serveur.py`) | AWS Lambda `eagle-api`, adresse de fonction HTTPS | `https://mchhm2dabjrbsfncikiw7i4qfa0hopli.lambda-url.us-east-1.on.aws` |
| Modèle des agents | Amazon Bedrock, appelé avec le rôle IAM `eagle-lambda` (aucune clé) | |

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

## Une seule adresse, une seule branche

- **L'adresse à donner au jury est celle de CloudFront.** Le projet Vercel `alphaforge-polyfinances` date du début du dimanche (dernier envoi à 19 h 37 UTC le 15 novembre) : plus rien n'y est déployé, il montre une ancienne version et n'appelle pas l'API AWS. Ne pas le partager.
- **On déploie depuis une branche qui contient `main`.** Le premier déploiement était parti de `agents-eagle`, qui n'avait pas encore la direction artistique fusionnée dans `main` : le site en ligne et le site local ne se ressemblaient pas. Avant de déployer : `git fetch origin && git merge origin/main`, puis les tests.

## Vérifié le 16 novembre 2026

- `GET /sante`, `GET /actif`, `GET /demonstration/robert` : 200.
- `POST /analyse` sur un profil libre (énergie propre) : 200 en 82 s, format v2, thème tiré de `data/themes.csv`.
- Le site appelle l'API depuis l'adresse CloudFront : CORS en place.
- Site à 1440 px : parcours de démonstration complet, sans erreur dans la console.

## Limites

- L'API `/analyse` est publique et appelle Bedrock : la concurrence plafonnée borne le coût, pas l'accès.
- La voix (ElevenLabs) demande un micro et un geste (« Démarrer l'appel »). La liaison part en WebRTC et reprend par WebSocket si le réseau bloque l'UDP. Sans micro, l'échange se fait par écrit.
- Un appel vocal est limité à 30 minutes par l'agent ElevenLabs (réglage `max_duration_seconds`, relevé de 600 à 1800 s).
- Le compte de l'atelier et tout ce qui y est déployé sont supprimés à l'expiration du compte. Le code reste sur GitHub et se redéploie par la commande ci-dessus.
