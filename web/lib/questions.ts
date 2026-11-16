import type { Profil } from "./types";

// Les huit questions d'accueil d'Eagle, une par diapositive. Les valeurs
// envoyées sont celles du schéma du profil (python -m agents.profil).
// La connaissance part en `connaissance_niveau` (1 à 5) : le serveur en déduit
// `connaissance`, l'interface ne l'envoie pas.

export type Option = { valeur: string | number; titre: string; detail?: string; icone?: string };
export type Champ =
  | "horizon_annees" | "objectif" | "tolerance_risque" | "connaissance_niveau"
  | "preferences" | "exclusions" | "centres_interet" | "capital_fictif";

type Base = { champ: Champ; texte: string; aide?: string };
export type QuestionChoix = Base & {
  type: "choix";
  options: Option[];
  multiple?: boolean;
  /** Libellé du choix « aucun » d'une question à plusieurs réponses. */
  aucun?: string;
  /** Champ libre sous les options (questions à plusieurs réponses). */
  libre?: string;
};
export type QuestionCurseur = Base & {
  type: "curseur";
  min: number;
  max: number;
  pas: number;
  /** Texte de la bulle pour chaque cran (connaissance). */
  crans?: Record<number, string>;
  /** Valeur proposée tant que la personne n'a pas bougé le curseur. */
  depart: number;
};
export type Question = QuestionChoix | QuestionCurseur;

export const CRANS_CONNAISSANCE: Record<number, string> = {
  1: "Je ne connais pas le fonctionnement des marchés financiers.",
  2: "Je connais les notions de base : action, obligation, fonds.",
  3: "J'ai déjà investi et je comprends la diversification et le risque.",
  4: "Je suis mes placements et je lis des indicateurs comme la volatilité.",
  5: "Je maîtrise la construction de portefeuille : corrélation, duration, allocation d'actifs.",
};

export const QUESTIONS: Question[] = [
  {
    type: "choix", champ: "horizon_annees", texte: "Dans combien d'années prévoyez-vous d'utiliser ce capital ?",
    aide: "Pour une fourchette, la borne basse, plus prudente, est retenue.",
    options: [
      { valeur: 2, titre: "Moins de 3 ans", detail: "Horizon retenu : 2 ans" },
      { valeur: 3, titre: "De 3 à 5 ans", detail: "Horizon retenu : 3 ans" },
      { valeur: 5, titre: "De 5 à 8 ans", detail: "Horizon retenu : 5 ans" },
      { valeur: 8, titre: "De 8 à 12 ans", detail: "Horizon retenu : 8 ans" },
      { valeur: 12, titre: "De 12 à 15 ans", detail: "Horizon retenu : 12 ans" },
      { valeur: 15, titre: "15 ans et plus", detail: "Horizon retenu : 15 ans" },
    ],
  },
  {
    type: "choix", champ: "objectif", texte: "Quel est l'objectif principal de ce placement ?",
    options: [
      { valeur: "préservation du capital", titre: "Préserver le capital", detail: "Limiter les pertes, même au prix d'une croissance faible." },
      { valeur: "revenu", titre: "Percevoir un revenu régulier", detail: "Dividendes et intérêts plutôt que plus-values." },
      { valeur: "équilibre", titre: "Équilibrer croissance et stabilité", detail: "Accepter des variations modérées pour une croissance mesurée." },
      { valeur: "croissance", titre: "Faire croître le capital à long terme", detail: "Accepter des variations marquées en vue de la croissance." },
    ],
  },
  {
    type: "choix", champ: "tolerance_risque",
    texte: "Votre portefeuille perd une part importante de sa valeur en un an. Que faites-vous ?",
    aide: "En cas d'hésitation entre deux réponses, la plus prudente est retenue.",
    options: [
      { valeur: "faible", titre: "Je vends pour limiter la perte", detail: "Tolérance au risque faible" },
      { valeur: "modéré", titre: "J'attends sans modifier le portefeuille", detail: "Tolérance au risque modérée" },
      { valeur: "élevé", titre: "Je renforce la position", detail: "Tolérance au risque élevée" },
    ],
  },
  {
    type: "curseur", champ: "connaissance_niveau", texte: "Comment évaluez-vous votre connaissance des marchés financiers ?",
    aide: "Le vocabulaire et le niveau de détail des explications s'y adaptent.",
    min: 1, max: 5, pas: 1, depart: 3, crans: CRANS_CONNAISSANCE,
  },
  {
    type: "choix", champ: "preferences", texte: "Quelles préférences souhaitez-vous voir respectées ?",
    aide: "Plusieurs réponses possibles.", multiple: true, aucun: "Aucune préférence particulière", libre: "Autre préférence",
    options: [
      { valeur: "ESG", titre: "Critères ESG", detail: "Environnement, social et gouvernance des sociétés" },
      { valeur: "dividendes", titre: "Revenus de dividendes", detail: "Sociétés qui distribuent une part de leurs bénéfices" },
      { valeur: "Canada", titre: "Marché canadien", detail: "Titres et fonds cotés à Toronto" },
      { valeur: "États-Unis", titre: "Marché américain", detail: "Titres et fonds cotés aux États-Unis" },
      { valeur: "FNB indiciels", titre: "Fonds indiciels (FNB)", detail: "Diversification large à faible coût" },
      { valeur: "sociétés établies", titre: "Sociétés établies", detail: "Modèle d'affaires éprouvé et lisible" },
      { valeur: "faible volatilité", titre: "Faible volatilité", detail: "Privilégier les placements les plus stables" },
    ],
  },
  {
    type: "choix", champ: "exclusions", texte: "Souhaitez-vous exclure certains placements ?",
    aide: "Plusieurs réponses possibles.", multiple: true, aucun: "Aucune exclusion", libre: "Autre exclusion (secteur, société, symbole)",
    options: [
      { valeur: "énergies fossiles", titre: "Énergies fossiles", detail: "Pétrole, gaz et charbon" },
      { valeur: "controverses", titre: "Sociétés controversées", detail: "Controverse environnementale ou sociale documentée" },
      { valeur: "crypto", titre: "Cryptoactifs", detail: "Bitcoin, Ether" },
      { valeur: "or", titre: "Or et matières premières", detail: "FNB adossés à l'or" },
      { valeur: "finance", titre: "Secteur financier", detail: "Banques et assureurs" },
      { valeur: "tabac", titre: "Tabac" },
      { valeur: "armement", titre: "Armement" },
    ],
  },
  {
    type: "choix", champ: "centres_interet", texte: "Quels secteurs ou thèmes retiennent votre intérêt ?",
    aide: "Plusieurs réponses possibles. Un thème reste une part limitée du portefeuille, plafonnée.",
    multiple: true, aucun: "Aucun thème", libre: "Autre thème",
    options: [
      { valeur: "technologie", titre: "Technologie", icone: "technologie" },
      { valeur: "intelligence artificielle", titre: "Intelligence artificielle", icone: "ia" },
      { valeur: "jeu vidéo", titre: "Jeu vidéo", icone: "jeu" },
      { valeur: "santé", titre: "Santé", icone: "sante" },
      { valeur: "énergie propre", titre: "Énergie propre", icone: "energie" },
      { valeur: "immobilier", titre: "Immobilier", icone: "immobilier" },
      { valeur: "finance", titre: "Finance", icone: "finance" },
      { valeur: "luxe", titre: "Luxe", icone: "luxe" },
      { valeur: "sport", titre: "Sport", icone: "sport" },
      { valeur: "aérospatiale", titre: "Aérospatiale", icone: "aerospatiale" },
      { valeur: "alimentation", titre: "Alimentation", icone: "alimentation" },
      { valeur: "crypto", titre: "Cryptoactifs", icone: "crypto" },
    ],
  },
  {
    type: "curseur", champ: "capital_fictif", texte: "Quel montant souhaitez-vous simuler ?",
    aide: "Montant fictif, en dollars canadiens : aucune somme n'est investie.",
    min: 5000, max: 1000000, pas: 5000, depart: 50000,
  },
];

export const PROFIL_VIDE: Partial<Profil> = { preferences: [], exclusions: [], centres_interet: [], devise: "CAD" };

const LISTES: Champ[] = ["preferences", "exclusions", "centres_interet"];

/** Écrit une réponse dans le profil (aussi appelé par l'outil vocal noter_profil). */
export function noter(profil: Partial<Profil>, champ: string, valeur: unknown): Partial<Profil> {
  if ((LISTES as string[]).includes(champ)) {
    const c = champ as "preferences" | "exclusions" | "centres_interet";
    const actuel = profil[c] ?? [];
    const liste = Array.isArray(valeur) ? valeur.map(String) : String(valeur).split(/,\s*/).map((x) => x.trim()).filter(Boolean);
    // Une liste complète (voix, ou tableau) remplace ; une valeur seule s'ajoute ou se retire.
    const suivant = Array.isArray(valeur) || liste.length > 1
      ? liste
      : liste.reduce((acc, v) => (acc.includes(v) ? acc.filter((x) => x !== v) : [...acc, v]), actuel);
    return { ...profil, [c]: suivant };
  }
  if (champ === "horizon_annees" || champ === "capital_fictif" || champ === "connaissance_niveau") {
    const n = Number(String(valeur).replace(/\s/g, "").replace(",", ".").replace(/[^\d.]/g, ""));
    if (!Number.isFinite(n) || n <= 0) return profil;
    if (champ === "connaissance_niveau") return { ...profil, connaissance_niveau: Math.min(5, Math.max(1, Math.round(n))) };
    return { ...profil, [champ]: n };
  }
  return { ...profil, [champ]: valeur };
}

function sansAccent(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
}

/** Mots que les gens disent pour une option, quand ils ne reprennent pas son libellé. */
const AUTREMENT_DIT: Record<string, string[]> = {
  ESG: ["esg", "investissement responsable", "responsable", "ethique", "durable"],
  dividendes: ["dividende", "dividendes", "revenus de dividendes"],
  Canada: ["canada", "canadien", "marche canadien", "toronto"],
  "États-Unis": ["etats unis", "usa", "americain", "marche americain"],
  "FNB indiciels": ["fnb", "fonds indiciels", "indiciel", "etf"],
  "sociétés établies": ["societes etablies", "grandes entreprises", "entreprises solides"],
  "faible volatilité": ["faible volatilite", "stable", "peu de variations"],
  "énergies fossiles": ["energies fossiles", "petrole", "gaz", "charbon", "fossile", "fossiles"],
  controverses: ["controverse", "controverses", "societes controversees"],
  crypto: ["crypto", "cryptos", "cryptomonnaie", "cryptomonnaies", "cryptoactifs", "bitcoin"],
  or: ["or", "l or", "metaux precieux"],
  finance: ["finance", "banques", "banque", "secteur financier", "assureurs"],
  tabac: ["tabac", "cigarettes"],
  armement: ["armement", "armes", "defense"],
  technologie: ["technologie", "techno", "tech"],
  "intelligence artificielle": ["intelligence artificielle", "ia"],
  "jeu vidéo": ["jeu video", "jeux video", "gaming"],
  "santé": ["sante", "medical", "pharmaceutique"],
  "énergie propre": ["energie propre", "energies propres", "energie verte", "renouvelable", "renouvelables"],
  immobilier: ["immobilier", "immo"],
  luxe: ["luxe"], sport: ["sport", "sports"], "aérospatiale": ["aerospatiale", "aerospatial", "aviation", "espace"],
  alimentation: ["alimentation", "agroalimentaire", "agriculture"],
};

/** Réponse dictée à une question à plusieurs choix : chaque mot est ramené à la valeur de son option
 *  (pour que la case se coche à l'écran), un texte inconnu reste une réponse libre.
 *  Une seule valeur s'ajoute aux choix déjà faits ; plusieurs valeurs, ou « aucun », remplacent la liste. */
export function listeDite(q: QuestionChoix, actuel: string[] | undefined, valeur: unknown): string[] {
  const dits = (Array.isArray(valeur) ? valeur.map(String) : String(valeur ?? "").split(/[,;]|\bet\b/)).map((x) => x.trim()).filter(Boolean);
  const rien = dits.length === 0 || dits.every((x) => /^(aucun|aucune|rien|non|pas de preference|sans)$/.test(sansAccent(x)));
  if (rien) return [];
  const versOption = (x: string): string => {
    const n = sansAccent(x);
    const o = q.options.find((o) => sansAccent(String(o.valeur)) === n || sansAccent(o.titre) === n
      || (AUTREMENT_DIT[String(o.valeur)] ?? []).includes(n));
    return o ? String(o.valeur) : x;
  };
  const valeurs = Array.from(new Set(dits.map(versOption)));
  return valeurs.length > 1 ? valeurs : Array.from(new Set([...(actuel ?? []), ...valeurs]));
}

/** Le profil envoyé à POST /analyse. Avec le curseur, `connaissance` n'est pas
 *  envoyée : le serveur la déduit de `connaissance_niveau`. */
export function profilPourAnalyse(p: Profil): Record<string, unknown> {
  const { prenom, demande, connaissance, ...reste } = p;
  void prenom; void demande;
  return p.connaissance_niveau ? reste : { ...reste, connaissance };
}

export function complet(p: Partial<Profil>): p is Profil {
  return Boolean(p.horizon_annees && p.objectif && p.tolerance_risque && (p.connaissance_niveau || p.connaissance) && p.capital_fictif);
}

export function estRepondue(p: Partial<Profil>, q: Question): boolean {
  if (q.type === "choix" && q.multiple) return true;
  const v = p[q.champ];
  return v !== undefined && v !== null && v !== "";
}
