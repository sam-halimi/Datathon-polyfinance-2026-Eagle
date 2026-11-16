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
- Le compte est **facultatif** depuis le 16 novembre : l'écran de connexion propose « Continuer sans compte », et `/analyse`, `/scenarios` et `/actif` acceptent une requête sans jeton. Eagle est un outil de démonstration pour le datathon ; l'analyse, qui appelle Bedrock, est donc ouverte à qui a l'adresse, dans la limite de cinq analyses à la fois (concurrence plafonnée de la fonction). Un jeton présenté reste vérifié : expiré ou faux, il est refusé (401). Pour réserver de nouveau l'analyse aux personnes connectées : variable `EAGLE_COMPTE_OBLIGATOIRE=1` sur la fonction. `/sante`, `/progression` et `/demonstration/<persona>` sont ouvertes.
- Aucune donnée personnelle n'est demandée : un pseudonyme suffit comme identifiant. Eagle ne stocke ni le mot de passe ni le profil ; le profil vit dans le navigateur le temps de la séance.
- Supprimer un compte : console Cognito, ou `aws cognito-idp admin-delete-user --user-pool-id <groupe> --username <identifiant>`.

## Avancement d'une analyse

Une analyse dure de une à trois minutes et l'adresse de fonction ne renvoie sa réponse qu'à la fin. Pour que l'écran d'attente montre ce qui se passe vraiment, le site joint un identifiant de suivi (`suivi`, un UUID) à `POST /analyse`. Le journal du pipeline (`agents/journal.py`) signale chaque agent qui prend la main et chaque étape finie ; `agents/progression.py` écrit cet état dans `s3://eagle-deploiement-<compte>/progression/<id>.json`, et le site le relit par `GET /progression?id=…` toutes les deux secondes et demie. S3 est nécessaire parce que l'analyse et les lectures ne tombent pas sur la même instance de la fonction. Le rôle `eagle-lambda` n'a le droit d'écrire et de lire que ce préfixe ; les fichiers sont effacés au bout d'un jour. L'état ne contient que des noms d'agents et leurs constats. Si l'écriture échoue, l'analyse continue et l'écran d'attente montre seulement le déroulé prévu et le temps écoulé.

## Pannes passagères de Bedrock

Le 16 novembre 2026, entre 0 h 27 et 0 h 35 UTC, Bedrock a répondu « serviceUnavailableException » au milieu des réponses : toutes les analyses échouaient en « erreur 500 », y compris après « Relancer ». Depuis (`agents/resistance.py`) : réponses non diffusées, reprises de botocore, puis modèle de secours (`us.anthropic.claude-sonnet-4-6`, puis `global.anthropic.claude-sonnet-4-5-20250929-v1:0`), trois tours. Si tout échoue, l'API répond 503 avec une phrase claire et le site garde le profil. `meta.modele` de la sortie nomme le modèle qui a réellement répondu.

## Option anglaise

Le pipeline écrit en français. Quand le site est en anglais, il ajoute `langue: "en"` à ses appels (`/analyse`, `/actif`, `/scenarios`) et le service traduit les textes de la réponse avec `agents/traduction.py`, sur Bedrock, par le même chemin que les agents (`agents.modele.creer_agent` : reprises et modèle de secours).

- **Aucun chiffre ne passe par le modèle.** Avant l'appel, chaque nombre, marqueur de chiffre (`{vol_tsla}`), date, nom de fichier, adresse et symbole est remplacé par un jeton (`⟦0⟧`), puis remis tel quel. Une traduction qui perd, ajoute ou répète un jeton est refusée, reprise une fois, et sinon le texte reste en français. `meta.traduction` dit combien de textes ont été traités et combien sont restés en français.
- **Mémoire** : `agents/traductions/en.json` garde les traductions sous leur forme à jetons, donc une phrase d'outil (« Les poids totalisent ⟦0⟧ % du capital fictif. ») n'est traduite qu'une fois pour toutes les valeurs. Elle est embarquée dans la fonction ; sur Lambda, ce qui s'y ajoute ne vit que le temps de l'instance.
- **Coût en temps** : environ 30 secondes de plus qu'une analyse en français (les textes écrits par les agents sont nouveaux à chaque fois).
- **Démonstrations** : déjà traduites dans `agents/sorties/en/` et `web/data/graphiques/en/` (`python -m agents.traduction`, puis `python web/scripts/graphiques.py`). `tests/agents/test_traduction.py` vérifie que l'anglais et le français ont exactement les mêmes chiffres, marqueurs, dates et fichiers.
- Une panne du modèle pendant la traduction ne fait pas échouer l'analyse : elle est rendue en français.

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

### Option anglaise (16 novembre)

- Relevé automatique de tous les textes affichés, écran par écran (présentation, choix, trois cas, huit questions, récapitulatif, attente, panne, neuf diapositives, fiche d'un chiffre, autre proposition, question sur un actif, dossier, comptes) : 1 018 textes en anglais, aucun resté en français hors de ce que la personne a tapé elle-même. Même relevé en français : inchangé.
- Bascule Français / English sans rechargement, dans les deux sens, pendant une démonstration ; aucune erreur dans la console.
- Analyse complète en anglais par l'API AWS (revenu, dividendes, Canada, sans tabac, immobilier et santé) : 200 en 190 s, dont environ 30 s de traduction ; 1 333 textes, 3 restés en français (une même phrase, dont la réponse du modèle était illisible : l'échange avec le modèle a depuis été rendu insensible aux guillemets, et les dix analyses enregistrées se traduisent sans aucun reste). Aucun des mots « advice », « advisor », « recommend ».
- Voix anglaise, appel réel avec un micro simulé qui lit deux réponses en anglais : l'agent anglais se présente, transcrit « In about 10 years » et « I want long-term growth », appelle `noter_profil` avec les valeurs du profil et l'écran suit (Horizon 8 years, Objective Growth).
- Sur le site CloudFront, après le dernier déploiement : même relevé, 1 015 textes en anglais sans reste de français (deux passages), aucun texte anglais en mode français ; le dossier exporté d'une démonstration suit la langue (un croisement de deux chargements l'affichait en français, corrigé). Appel vocal réel en anglais puis en français : chaque langue a son agent, les deux remplissent le profil.
- Téléphone (390 × 844 et 360 × 740) en anglais : en-tête sur une ligne (sigles FR / EN), aucun texte coupé, aucun défilement horizontal.

### Vérification finale du 16 novembre (écran d'attente, compte facultatif, présentation guidée par la voix)

Sur le site CloudFront, dans un navigateur piloté :

- Routes de l'API : `/sante`, les trois démonstrations en français et en anglais, `/actif` (Tesla à plafonner, SPY compatible, bitcoin hors profil, symbole inconnu), `/scenarios`, `/progression`, refus d'un jeton faux (401), requête mal formée (400).
- Entrée : cinq diapositives, choix, création d'un compte (refus d'un mot de passe faible, d'une confirmation différente, d'un identifiant pris), connexion, mauvais mot de passe, déconnexion, puis « Continuer sans compte » : question sur un actif sans jeton, choix retenu après rechargement, « Se connecter » depuis le mode sans compte. Aucune erreur.
- Analyse sans compte : 200 en 140 s en français, 161 s en anglais sur téléphone (huitième étape « Translation »). L'écran d'attente a suivi les agents un par un, lus dans S3 par `/progression`.
- Questions (curseur aligné à 0 px, 12 thèmes et les questions 5 et 6 illustrés, montant au dollar près), neuf diapositives des trois cas à 1440 × 900, 1280 × 720 et 390 × 844 sans contenu coupé, dossier exporté des trois cas (trois camemberts alignés, de même taille), questions sur un actif, autre proposition, « Modifier mon profil ».
- Voix, appel réel avec micro simulé : profil rempli à l'écran reconnu par l'agent, « lancez l'analyse » dit au micro, une seule analyse, écran d'attente réel, puis présentation menée par la voix. Avec la relance automatique, les neuf diapositives s'enchaînent sans intervention (160 s) et l'agent termine par sa question. Pause : aucune parole pendant 20 s, reprise correcte.
- Écran en avance sur la voix : corrigé par `execution_mode: post_tool_speech` sur `afficher_diapositive`. Vérifié sur trois diapositives seulement : l'appel suivant a été coupé par ElevenLabs, **crédits du compte épuisés**.

Limite constatée : le compte ElevenLabs (forfait Starter, 40 000 crédits par mois) est à zéro depuis le 16 novembre vers 4 h 45 UTC ; remise à zéro le 17 novembre à 0 h 27 UTC. Un appel complet (questions, analyse, neuf diapositives) coûte de 3 000 à 4 000 crédits, soit une dizaine d'appels par mois avec ce forfait. Sans crédits, « Démarrer l'appel » affiche « La voix n'est pas disponible pour le moment » et tout le parcours reste possible à l'écran.

Non vérifié : un appel vocal complet par une personne (huit questions, analyse, neuf diapositives lues) et un vrai téléphone ; les essais sont faits dans un navigateur piloté.

## Limites

- Le compte est facultatif et sa création est ouverte à tous (aucune validation par courriel) : il ne protège pas l'analyse et ne prouve pas l'identité de la personne. Seule la concurrence plafonnée (cinq analyses à la fois) borne le coût.
- La voix (ElevenLabs) demande un micro et un geste (« Démarrer l'appel »). La liaison part en WebRTC et reprend par WebSocket si le réseau bloque l'UDP. Sans micro, l'échange se fait par écrit.
- La voix dépend des crédits du compte ElevenLabs : environ 390 crédits par minute d'appel. Un appel laissé ouvert 30 minutes en consomme 16 000. Raccrocher après chaque essai.
- Un appel vocal est limité à 30 minutes par l'agent ElevenLabs (réglage `max_duration_seconds`, relevé de 600 à 1800 s).
- Sur Lambda, il n'y a ni clé ni cache Finnhub : le critère « sociétés établies » (ancienneté de cotation) répond « information manquante » pour les actions, avec sa raison. Les autres critères ne dépendent que de `data/`.
- Le compte de l'atelier et tout ce qui y est déployé sont supprimés à l'expiration du compte. Le code reste sur GitHub et se redéploie par la commande ci-dessus.
