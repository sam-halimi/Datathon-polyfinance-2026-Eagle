import amira from "../../tests/scenarios/amira.json";
import mateo from "../../tests/scenarios/mateo.json";
import robert from "../../tests/scenarios/robert.json";
import type { SortiePipeline } from "./types";

// Les trois personas des tests d'acceptation (tests/scenarios/). L'écran de
// choix lit ces fiches, légères ; la sortie du pipeline du persona choisi
// (agents/sorties/<id>.json) n'est chargée qu'au moment du choix.

export type Persona = {
  id: "robert" | "amira" | "mateo";
  nom: string;
  age: number;
  description: string;
  demande: string;
  tolerance: string;
  horizon: number;
  /** Comment l'accueil a traduit ses réponses (écrit par l'équipe, pas par un modèle). */
  choix: string[];
};

type Scenario = {
  id: string;
  persona: { nom: string; age: number; description: string };
  profil: { tolerance_risque: string; horizon_annees: number };
  choix_de_l_accueil?: string[];
  demande: string;
};

function persona(s: Scenario): Persona {
  return {
    id: s.id as Persona["id"],
    nom: s.persona.nom,
    age: s.persona.age,
    description: s.persona.description,
    demande: s.demande,
    tolerance: s.profil.tolerance_risque,
    horizon: s.profil.horizon_annees,
    choix: s.choix_de_l_accueil ?? [],
  };
}

export const PERSONAS: Persona[] = [robert, amira, mateo].map(persona);

const CHARGEURS: Record<Persona["id"], () => Promise<{ default: unknown }>> = {
  robert: () => import("../../agents/sorties/robert.json"),
  amira: () => import("../../agents/sorties/amira.json"),
  mateo: () => import("../../agents/sorties/mateo.json"),
};

/** Charge la sortie du pipeline d'un persona. */
export async function chargerSortie(id: Persona["id"]): Promise<SortiePipeline> {
  const m = await CHARGEURS[id]();
  return m.default as SortiePipeline;
}
