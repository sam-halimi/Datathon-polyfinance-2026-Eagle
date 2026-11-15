// Format de la sortie du pipeline : docs/sortie-pipeline.md.
// Les fichiers lus sont agents/sorties/<persona>.json. Seuls les champs
// affichés sont typés ; les autres (journal, specialistes…) sont ignorés.

export type Reference = {
  outil: string;
  parametres: Record<string, unknown>;
  periode: { debut: string | null; fin: string | null; observations: number | null };
  valeur: number;
  unite: string;
  formule: string;
  sources: string[];
  details: Record<string, unknown>;
  champ?: string;
};

export type Profil = {
  prenom?: string;
  horizon_annees: number;
  objectif: string;
  tolerance_risque: string;
  connaissance: string;
  preferences: string[];
  exclusions: string[];
  centres_interet: string[];
  capital_fictif: number;
  devise: string;
  demande?: string;
};

export type Ligne = {
  symbole: string;
  nom: string;
  classe: string;
  classe_code: string;
  role: string;
  role_code: string;
  poids: number;
};

export type Controle = {
  statut: "ok" | "alerte" | "echec";
  titre: string;
  detail: string;
  controle?: string;
  statut_outil?: string;
  symboles?: string[];
  chiffres?: string[];
  source?: string;
};

export type Portefeuille = {
  id: string;
  nom: string;
  intention: string;
  lignes: Ligne[];
  volatilite: string;
  pire_baisse: string;
  parts_du_risque: Record<string, string>;
  pires_baisses: Record<string, string>;
  volatilites: Record<string, string>;
  theme: { nom: string; symboles: string[] } | null;
  essai: number;
  controles: Controle[];
};

export type Proposition = {
  essai: number;
  portefeuille: string;
  nom: string;
  accepte: boolean;
  rejets: string[];
};

export type SortiePipeline = {
  exemple: boolean;
  note: string;
  scenario: string;
  profil: Profil;
  etapes: { agent: string; fait: string }[];
  portefeuilles: Portefeuille[];
  gouvernance: {
    essai: number;
    essais_max: number;
    statut: "accepte";
    portefeuille_retenu: string;
    controles: Controle[];
    historique: Proposition[];
  };
  explication: {
    niveau_par_defaut: 1 | 2 | 3;
    sujet: string;
    niveau1: string;
    niveau2: string[];
    niveau3: { formule: string; lignes: string[] };
    chiffre_central: string;
  };
  limites: { faits: string[]; hypotheses: string[]; limites: string[] };
  messages: Record<"analyse" | "repartition" | "risque" | "verifications" | "pourquoi" | "limites" | "tout", string>;
  chiffres: Record<string, Reference>;
  exclus: Record<string, string>;
  meta: { modele: string; duree_secondes: number; date: string };
  graphiques: Graphiques;
  demande_analysee?: { texte: string; resume: string; symboles: { symbole: string; poids: number }[]; classes: string[]; part_risquee: number };
  /** Éventail de scénarios (réponse de POST /analyse). Absent des sorties de démonstration. */
  scenarios?: Scenarios;
};

/** Format attendu du champ « scenarios » : une médiane et des bandes par
 *  date ou année, en valeur du capital fictif ou en multiple du départ.
 *  Chaque série peut renvoyer à un chiffre de la table (reference). */
export type Scenarios = {
  titre?: string;
  unite?: string;
  abscisses?: (string | number)[];
  annees?: (string | number)[];
  mediane: number[];
  bandes?: { nom?: string; niveau?: number | string; bas: number[]; haut: number[] }[];
  reference?: string;
  chiffres?: Record<string, Reference>;
  hypotheses?: string[];
  methode?: string;
  [cle: string]: unknown;
};

export const CARTES = ["profil", "repartition", "risque", "verifications", "pourquoi", "limites"] as const;
export type Carte = (typeof CARTES)[number];

export const ETAPES = ["Profil", "Analyse", "Proposition", "Vérification", "Explication"] as const;

// Données des graphiques : web/data/graphiques/<persona>.json, calculées par
// web/scripts/graphiques.py. Leurs chiffres rejoignent la table « chiffres ».
export type Part = { libelle: string; id: string; symboles: string[] };
export type Regroupement = "actif" | "secteur" | "zone";

export type Graphiques = {
  note: string;
  repartitions: Record<string, Record<Regroupement, Part[]>>;
  cours: {
    symbole: string;
    id: string;
    nom: string;
    devise: string;
    points: [string, number][];
    date_pic: string;
    date_creux: string;
    reference: string;
    sources: string[];
  };
  chiffres: Record<string, Reference>;
};
