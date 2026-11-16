import type { Reference, SortiePipeline } from "./types";

// L'éventail de scénarios renvoyé par le serveur (tools.scenarios.eventail_scenarios,
// voir docs/api-eagle.md) : une référence d'appel dont la valeur contient les
// années et cinq centiles. Les chiffres montrés (médiane, bornes à l'horizon)
// deviennent des entrées de la table « chiffres », avec la même référence.

export type Eventail = {
  annees: number[];
  p10: number[]; p25: number[]; p50: number[]; p75: number[]; p90: number[];
  devise: string;
  capital: number | null;
  hypotheses: string[];
  avertissement: string | null;
  formule: string;
  chiffres: Record<string, Reference>;
};

type Brut = Reference & { valeur: unknown };

export function lireEventail(s: SortiePipeline): Eventail | null {
  const sc = s.scenarios as unknown as Brut | undefined | null;
  const v = sc?.valeur as Record<string, number[]> | undefined;
  if (!sc || !v || !Array.isArray(v.annees) || !Array.isArray(v.p50)) return null;
  const n = v.annees.length - 1;
  const params = (sc.parametres ?? {}) as Record<string, unknown>;
  const devise = String(params.devise ?? s.profil?.devise ?? "CAD");
  const d = (sc.details ?? {}) as Record<string, unknown>;
  const base = { outil: sc.outil, parametres: sc.parametres, periode: sc.periode, formule: sc.formule, sources: sc.sources,
    formule_en: (sc as { formule_en?: string }).formule_en };
  const chiffre = (champ: string, valeur: number, unite: string, decrit: string): Reference => ({
    ...base, valeur, unite, champ, details: { avertissement: d.avertissement, nature: decrit },
  });
  const montant = `montant en ${devise}`;
  const chiffres: Record<string, Reference> = {
    scen_p50_fin: chiffre("p50", v.p50[n], montant, `médiane des scénarios à ${v.annees[n]} ans`),
    scen_p10_fin: chiffre("p10", v.p10[n], montant, `10e centile des scénarios à ${v.annees[n]} ans`),
    scen_p90_fin: chiffre("p90", v.p90[n], montant, `90e centile des scénarios à ${v.annees[n]} ans`),
  };
  if (typeof d.part_des_scenarios_sous_le_capital === "number") {
    chiffres.scen_sous_capital = chiffre("part_des_scenarios_sous_le_capital", d.part_des_scenarios_sous_le_capital,
      "fraction des scénarios", "part des scénarios qui finissent sous le capital de départ");
  }
  return {
    annees: v.annees, p10: v.p10, p25: v.p25, p50: v.p50, p75: v.p75, p90: v.p90, devise,
    capital: typeof params.capital === "number" ? params.capital : null,
    hypotheses: Array.isArray(d.hypotheses) ? (d.hypotheses as string[]) : [],
    avertissement: typeof d.avertissement === "string" ? d.avertissement : null,
    formule: sc.formule, chiffres,
  };
}
