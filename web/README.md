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

## Parcours

1. **Questions** une par une (`lib/questions.ts`, valeurs du schéma `python -m agents.profil`). Chaque réponse remplit le profil à droite.
2. **Récapitulatif**, prénom et demande, puis `POST /analyse` avec `{profil, demande, prenom}` (`lib/api.ts`). Pendant l'attente, les agents au travail.
3. **Présentation** (`components/Diapositives.tsx`) : la démarche (les étapes des agents et le diagnostic de chaque spécialiste, champ `specialistes`), la demande face au profil, répartition (camemberts actif, secteur, zone), cours commenté de l'actif demandé, « Scénarios, pas une prévision » (champ `scenarios`), vérifications, limites. Chaque diapositive a sa justification et le texte que la voix lit.
4. **Question sur un actif** à tout moment (« et Tesla ? ») : `GET /actif?symbole=…&tolerance=…&horizon=…`, diapositive « compatible » ou « pourquoi cet actif ne convient pas à ton profil ».

Le dossier imprimable (bouton « Exporter le dossier ») : `/rapport/?persona=…` pour une démonstration, `/rapport/?source=analyse` pour une analyse en direct (la réponse du pipeline passe par le stockage local du navigateur, rien n'est envoyé ailleurs).

## Voix

ElevenLabs Agents (`components/Voix.tsx`, `@elevenlabs/react`), identifiant dans `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` (`web/.env.local`). Trois outils côté client : `noter_profil(champ, valeur)`, `lancer_analyse()`, `afficher_diapositive(id)`. Configuration exacte de l'agent : `docs/agent-elevenlabs.md`. Sans identifiant, tout marche par écrit. La liaison audio part en WebRTC ; si le réseau la bloque (UDP fermé), elle reprend une fois par WebSocket. Le déploiement (`deploiement/deployer.py`) fournit l'identifiant à l'export.

## Données et chiffres

- Chaque chiffre affiché est un repère `{id}` de la table `chiffres` : le toucher ouvre sa référence (outil, paramètres, période, formule, source).
- `python web/scripts/graphiques.py` (depuis la racine) écrit `data/graphiques/<persona>.json` (camemberts, cours et éventail de scénarios des démonstrations) et `data/univers.json` (secteur, zone et cours hebdomadaire de tous les actifs des deux tables sourcées, univers étendu et thèmes compris, pour les analyses en direct, calculées dans `lib/repartition.ts`). À relancer quand `data/` ou `agents/sorties/` change : `tests/interface/` échoue sinon, et le déploiement le relance de lui-même.
- Une information absente (scénarios, cours) est signalée, jamais remplacée.
