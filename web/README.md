# Interface AlphaForge (`web/`)

Site Next.js, conçu à 390 px de large puis adapté au bureau. Aucun défilement dans un écran : une seule chose à la fois.

## Lancer

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

Production : `npm run build && npm run start`. Le micro (étape 3) exigera HTTPS.

## Données

Le site lit les **vraies sorties du pipeline**, là où le pipeline les écrit :

- `agents/sorties/robert.json`, `amira.json`, `mateo.json` (format : `docs/sortie-pipeline.md`, types : `lib/types.ts`) ;
- `tests/scenarios/<persona>.json` pour l'écran de choix (prénom, âge, demande) et les choix de l'accueil.

Les deux dossiers sont hors de `web/` : `next.config.ts` place donc la racine de compilation à la racine du dépôt. Pour mettre à jour l'interface après un nouveau passage du pipeline, il suffit de relancer `python -m agents.pipeline robert amira mateo` puis le build. Aucune copie à tenir à jour.

Seul le persona choisi est chargé (`lib/personas.ts`, import dynamique).

## Ce qu'il y a

- **Départ** : bouton « Démarrer l'appel » (le navigateur exige un geste avant l'audio).
- **Choix du persona** : Robert, Amira ou Mateo, avec sa demande. Le choix charge sa sortie du pipeline.
- **Récapitulatif** : le profil du persona tel que le pipeline l'a lu, avec les choix de l'accueil (« borne basse retenue »…).
- **Analyse** : ce que chaque agent a fait (`etapes`).
- **Six cartes** : profil, répartition, risque, vérifications, pourquoi (trois niveaux : en bref, les chiffres, le calcul), limites (faits, hypothèses, limites). Répartition et risque montrent les 2 ou 3 portefeuilles simulés (A, B, C), le retenu d'abord. Vérifications montre les contrôles de la gouvernance, les rejets renvoyés au constructeur et les titres écartés avec leur source. Puis **« tout voir »** : les six sur un écran.
- **Chiffres touchables** : chaque repère `{id}` d'un texte est remplacé par la valeur de la table `chiffres`, soulignée. La toucher ouvre sa référence d'appel (outil, champ, paramètres, période, formule, source). Un repère inconnu s'affiche « ? » en rouge.
- **Pas de défilement** : une liste trop longue pour l'écran est coupée en pages (‹ › ou glissement), calculées d'après la place réelle (`components/Pages.tsx`).
- **Repli en texte** : la saisie en bas affiche une carte (« risque », « pourquoi », « tout »), comme le fera la voix.

Aucun chiffre n'est écrit par l'interface : elle arrondit pour l'affichage une valeur brute venue de `tools/` (`lib/format.ts`).
