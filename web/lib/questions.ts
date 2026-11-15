import type { Profil } from "./types";

// Les questions d'accueil d'Eagle, une par diapositive. Les valeurs sont
// celles du schéma du profil (python -m agents.profil) : rien à traduire.

export type Option = { valeur: string | number; titre: string; detail?: string };
export type Champ = "horizon_annees" | "objectif" | "tolerance_risque" | "connaissance" | "preferences" | "exclusions" | "centres_interet" | "capital_fictif";

export type Question = { champ: Champ; texte: string; aide?: string; multiple?: boolean; aucun?: string; options: Option[] };

export const QUESTIONS: Question[] = [
  {
    champ: "horizon_annees", texte: "Dans combien d'années prévoyez-vous d'utiliser ce capital ?",
    aide: "Pour une fourchette, la borne basse, plus prudente, est retenue.",
    options: [
      { valeur: 2, titre: "Moins de 3 ans", detail: "2 ans retenus" },
      { valeur: 3, titre: "3 à 5 ans", detail: "3 ans retenus" },
      { valeur: 8, titre: "8 à 12 ans", detail: "8 ans retenus" },
      { valeur: 15, titre: "15 ans et plus", detail: "15 ans retenus" },
    ],
  },
  {
    champ: "objectif", texte: "Quel est l'objectif principal de ce placement ?",
    options: [
      { valeur: "préservation du capital", titre: "Garder ce que j'ai", detail: "Préservation du capital" },
      { valeur: "revenu", titre: "Un revenu régulier", detail: "Revenu" },
      { valeur: "équilibre", titre: "Croître sans excès", detail: "Équilibre" },
      { valeur: "croissance", titre: "Faire croître à long terme", detail: "Croissance" },
    ],
  },
  {
    champ: "tolerance_risque", texte: "Votre portefeuille perd une part importante de sa valeur en un an. Que faites-vous ?",
    aide: "En cas d'hésitation entre deux réponses, la plus prudente est retenue.",
    options: [
      { valeur: "faible", titre: "Je vends pour limiter la perte", detail: "Tolérance faible" },
      { valeur: "modéré", titre: "J'attends sans modifier le portefeuille", detail: "Tolérance modérée" },
      { valeur: "élevé", titre: "Je renforce la position", detail: "Tolérance élevée" },
    ],
  },
  {
    champ: "connaissance", texte: "Quelle est votre connaissance des marchés financiers ?", aide: "Le niveau des explications s'y adapte.",
    options: [
      { valeur: "débutant", titre: "Pas vraiment", detail: "Débutant" },
      { valeur: "intermédiaire", titre: "Un peu", detail: "Intermédiaire" },
      { valeur: "avancé", titre: "Bien", detail: "Avancé" },
    ],
  },
  {
    champ: "preferences", texte: "Quelles sont vos préférences de placement ?", multiple: true, aucun: "Rien de particulier",
    options: [
      { valeur: "ESG", titre: "L'environnement et le social (ESG)" },
      { valeur: "dividendes", titre: "Des dividendes" },
      { valeur: "Canada", titre: "Des placements canadiens" },
    ],
  },
  {
    champ: "exclusions", texte: "Souhaitez-vous exclure certains placements ?", multiple: true, aucun: "Rien à écarter",
    options: [
      { valeur: "énergies fossiles", titre: "Le pétrole et le gaz" },
      { valeur: "controverses", titre: "Les entreprises à controverses" },
      { valeur: "crypto", titre: "Les cryptoactifs" },
    ],
  },
  {
    champ: "centres_interet", texte: "Quels secteurs ou thèmes retiennent votre intérêt ?", aide: "Un thème reste une part limitée du portefeuille, plafonnée.", multiple: true, aucun: "Aucun",
    options: [
      { valeur: "technologie", titre: "La technologie" },
      { valeur: "crypto", titre: "Les cryptoactifs" },
      { valeur: "santé", titre: "La santé" },
    ],
  },
  {
    champ: "capital_fictif", texte: "Quel montant souhaitez-vous simuler ?", aide: "Montant fictif : aucune somme n'est investie.",
    options: [
      { valeur: 10000, titre: "10 000 $" },
      { valeur: 50000, titre: "50 000 $" },
      { valeur: 200000, titre: "200 000 $" },
    ],
  },
];

export const PROFIL_VIDE: Partial<Profil> = { preferences: [], exclusions: [], centres_interet: [], devise: "CAD" };

/** Écrit une réponse dans le profil (aussi appelé par l'outil vocal noter_profil). */
export function noter(profil: Partial<Profil>, champ: string, valeur: unknown): Partial<Profil> {
  const q = QUESTIONS.find((x) => x.champ === champ);
  if (q?.multiple) {
    const actuel = (profil[q.champ] as string[] | undefined) ?? [];
    const liste = Array.isArray(valeur) ? valeur.map(String) : String(valeur).split(/,\s*/).filter(Boolean);
    const suivant = Array.isArray(valeur) ? liste : liste.reduce((acc, v) => (acc.includes(v) ? acc.filter((x) => x !== v) : [...acc, v]), actuel);
    return { ...profil, [q.champ]: suivant };
  }
  if (champ === "horizon_annees" || champ === "capital_fictif") {
    const n = Number(String(valeur).replace(/[^\d.]/g, ""));
    return Number.isFinite(n) && n > 0 ? { ...profil, [champ]: n } : profil;
  }
  return { ...profil, [champ]: valeur };
}

export function complet(p: Partial<Profil>): p is Profil {
  return Boolean(p.horizon_annees && p.objectif && p.tolerance_risque && p.connaissance && p.capital_fictif);
}
