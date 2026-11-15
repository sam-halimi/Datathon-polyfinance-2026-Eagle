import { profilPourAnalyse } from "./questions";
import type { Profil, SortiePipeline } from "./types";

// Le service du pipeline (agents/) : POST /analyse et GET /actif.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function analyser(profil: Profil, demande: string, prenom: string): Promise<SortiePipeline> {
  const r = await fetch(`${API}/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profil: profilPourAnalyse(profil), demande, prenom }),
  });
  if (!r.ok) throw new Error(`POST /analyse : ${r.status}`);
  return r.json();
}

/** Réponse de GET /actif : verdict, textes avec repères {id} et leurs chiffres. */
export type VerdictActif = {
  symbole: string;
  compatible?: boolean;
  verdict?: string;
  raisons?: string[];
  explication?: string | string[];
  chiffres?: SortiePipeline["chiffres"];
  [cle: string]: unknown;
};

export async function verifierActif(symbole: string, tolerance: string, horizon: number): Promise<VerdictActif> {
  const q = new URLSearchParams({ symbole, tolerance, horizon: String(horizon) });
  const r = await fetch(`${API}/actif?${q}`);
  if (!r.ok) throw new Error(`GET /actif : ${r.status}`);
  return r.json();
}

export const ADRESSE_API = API;
