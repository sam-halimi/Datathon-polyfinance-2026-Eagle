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

## Vérifié le 16 novembre 2026

- `GET /sante`, `GET /actif`, `GET /demonstration/robert` : 200.
- `POST /analyse` sur un profil libre (énergie propre) : 200 en 82 s, format v2, thème tiré de `data/themes.csv`.
- Le site appelle l'API depuis l'adresse CloudFront : CORS en place.
- Site à 1440 px : parcours de démonstration complet, sans erreur dans la console.

## Limites

- L'API `/analyse` est publique et appelle Bedrock : la concurrence plafonnée borne le coût, pas l'accès.
- La voix (ElevenLabs) reste désactivée tant que `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` n'est pas fourni au moment de l'export ; l'échange se fait par écrit.
- À 390 px de large, les panneaux de l'écran de bureau se chevauchent : la mise en page mobile reste à faire côté interface.
- Le compte de l'atelier et tout ce qui y est déployé sont supprimés à l'expiration du compte. Le code reste sur GitHub et se redéploie par la commande ci-dessus.
