// Format provisoire de la sortie du pipeline, calqué sur web/data/exemple.json.
// À aligner sur docs/sortie-pipeline.md quand la branche agents l'aura écrit.

export type Reference = {
  outil: string;
  parametres: Record<string, unknown>;
  periode: { debut: string | null; fin: string | null; observations: number | null };
  valeur: number;
  unite: string;
  formule: string;
  sources: string[];
  details: Record<string, unknown>;
};

export type Profil = {
  prenom?: string;
  horizon_annees: string;
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
  role: string;
  poids: number;
};

export type Portefeuille = {
  id: string;
  nom: string;
  lignes: Ligne[];
  volatilite: string;
  parts_du_risque: Record<string, string>;
  pires_baisses: Record<string, string>;
};

export type Controle = {
  statut: "ok" | "alerte" | "echec";
  titre: string;
  detail: string;
};

export type SortiePipeline = {
  exemple: boolean;
  note: string;
  profil: Profil;
  etapes: { agent: string; fait: string }[];
  portefeuilles: Portefeuille[];
  gouvernance: {
    essai: number;
    essais_max: number;
    statut: "accepte" | "rejete";
    controles: Controle[];
  };
  explication: {
    niveau_par_defaut: 1 | 2 | 3;
    sujet: string;
    niveau1: string;
    niveau2: string[];
    niveau3: { formule: string; lignes: string[] };
  };
  limites: { faits: string[]; hypotheses: string[]; limites: string[] };
  messages: Record<string, string>;
  chiffres: Record<string, Reference>;
};

export const CARTES = ["profil", "repartition", "risque", "verifications", "pourquoi", "limites"] as const;
export type Carte = (typeof CARTES)[number];

export const ETAPES = ["Profil", "Analyse", "Proposition", "Vérification", "Explication"] as const;
