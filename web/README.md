# Eagle (`web/`)

Site Next.js pour ordinateur, format horizontal. Un seul écran en trois colonnes, sans défilement :

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
3. **Présentation** (`components/Diapositives.tsx`) : la demande face au profil, répartition (camemberts actif, secteur, zone), cours commenté de l'actif demandé, « Scénarios, pas une prévision » (champ `scenarios`), vérifications, limites. Chaque diapositive a sa justification et le texte que la voix lit.
4. **Question sur un actif** à tout moment (« et Tesla ? ») : `GET /actif?symbole=…&tolerance=…&horizon=…`, diapositive « compatible » ou « pourquoi cet actif ne convient pas à ton profil ».

Le dossier imprimable reste sur `/rapport?persona=…` (bouton « Exporter le dossier »).

## Voix

ElevenLabs Agents (`components/Voix.tsx`, `@elevenlabs/react`), identifiant dans `NEXT_PUBLIC_ELEVENLABS_AGENT_ID` (`web/.env.local`). Trois outils côté client : `noter_profil(champ, valeur)`, `lancer_analyse()`, `afficher_diapositive(id)`. Configuration exacte de l'agent : `docs/agent-elevenlabs.md`. Sans identifiant, tout marche par écrit.

## Données et chiffres

- Chaque chiffre affiché est un repère `{id}` de la table `chiffres` : le toucher ouvre sa référence (outil, paramètres, période, formule, source).
- `python web/scripts/graphiques.py` (depuis la racine) écrit `data/graphiques/<persona>.json` (camemberts et cours des démonstrations) et `data/univers.json` (secteur, zone et cours hebdomadaire de chaque actif, pour les analyses en direct, calculées dans `lib/repartition.ts`).
- Une information absente (scénarios, cours) est signalée, jamais remplacée.
