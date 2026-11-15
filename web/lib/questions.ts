import type { Profil } from "./types";

// Les 8 questions d'accueil. Chacune remplit un ou deux champs du profil
// (CLAUDE.md, section Profil). Une question par écran.

export type Option = { valeur: string; titre: string; detail?: string };

export type Question = {
  id: string;
  champ: keyof Profil;
  texte: string;
  aide?: string;
  multiple?: boolean;
  aucun?: string; // libellé du choix « rien », qui vide la liste
  options: Option[];
  saisie?: { champ: keyof Profil; invite: string }; // champ libre en bas d'écran
};

export const QUESTIONS: Question[] = [
  {
    id: "horizon",
    champ: "horizon_annees",
    texte: "Dans combien de temps aurez-vous besoin de cet argent ?",
    options: [
      { valeur: "Moins de 3 ans", titre: "Moins de 3 ans" },
      { valeur: "3 à 5 ans", titre: "3 à 5 ans" },
      { valeur: "5 à 10 ans", titre: "5 à 10 ans" },
      { valeur: "10 à 15 ans", titre: "10 à 15 ans" },
      { valeur: "15 ans et plus", titre: "15 ans et plus" },
    ],
  },
  {
    id: "objectif",
    champ: "objectif",
    texte: "Quel est votre but ?",
    options: [
      { valeur: "Préserver mon capital", titre: "Garder ce que j'ai", detail: "Préserver mon capital" },
      { valeur: "Croître de façon équilibrée", titre: "Croître sans excès", detail: "Un équilibre croissance et stabilité" },
      { valeur: "Faire croître mon capital à long terme", titre: "Faire croître", detail: "Croissance à long terme" },
    ],
  },
  {
    id: "risque",
    champ: "tolerance_risque",
    texte: "Votre portefeuille baisse fort. Comment le vivez-vous ?",
    options: [
      { valeur: "faible", titre: "Ça m'inquiète beaucoup", detail: "Risque faible : je veux de la stabilité" },
      { valeur: "modéré", titre: "Ça m'inquiète un peu", detail: "Risque modéré : des hauts et des bas, ça va" },
      { valeur: "élevé", titre: "Ça ne m'inquiète pas", detail: "Risque élevé : j'accepte de fortes variations" },
    ],
  },
  {
    id: "connaissance",
    champ: "connaissance",
    texte: "Les placements, vous connaissez ?",
    aide: "Je m'adapte : plus simple ou plus détaillé.",
    options: [
      { valeur: "débutant", titre: "Pas vraiment", detail: "Débutant" },
      { valeur: "intermédiaire", titre: "Un peu", detail: "Intermédiaire" },
      { valeur: "avancé", titre: "Bien", detail: "Avancé" },
    ],
  },
  {
    id: "preferences",
    champ: "preferences",
    texte: "Qu'est-ce qui compte pour vous ?",
    aide: "Plusieurs choix possibles.",
    multiple: true,
    aucun: "Rien de particulier",
    options: [
      { valeur: "Garder une diversification", titre: "Ne pas tout miser au même endroit" },
      { valeur: "Critères ESG", titre: "L'environnement et le social (ESG)" },
      { valeur: "Entreprises établies", titre: "Des entreprises solides et connues" },
      { valeur: "Placements canadiens", titre: "Des placements canadiens" },
    ],
  },
  {
    id: "exclusions",
    champ: "exclusions",
    texte: "Voulez-vous écarter quelque chose ?",
    aide: "Plusieurs choix possibles.",
    multiple: true,
    aucun: "Rien à écarter",
    options: [
      { valeur: "Cryptoactifs", titre: "Les cryptoactifs" },
      { valeur: "Énergies fossiles", titre: "Le pétrole et le gaz" },
      { valeur: "Controverses", titre: "Les entreprises controversées" },
    ],
  },
  {
    id: "interets",
    champ: "centres_interet",
    texte: "Un sujet vous passionne ? Une idée précise ?",
    aide: "Un thème reste une petite part, plafonnée.",
    multiple: true,
    aucun: "Aucun",
    options: [
      { valeur: "IA et techno", titre: "IA et techno" },
      { valeur: "Cryptoactifs", titre: "Cryptoactifs" },
      { valeur: "Jeu vidéo", titre: "Jeu vidéo" },
      { valeur: "Santé", titre: "Santé" },
    ],
    saisie: { champ: "demande", invite: "Votre idée, en vos mots" },
  },
  {
    id: "capital",
    champ: "capital_fictif",
    texte: "Combien voulez-vous simuler ?",
    aide: "De l'argent fictif. Rien n'est investi.",
    options: [
      { valeur: "10000", titre: "10 000 $" },
      { valeur: "50000", titre: "50 000 $" },
      { valeur: "100000", titre: "100 000 $" },
    ],
  },
];

export function valeurDe(profil: Profil, q: Question): string[] {
  const v = profil[q.champ];
  if (Array.isArray(v)) return v;
  if (v === undefined || v === null || v === "") return [];
  return [String(v)];
}

export function choisir(profil: Profil, q: Question, valeur: string): Profil {
  if (q.champ === "capital_fictif") return { ...profil, capital_fictif: Number(valeur) };
  if (!q.multiple) return { ...profil, [q.champ]: valeur };
  const actuel = valeurDe(profil, q);
  const suivant = actuel.includes(valeur) ? actuel.filter((x) => x !== valeur) : [...actuel, valeur];
  return { ...profil, [q.champ]: suivant };
}

export function viderListe(profil: Profil, q: Question): Profil {
  return { ...profil, [q.champ]: [] };
}

export function estRepondue(profil: Profil, q: Question): boolean {
  // Une liste vide est une réponse (« rien à écarter »).
  return q.multiple ? true : valeurDe(profil, q).length > 0;
}
