// Option anglaise de l'interface.
//
// Le site est écrit en français. En anglais, chaque texte affiché passe par un dictionnaire
// (lib/en.ts) au moment où il arrive dans la page : un observateur du document traduit les
// nœuds de texte et quelques attributs (aria-label, placeholder, title, alt), et garde le
// français d'origine pour revenir en arrière sans recharger. Un texte absent du dictionnaire
// reste en français : rien n'est inventé. Les textes produits par le pipeline ne passent pas par
// ce dictionnaire : le serveur les renvoie déjà en anglais (agents/traduction.py).

import { EXACT, MOTIFS, PARTIELS } from "./en";

export type Langue = "fr" | "en";
const CLE = "eagle:langue";
const ATTRIBUTS = ["aria-label", "placeholder", "title", "alt"] as const;

let langue: Langue = "fr";
const ecouteurs = new Set<(l: Langue) => void>();
const origine = new WeakMap<Text, string>();
const ecrit = new WeakMap<Text, string>();

export function langueCourante(): Langue {
  return langue;
}

export function lireLangue(): Langue {
  try { return window.localStorage.getItem(CLE) === "en" ? "en" : "fr"; } catch { return "fr"; }
}

export function ecouterLangue(f: (l: Langue) => void): () => void {
  ecouteurs.add(f);
  return () => { ecouteurs.delete(f); };
}

/** Écrit à l'anglaise les nombres d'un texte : « 1 234,5 % » devient « 1,234.5% », « 50 000 $ » devient
 *  « $50,000 ». Seule l'écriture change, jamais la valeur : les chiffres viennent toujours des outils. */
export function nombresEnAnglais(texte: string): string {
  if (!/\d/.test(texte)) return texte;
  return texte
    // Milliers : « 50 000 » -> « 50,000 » (espace simple, insécable ou fine).
    .replace(/(?<![\d.,])\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)/g, (n) => n.replace(/[ \u00a0\u202f]/g, "\u0001"))
    // Décimales : « 12,5 » -> « 12.5 ».
    .replace(/(\d),(\d)/g, "$1.$2")
    .replace(/\u0001/g, ",")
    // Signes : « 12 % » -> « 12% », « 50,000 $ » -> « $50,000 ».
    .replace(/(\d)[ \u00a0\u202f]%/g, "$1%")
    .replace(/([-−+]?)(\d[\d.,]*)[ \u00a0\u202f]\$/g, "$1$$$2");
}

/** Ponctuation à l'anglaise : pas d'espace avant « : ; ? ! », guillemets “ ”. */
function ponctuationAnglaise(texte: string): string {
  return texte
    .replace(/[ \u00a0\u202f]+([:;?!])(?=\s|$|[)”"])/g, "$1")
    .replace(/«[ \u00a0\u202f]?/g, "“")
    .replace(/[ \u00a0\u202f]?»/g, "”");
}

function dictionnaire(coeur: string): string | undefined {
  // La typographie française met des espaces insécables (« ? », « : », guillemets) : le dictionnaire les ignore.
  const cle = coeur.replace(/[\u00a0\u202f]/g, " ");
  const exact = EXACT[cle];
  if (exact !== undefined) return exact;
  for (const [motif, remplacement] of MOTIFS) {
    // (String.replace accepte une chaîne ou une fonction ; le type exact dépend du motif.)
    if (motif.test(cle)) return cle.replace(motif, remplacement as never);
  }
  // Une liste de valeurs connues : « énergies fossiles, tabac ».
  const parts = cle.split(", ");
  if (parts.length > 1 && parts.every((x) => EXACT[x] !== undefined)) return parts.map((x) => EXACT[x]).join(", ");
  let partiel = cle;
  for (const [motif, remplacement] of PARTIELS) partiel = partiel.replace(motif, remplacement as never);
  return partiel === cle ? undefined : partiel;
}

/** Traduit un texte français de l'interface. Inconnu du dictionnaire : les mots restent tels
 *  quels (un texte du pipeline arrive déjà en anglais), seule l'écriture des nombres change. */
export function traduire(texte: string): string {
  const coeur = texte.trim();
  if (!coeur) return texte;
  const debut = texte.indexOf(coeur);
  return texte.slice(0, debut) + ponctuationAnglaise(nombresEnAnglais(dictionnaire(coeur) ?? coeur)) + texte.slice(debut + coeur.length);
}

/** Pour le code qui fabrique un texte hors de la page (voix, transcription) : traduit si l'anglais est choisi. */
export function tr(texte: string): string {
  return langue === "en" ? traduire(texte) : texte;
}

function ignorer(n: Node | null): boolean {
  for (let e = n instanceof Element ? n : n?.parentElement; e; e = e.parentElement) {
    if (e.hasAttribute("data-sans-traduction") || e.tagName === "SCRIPT" || e.tagName === "STYLE" || e.tagName === "CODE") return true;
  }
  return false;
}

function texte(n: Text): void {
  if (ignorer(n)) return;
  const valeur = n.nodeValue ?? "";
  // Un texte différent de ce que nous avons écrit vient de React : c'est le nouvel original.
  if (ecrit.get(n) !== valeur) origine.set(n, valeur);
  const source = origine.get(n) ?? valeur;
  const cible = langue === "en" ? traduire(source) : source;
  if (cible !== valeur) { ecrit.set(n, cible); n.nodeValue = cible; }
}

function attributs(e: Element): void {
  if (ignorer(e)) return;
  for (const a of ATTRIBUTS) {
    const v = e.getAttribute(a);
    if (v === null) continue;
    const garde = `data-fr-${a}`;
    // L'original est gardé à part ; si React a remplacé la valeur, elle redevient l'original.
    const fr = e.getAttribute(garde);
    const source = fr !== null && (v === fr || v === traduire(fr)) ? fr : v;
    if (source !== fr) e.setAttribute(garde, source);
    const cible = langue === "en" ? traduire(source) : source;
    if (cible !== v) e.setAttribute(a, cible);
  }
}

function parcourir(racine: Node): void {
  if (racine.nodeType === Node.TEXT_NODE) { texte(racine as Text); return; }
  if (!(racine instanceof Element)) return;
  attributs(racine);
  const marche = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = marche.nextNode(); n; n = marche.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) texte(n as Text); else attributs(n as Element);
  }
}

let installe = false;

/** À appeler une fois, côté navigateur : lit la langue choisie et suit les changements de la page. */
export function installerTraduction(): void {
  if (installe || typeof window === "undefined") return;
  installe = true;
  langue = lireLangue();
  document.documentElement.lang = langue === "en" ? "en-CA" : "fr-CA";
  new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "characterData") texte(m.target as Text);
      else if (m.type === "attributes") attributs(m.target as Element);
      else m.addedNodes.forEach(parcourir);
    }
  }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRIBUTS] });
  parcourir(document.body);
}

export function choisirLangue(l: Langue): void {
  langue = l;
  try { window.localStorage.setItem(CLE, l); } catch { /* la langue vaut pour cette visite */ }
  if (typeof document !== "undefined") {
    document.documentElement.lang = l === "en" ? "en-CA" : "fr-CA";
    parcourir(document.body);
  }
  ecouteurs.forEach((f) => f(l));
}
