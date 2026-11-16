import amira from "../../tests/scenarios/amira.json";
import mateo from "../../tests/scenarios/mateo.json";
import robert from "../../tests/scenarios/robert.json";
import type { Graphiques, SortiePipeline } from "./types";

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

const GRAPHIQUES: Record<Persona["id"], () => Promise<{ default: unknown }>> = {
  robert: () => import("../data/graphiques/robert.json"),
  amira: () => import("../data/graphiques/amira.json"),
  mateo: () => import("../data/graphiques/mateo.json"),
};

/** Clé du stockage local où l'écran dépose l'analyse en cours pour le dossier imprimable. */
export const CLE_DOSSIER = "eagle:dossier";

export function estPersona(id: string | null): id is Persona["id"] {
  return id === "robert" || id === "amira" || id === "mateo";
}

/** Charge la sortie du pipeline d'un persona et les données de ses graphiques.
 *  Les parts des camemberts rejoignent la table « chiffres ». */
export async function chargerSortie(id: Persona["id"]): Promise<SortiePipeline> {
  const [m, g] = await Promise.all([CHARGEURS[id](), GRAPHIQUES[id]()]);
  const sortie = m.default as Omit<SortiePipeline, "graphiques">;
  const { scenarios, ...graphiques } = g.default as Graphiques & { scenarios?: SortiePipeline["scenarios"] };
  // L'éventail de scénarios du portefeuille retenu est calculé avec les graphiques
  // (tools.scenarios.eventail_scenarios) : la démonstration l'affiche sans serveur.
  return { ...sortie, graphiques: graphiques as Graphiques, scenarios: sortie.scenarios ?? scenarios ?? undefined,
    chiffres: { ...sortie.chiffres, ...graphiques.chiffres } };
}
