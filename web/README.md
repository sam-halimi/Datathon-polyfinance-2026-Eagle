# Eagle (`web/`)

Site Next.js. Sur ordinateur, un seul écran en trois colonnes : la page ne défile pas, mais un contenu plus long que sa carte (diagnostic des agents, adéquation, vérifications, transcription) défile dans la carte. Sous 900 px de large (téléphone), une seule colonne et la page défile.

- **à gauche** : l'aigle (SVG original, `components/Aigle.tsx`), l'état de l'appel, le bouton « Démarrer l'appel » (voix) et la transcription ;
- **au centre** : une diapositive à la fois ;
- **à droite** : le profil qui se remplit en direct, et trois boutons « Démonstration » (Robert, Amira, Mateo, lus dans `agents/sorties/`).

## Lancer

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

Le pipeline doit répondre sur http://localhost:8000 (autre adresse : `NEXT_PUBLIC_API_URL`). Sans lui, l'analyse en direct est signalée indisponible et les démonstrations marchent.

## Entrée

`components/Entree.tsx` : une présentation en cinq diapositives (ce qu'est Eagle, comment s'en servir), montrée à la première visite et rouverte par « Mode d'emploi » ; puis, sur le site déployé seulement (`NEXT_PUBLIC_COMPTES=1`), la connexion à un compte ; puis le tableau de bord, qui reste monté (rouvrir le mode d'emploi ou se reconnecter ne fait pas perdre le profil).

Comptes (`lib/compte.ts`, `agents/comptes.py`) : un identifiant et un mot de passe, gardés par Amazon Cognito. Aucune adresse courriel. Le site ne conserve que le jeton d'accès (8 heures) dans le stockage local du navigateur et le joint aux appels `/analyse`, `/scenarios` et `/actif`. En local, le serveur n'exige rien et aucun écran de connexion n'apparaît.

## Parcours

1. **Questions** une par une (`lib/questions.ts`, valeurs du schéma `python -m agents.profil`). Chaque réponse remplit le profil à droite. Le montant se règle au curseur ou se saisit au dollar près.
2. **Récapitulatif**, prénom et demande, puis `POST /analyse` avec `{profil, demande, prenom}` (`lib/api.ts`). Pendant l'attente, les agents au travail.
3. **Présentation** (`components/Diapositives.tsx`) : la démarche (les étapes des agents et le diagnostic de chaque spécialiste, champ `specialistes`), la demande face au profil, répartition (camemberts actif, secteur, zone), cours commenté de l'actif demandé, « Scénarios, pas une prévision » (champ `scenarios`), vérifications, limites. Chaque diapositive a sa justification et le texte que la voix lit.
4. **Question sur un actif** à tout moment (« et Tesla ? ») : `GET /actif?symbole=…&tolerance=…&horizon=…`, diapositive « compatible » ou « pourquoi cet actif ne convient pas à ton profil ».

Le dossier imprimable (bouton « Exporter le dossier ») : `/rapport/?persona=…` pour une démonstration, `/rapport/?source=analyse` pour une analyse en direct (la réponse du pipeline passe par le stockage local du navigateur, rien n'est envoyé ailleurs).

## Voix

ElevenLabs Agents (`components/Voix.tsx`, `@elevenlabs/react`), identifiant dans `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` (`web/.env.local`). Trois outils côté client : `noter_profil(champ, valeur)`, `lancer_analyse()`, `afficher_diapositive(id)`. Configuration exacte de l'agent : `docs/agent-elevenlabs.md`. Sans identifiant, tout marche par écrit. Une seule analyse à la fois : un second `lancer_analyse` rejoint celle en cours. La liaison audio part en WebRTC ; si le réseau la bloque (UDP fermé), elle reprend une fois par WebSocket. Le déploiement (`deploiement/deployer.py`) fournit l'identifiant à l'export.

## Anglais

Le bouton « Français / English » (`components/Langue.tsx`) est sur chaque écran. Le site reste écrit en français ; en anglais :

- **Interface** : `lib/langue.ts` traduit chaque texte au moment où il arrive dans la page, avec le dictionnaire `lib/en.ts` (`EXACT` pour une phrase entière, `MOTIFS` pour une phrase à trous, `PARTIELS` pour une date au milieu d'un texte). Le français d'origine est gardé : on change de langue sans recharger. Un texte absent du dictionnaire reste tel quel, rien n'est inventé. Pour ajouter un texte à l'interface, ajouter sa ligne dans `lib/en.ts`.
- **Nombres** : mêmes valeurs, écriture anglaise (« 12,5 % » devient « 12.5% », « 50 000 $ » devient « $50,000 »). C'est un changement d'écriture fait par le code (`nombresEnAnglais`), jamais par un modèle.
- **Résultat de l'analyse** : le site envoie `langue: "en"` à `/analyse`, `/actif` et `/scenarios` ; le service traduit les textes (`agents/traduction.py`, voir `docs/deploiement-aws.md`). Les trois démonstrations sont déjà traduites : `agents/sorties/en/` et `data/graphiques/en/`.
- **Voix** : un second agent ElevenLabs, en anglais (`NEXT_PUBLIC_ELEVENLABS_AGENT_ID_EN`, `docs/agent-elevenlabs-en.md`).

Une démonstration suit le changement de langue tout de suite. Une analyse en direct garde la langue dans laquelle elle a été demandée : il faut la relancer pour l'avoir dans l'autre.

## Données et chiffres

- Chaque chiffre affiché est un repère `{id}` de la table `chiffres` : le toucher ouvre sa référence (outil, paramètres, période, formule, source).
- `python web/scripts/graphiques.py` (depuis la racine) écrit `data/graphiques/<persona>.json` (camemberts, cours et éventail de scénarios des démonstrations) et `data/univers.json` (secteur, zone et cours hebdomadaire de tous les actifs des deux tables sourcées, univers étendu et thèmes compris, pour les analyses en direct, calculées dans `lib/repartition.ts`). À relancer quand `data/` ou `agents/sorties/` change : `tests/interface/` échoue sinon, et le déploiement le relance de lui-même.
- Une information absente (scénarios, cours) est signalée, jamais remplacée.
