# DA Eagle — règles d'usage pour le site

Dossier à copier dans le projet Next.js. Source de vérité : `tokens.json` (même contenu que le design system « Eagle »).

## Contenu du dossier

| Fichier | Rôle |
|---|---|
| `tokens.css` | Variables CSS (couleurs, espacements, rayons, ombres, durées, courbes, polices) et classes de typographie `eg-*` |
| `tokens.json` | Les mêmes tokens en données (format du design system) |
| `eagle-components.css` | Composants : bouton, carte, curseur, anneau, ligne de portefeuille, bandeau d'alerte, avatar, apparitions |
| `logo/` | `eagle-logo-horizontal.svg`, `eagle-logo-vertical.svg`, `eagle-wordmark.svg`, `eagle-emblem.svg`, `eagle-badge.svg` |
| `avatar/` | `eagle-avatar-ecoute.svg`, `eagle-avatar-parle.svg`, `eagle-avatar-reflechit.svg` (animés) |
| `illustrations/` | `secteur-*.svg` (9) et `carte-monde.svg`, `carte-monde-neutre.svg` |

## Installation

1. Copier le dossier dans `src/styles/eagle/` (CSS et JSON) et les SVG dans `public/eagle/`.
2. Charger les polices et les feuilles dans `app/layout.tsx` :

```tsx
import { IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import "@/styles/eagle/tokens.css";
import "@/styles/eagle/eagle-components.css";

const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-sans" });
const plexSerif = IBM_Plex_Serif({ subsets: ["latin"], weight: ["500"], variable: "--font-plex-serif" });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${plexSans.variable} ${plexSerif.variable}`}>
      <body style={{ background: "var(--bg)", color: "var(--text)", fontFamily: "var(--font-sans)" }}>{children}</body>
    </html>
  );
}
```

3. Utiliser les variables (`var(--accent)`) et les classes (`eg-btn eg-btn--primary`, `eg-title-question`…). Ne jamais recopier une valeur hexadécimale dans un composant.

## Avatar et voix (ElevenLabs)

Brancher l'état de l'avatar sur la conversation :

```tsx
type EagleState = "ecoute" | "parle" | "reflechit";
<div className="eg-avatar" data-state={state} role="img" aria-label={`Eagle — ${state}`}>
  <img src="/eagle/logo/eagle-badge.svg" alt="" />
  <svg className="eg-avatar__arc" viewBox="0 0 180 180" aria-hidden="true">
    <circle cx="90" cy="90" r="86" fill="none" stroke="var(--signature)" strokeWidth="3" strokeLinecap="round" strokeDasharray="120 460" />
  </svg>
</div>
<div className="eg-voice" data-active={state === "parle"} aria-hidden="true"><span /><span /><span /><span /></div>
```

- `ecoute` : le micro est ouvert. `parle` : l'agent émet de l'audio. `reflechit` : entre la fin de la question et le début de la réponse (calcul du portefeuille).

## Curseur

`.eg-slider` porte `--p` (0 à 1). À chaque `onChange` : `style={{ "--p": (v - min) / (max - min) }}`, mise à jour du texte de la bulle et de `aria-valuetext`.

## Anneau

Rayon 88, épaisseur 22, `stroke-dasharray = longueur − 4` puis `circonférence`, `stroke-dashoffset = −cumul`, `transform="rotate(-90 110 110)"`. Couleurs par `style={{ stroke: "var(--chart-1)" }}`. Tracé initial : partir de `0 C` puis passer à la longueur, avec `transition-delay` = rang × 60 ms.

## Carte du monde

Charger `carte-monde-neutre.svg` en ligne (pas en `<img>`) pour pouvoir colorer chaque région : `#europe { fill: var(--chart-2) }`. Les régions sans exposition restent en `#3A434D`. `carte-monde.svg` est la version déjà colorée, pour une image fixe.

## Règles de la charte


Eagle est un assistant vocal : l'investisseur parle à un aigle, et l'écran présente son profil, les graphiques et les justifications comme un diaporama. Projet du Datathon PolyFinances 2026. Écran d'ordinateur, format horizontal (référence 1280 × 720).

### Ton

Gestion de patrimoine : formel, précis, calme. L'investisseur doit se sentir entouré par un professionnel. Ni enfantin, ni « appli crypto ».

- Vouvoiement, phrases courtes, un chiffre concret plutôt qu'un adjectif (« une baisse de 10 000 $ » plutôt que « une forte baisse »).
- Chaque choix du portefeuille est justifié en une ou deux phrases, en langage courant.
- Typographie française : espace insécable avant %, $, :, ?, ! ; signe moins « − » ; montants « 50 000 $ ».
- Mention « Simulation, pas un conseil financier » sur les écrans de résultat.

### Logo

- **Emblème** : tête de pygargue taillée en facettes, tons acier (`steel-050` à `steel-700`), bec ambre (`signature-light`, `signature`, `signature-dark`).
- **Logotype** : EAGLE en capitales géométriques dessinées, A sans barre, G octogonal, approche large.
- Versions : horizontale, verticale, logotype seul, emblème seul, pastille (emblème dans un disque `surface-2`).
- Toujours sur fond graphite (`bg`, `surface-1`). Sur fond clair ou photo : la pastille uniquement.
- Zone de protection : la hauteur du E autour du logo. Taille minimale : emblème 24 px, logo horizontal 120 px de large.
- Ne pas recolorer, étirer, ajouter d'ombre ou de contour, ni remplacer le logotype par une police.

### Couleurs

Thème unique « Graphite ». Fond `bg` #111417, cartes `surface-1` #191D22, pastilles et survols `surface-2` #232930.

- **Accent** acier `accent` #8DB4D9 : action principale, curseur, focus. Environ 10 % de l'écran au plus.
- **Signature** ambre `signature` #D9A15B : le bec, l'état « réfléchit », un détail de marque. Jamais pour un bouton ni un état.
- **États** : respecté `success`, alerte `warning`, refusé `danger`, toujours avec icône et libellé.
- **Texte** : `text` pour le courant, `text-muted` pour le secondaire, `text-subtle` seulement sur `bg` ou `surface-1`.

### Graphiques

Huit couleurs `chart-1` à `chart-8`, vérifiées sur `surface-1` : contraste d'au moins 3:1 pour chacune, et écart de couleur d'au moins 9,8 (CIEDE2000) entre deux couleurs quelconques, en vision normale comme en protanopie, deutéranopie et tritanopie simulées.

- Ordre d'usage : `chart-1`, puis 2, 3… par poids décroissant.
- Classes d'actifs, correspondance fixe : Actions `chart-1`, Or `chart-2`, Immobilier `chart-3`, Obligations `chart-4`, Crypto-actifs `chart-5`, Liquidités `chart-8`.
- Régions (carte du monde) : Amérique du Nord `chart-1`, Amérique latine `chart-3`, Europe `chart-2`, Afrique et Moyen-Orient `chart-4`, Asie `chart-6`, Océanie `chart-5`.
- Toujours une légende ou des étiquettes directes : la couleur n'est jamais la seule information.
- 4 px d'écart entre segments, pas d'ombre, pas de dégradé, pas de 3D.

### Typographie

- **Titres** : IBM Plex Serif 500 (`eg-display`, `eg-title-1`, `eg-title-question`, `eg-title-2`, `eg-title-3`). La question posée par Eagle est toujours en `eg-title-question`.
- **Texte** : IBM Plex Sans 400 à 600 (`eg-text-lg`, `eg-text`, `eg-text-sm`, `eg-caption`, `eg-label`, `eg-button`).
- **Chiffres** : IBM Plex Sans 500 en chiffres tabulaires (`font-variant-numeric: tabular-nums`) pour tous les montants et pourcentages (`eg-num-xl` à `eg-num-sm`), alignés à droite dans les listes.
- Polices Google Fonts, chargées avec `next/font/google` dans le site.

### Espacements et formes

Grille de 4 px : `space-1` (4) à `space-9` (72). Écran 1280 × 720 avec 40 px de marge (`space-7`). Rayons : `radius-sm` 6, `radius-md` 10 (boutons, bandeaux), `radius-lg` 20 (cartes), `radius-full` (avatar, pistes). Ombres très discrètes, réservées au survol et aux fenêtres.

### Mouvement

Durées `duration-instant` (100 ms) à `duration-reveal` (600 ms), décalage en cascade `duration-stagger` (60 ms). Courbes `ease-standard`, `ease-enter`, `ease-exit`, `ease-calm`. Calme : pas de rebond. Détails dans le composant Motion. `prefers-reduced-motion` respecté partout.

### Illustrations

Même construction que l'emblème : des facettes planes, lumière en haut à gauche, tons acier et ambre, posées sur une plaque hexagonale. Neuf secteurs et thèmes : technologie, santé, énergie, finance, immobilier, jeu vidéo, crypto-actifs, or, obligations. Une carte du monde en hexagones, un groupe par région (`id` = `amerique-du-nord`, `amerique-latine`, `europe`, `afrique-moyen-orient`, `asie`, `oceanie`) pour la colorer selon la répartition géographique.

### Icônes

Trait de 2 px, extrémités arrondies, grille de 24 px, couleur héritée (`currentColor`). Aucune émoticône.
