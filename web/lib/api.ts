import { profilPourAnalyse } from "./questions";
import type { Profil, SortiePipeline } from "./types";

// Le service du pipeline (agents/serveur.py) : POST /analyse et GET /actif.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const ADRESSE_API = API;
export const COMMANDE_SERVEUR = "python -m agents.serveur";

/** Échec d'un appel au service, dit en une phrase. `injoignable` : aucune réponse
 *  (serveur arrêté, mauvaise adresse) ; sinon le serveur a répondu par une erreur. */
export class ErreurService extends Error {
  constructor(message: string, readonly injoignable: boolean) {
    super(message);
  }
}

async function appeler(chemin: string, init?: RequestInit): Promise<Response> {
  let r: Response;
  try {
    r = await fetch(`${API}${chemin}`, init);
  } catch {
    throw new ErreurService(
      `Le service d'analyse ne répond pas à ${API} : lancez-le à la racine du dépôt avec « ${COMMANDE_SERVEUR} ».`, true);
  }
  if (!r.ok) {
    let detail = "";
    try {
      detail = ((await r.json()) as { erreur?: string }).erreur ?? "";
    } catch { /* corps illisible : on garde le code */ }
    throw new ErreurService(`Le service d'analyse a répondu par une erreur ${r.status}${detail ? ` : ${detail}` : "."}`, false);
  }
  return r;
}

export async function analyser(profil: Profil, demande: string, prenom: string): Promise<SortiePipeline> {
  const r = await appeler("/analyse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profil: profilPourAnalyse(profil), demande, prenom: prenom || undefined }),
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
  const q = new URLSearchParams({ symbole, tolerance, horizon: String(horizon) });
  const v = (await (await appeler(`/actif?${q}`)).json()) as VerdictActif;
  return { ...v, compatible: v.compatible ?? v.statut === "compatible" };
}
