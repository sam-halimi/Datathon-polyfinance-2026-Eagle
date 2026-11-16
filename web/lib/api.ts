import { enteteCompte, fermerSession } from "./compte";
import { langueCourante } from "./langue";
import { profilPourAnalyse } from "./questions";
import type { Profil, SortiePipeline } from "./types";

// Le service du pipeline (agents/serveur.py) : POST /analyse et GET /actif.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const ADRESSE_API = API;
export const COMMANDE_SERVEUR = "python -m agents.serveur";

/** Le service tourne-t-il sur la machine de la personne (développement) ou en ligne ? */
export const SERVICE_LOCAL = /\/\/(localhost|127\.0\.0\.1)(:|\/|$)/.test(API);

/** Échec d'un appel au service, dit en une phrase. `injoignable` : aucune réponse
 *  (serveur arrêté, mauvaise adresse) ; sinon le serveur a répondu par une erreur.
 *  `code` : 401 = connexion requise ou expirée, 503 = panne passagère (relancer suffit). */
export class ErreurService extends Error {
  constructor(message: string, readonly injoignable: boolean, readonly code: number = 0) {
    super(message);
  }
}

/** Prévenu quand le service refuse le jeton (401) : l'écran d'entrée redemande la connexion. */
let surDeconnexion: () => void = () => {};
export function ecouterDeconnexion(f: () => void): void { surDeconnexion = f; }

async function appeler(chemin: string, init?: RequestInit): Promise<Response> {
  let r: Response;
  try {
    r = await fetch(`${API}${chemin}`, { ...init, headers: { ...(init?.headers ?? {}), ...enteteCompte() } });
  } catch {
    throw new ErreurService(SERVICE_LOCAL
      ? `Le service d'analyse ne répond pas à ${API} : lancez-le à la racine du dépôt avec « ${COMMANDE_SERVEUR} ».`
      : "Le service d'analyse ne répond pas. Vérifiez votre connexion à Internet, puis relancez.", true);
  }
  if (!r.ok) {
    let detail = "";
    try {
      detail = ((await r.json()) as { erreur?: string }).erreur ?? "";
    } catch { /* corps illisible : on garde le code */ }
    if (r.status === 401) {
      fermerSession();
      surDeconnexion();
      throw new ErreurService(detail || "Connexion requise : reconnectez-vous.", false, 401);
    }
    // 503 : panne passagère du modèle, la phrase du serveur se suffit (« relancez dans un instant »).
    if (r.status === 503 && detail) throw new ErreurService(detail, false, 503);
    throw new ErreurService(`Le service d'analyse a répondu par une erreur ${r.status}${detail ? ` : ${detail}` : "."}`, false, r.status);
  }
  return r;
}

/** Où en est une analyse (agents/progression.py) : l'agent qui travaille, ce que les précédents ont constaté. */
export type Progression = {
  connu: boolean;
  phase?: "analyse" | "traduction" | "terminee" | "echec";
  agent?: string | null;
  essai?: number;
  agents?: string[];
  faits?: { agent: string; fait: string }[];
};

/** Identifiant de suivi d'une analyse, choisi par le site. */
export function nouveauSuivi(): string {
  try { return crypto.randomUUID(); } catch { return `suivi-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`; }
}

/** Avancement d'une analyse. Jamais d'erreur : sans réponse, l'écran d'attente se passe du détail. */
export async function lireProgression(suivi: string): Promise<Progression | null> {
  try {
    const r = await fetch(`${API}/progression?id=${encodeURIComponent(suivi)}`);
    return r.ok ? ((await r.json()) as Progression) : null;
  } catch {
    return null;
  }
}

export async function analyser(profil: Profil, demande: string, prenom: string, suivi?: string): Promise<SortiePipeline> {
  const r = await appeler("/analyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // `langue` : en anglais, le service traduit les textes de la réponse (agents/traduction.py).
    // `suivi` : identifiant sous lequel le service publie l'avancement, lu par l'écran d'attente.
    body: JSON.stringify({ profil: profilPourAnalyse(profil), demande, prenom: prenom || undefined, langue: langueCourante(), suivi }),
  });
  return r.json();
}

/** Réponse de GET /actif (tools.scenarios.fiche_actif) : statut calculé par des règles, titre,
 *  raisons chiffrées et notes. `compatible` est déduit du statut ici : le serveur ne l'envoie pas. */
export type VerdictActif = {
  symbole: string;
  statut?: "compatible" | "à plafonner" | "hors profil" | "inconnu";
  titre?: string;
  nom?: string;
  notes?: string[];
  compatible?: boolean;
  verdict?: string;
  raisons?: string[];
  explication?: string | string[];
  chiffres?: SortiePipeline["chiffres"];
  [cle: string]: unknown;
};

export async function verifierActif(symbole: string, tolerance: string, horizon: number): Promise<VerdictActif> {
  const q = new URLSearchParams({ symbole, tolerance, horizon: String(horizon), langue: langueCourante() });
  const v = (await (await appeler(`/actif?${q}`)).json()) as VerdictActif;
  return { ...v, compatible: v.compatible ?? v.statut === "compatible" };
}
