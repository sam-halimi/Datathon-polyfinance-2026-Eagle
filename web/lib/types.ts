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
  /** Déduite par le serveur de connaissance_niveau ; présente dans toute sortie du pipeline. */
  connaissance: string;
  /** Curseur de 1 à 5 de l'accueil. */
  connaissance_niveau?: number;
  preferences: string[];
  exclusions: string[];
  centres_interet: string[];
  capital_fictif: number;
  devise: string;
  demande?: string;
};

export type Source = { fichier: string; url: string | null; date: string | null; objet: string };

export type Ligne = {
  symbole: string;
  nom: string;
  classe: string;
  classe_code: string;
  role: string;
  role_code: string;
  poids: number;
  // Format v2 (agents-eagle) : absents d'une sortie v1, affichés « information manquante ».
  poids_id?: string;
  secteur?: string;
  pays?: string;
  devise?: string;
  pourquoi?: string;
  critere_profil?: string;
  plutot_que?: { symbole: string; raison: string } | null;
  chiffres?: { volatilite?: string; pire_baisse?: string; part_du_risque?: string };
  sources?: Source[];
};

export type Adequation = {
  critere: string;
  element: string | null;
  attente: string;
  reponse: string;
  statut: "respecté" | "partiel" | "non couvert";
  raison: string | null;
  chiffres: string[];
  regle: string;
};

export type LimiteSpecifique = { texte: string; type: string; lignes: string[]; chiffres: string[]; importance: number };
export type HypotheseSpecifique = { texte: string; si_elle_tombe: string; type: string; chiffres: string[]; lignes: string[] };

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
  adequation?: Adequation[];
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
    registre?: { niveau: number; nom: string; description: string; ecarts?: string[] };
    lexique?: { terme: string; definition: string }[];
  };
  limites: {
    faits: string[]; hypotheses: string[]; limites: string[];
    methode?: string[];
    limites_specifiques?: LimiteSpecifique[];
    hypotheses_specifiques?: HypotheseSpecifique[];
  };
  adequation?: Adequation[];
  messages: Record<"analyse" | "repartition" | "risque" | "verifications" | "pourquoi" | "limites" | "tout", string>;
  chiffres: Record<string, Reference>;
  exclus: Record<string, string>;
  meta: { modele: string; duree_secondes: number; date: string; version_format?: number };
  graphiques: Graphiques;
  demande_analysee?: { texte: string; resume: string; symboles: { symbole: string; poids: number }[]; classes: string[]; part_risquee: number };
  /** Éventail de scénarios (réponse de POST /analyse). Absent des sorties de démonstration. */
  scenarios?: Scenarios;
};

/** Champ « scenarios » de POST /analyse et GET /demonstration : référence
 *  d'appel de tools.scenarios.eventail_scenarios (voir lib/scenarios.ts). */
export type Scenarios = Omit<Reference, "valeur"> & { valeur: Record<string, number[]> };

export const CARTES = ["profil", "repartition", "risque", "verifications", "pourquoi", "limites"] as const;
export type Carte = (typeof CARTES)[number];

export const ETAPES = ["Profil", "Analyse", "Proposition", "Vérification", "Explication"] as const;

// Données des graphiques : web/data/graphiques/<persona>.json, calculées par
// web/scripts/graphiques.py. Leurs chiffres rejoignent la table « chiffres ».
export type Part = {
  libelle: string; id: string; symboles: string[];
  /** Couleur fixe de la charte (classes d'actif, régions) ; sinon ordre par poids décroissant. */
  couleur?: string;
  /** Région de la carte du monde (id du groupe dans carte-monde-neutre.svg). */
  region?: string;
};
export type Regroupement = "actif" | "classe" | "secteur" | "zone" | "region";

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
