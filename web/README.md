# Interface AlphaForge (`web/`)

Site Next.js, conçu à 390 px de large puis adapté au bureau. Aucun défilement dans un écran : une seule chose à la fois.

## Lancer

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

Production : `npm run build && npm run start`. Le micro (étape 3) exigera HTTPS.

## Ce qu'il y a

- **Départ** : bouton « Démarrer l'appel » (le navigateur exige un geste avant l'audio).
- **Accueil en texte** : 8 questions, une par écran, puis un récapitulatif à valider. Elles remplissent les champs du profil de `CLAUDE.md` (`lib/questions.ts`).
- **Écran d'appel** : barre d'étapes (Profil, Analyse, Proposition, Vérification, Explication), l'assistant en haut, une carte au milieu, la saisie en bas.
- **Six cartes** : profil, répartition, risque, vérifications, pourquoi (trois niveaux : en bref, les chiffres, le calcul), limites (faits, hypothèses, limites). Puis **« tout voir »** : les six sur un écran.
- **Chiffres touchables** : chaque chiffre souligné ouvre sa référence d'appel (outil, paramètres, période, formule, source).
- **Repli en texte** : la saisie en bas affiche une carte (« risque », « pourquoi », « tout »), comme le fera la voix.

## Données

L'interface lit `data/exemple.json`, en attendant la sortie du pipeline (`docs/sortie-pipeline.md`, branche `agents`). Types : `lib/types.ts`.

Le fichier se régénère depuis la racine du dépôt :

```bash
python web/scripts/exemple.py
```

Aucun chiffre écrit à la main. Les mesures par actif viennent de vrais appels à `tools/mesures.py` (`volatilite`, `pire_baisse`) et gardent leur référence. Les mesures de portefeuille (60 % SPY, 30 % AGG, 10 % BTC) sont recopiées de `analyses/exemples_explications.py` et marquées « en attente » jusqu'à ce que `stats_portefeuille` et `parts_du_risque` existent dans `tools/`.

Les textes portent des repères `{id}` que l'interface remplace par le chiffre de la table `chiffres`. Un repère inconnu s'affiche « ? » en rouge.
