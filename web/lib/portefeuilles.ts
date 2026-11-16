import type { SortiePipeline } from "./types";

// « Autre proposition » : le pipeline propose deux ou trois portefeuilles simulés, tous vérifiés par la
// gouvernance, et en retient un. La personne peut demander à voir les autres. Rien n'est recalculé ici :
// chaque proposition a déjà ses lignes, ses mesures, ses contrôles, son adéquation et son éventail.

/** La même sortie, vue sur la proposition `id`. Les écrans lisent alors ses contrôles et son éventail. */
export function vueSur(s: SortiePipeline, id: string): SortiePipeline {
  const retenu = s.vue?.retenu ?? s.gouvernance.portefeuille_retenu;
  const ptf = s.portefeuilles.find((p) => p.id === id);
  if (!ptf || id === retenu) return s.vue ? { ...s, vue: undefined } : s;
  return {
    ...s,
    gouvernance: { ...s.gouvernance, portefeuille_retenu: id, controles: ptf.controles ?? [] },
    scenarios: s.scenarios_par_portefeuille?.[id],
    vue: { retenu },
  };
}

/** Propositions acceptées par la gouvernance, la retenue en tête. */
export function propositions(s: SortiePipeline): string[] {
  const retenu = s.vue?.retenu ?? s.gouvernance.portefeuille_retenu;
  const acceptees = s.portefeuilles.map((p) => p.id).filter((id) => id !== retenu);
  return [retenu, ...acceptees];
}

const LIBELLES: Record<string, string> = {
  max_titre_individuel: "Une action seule", max_crypto: "Cryptoactifs", max_part_risquee: "Part risquée (actions, FNB d'actions, crypto)",
  max_un_secteur: "Un même secteur, en actions détenues en direct", plafond_theme: "Thèmes d'intérêt, au total",
};

/** Ce que le profil impose : chaque plafond, la réponse qui l'a fixé, et le repère {id} de son chiffre. */
export function contraintesDuProfil(s: SortiePipeline): { libelle: string; texte: string }[] {
  const c = s.contraintes;
  if (!c) return [];
  const lignes = Object.entries(LIBELLES).filter(([k]) => c.limites[k] !== undefined).map(([k, libelle]) => ({
    libelle,
    texte: `au plus ${s.chiffres[`lim_${k}`] ? `{lim_${k}}` : `${Math.round(c.limites[k] * 1000) / 10} %`} du capital${c.origine[k] ? `, parce que : ${c.origine[k]}` : ""}.`,
  }));
  if (c.limites.min_lignes) lignes.push({ libelle: "Diversification", texte: `au moins ${c.limites.min_lignes} lignes${c.origine.min_lignes ? `, parce que : ${c.origine.min_lignes}` : ""}.` });
  if (s.chiffres.seuil_volatilite) lignes.push({ libelle: "Variation annuelle du portefeuille", texte: "au plus {seuil_volatilite}, d'après votre tolérance au risque." });
  if (s.chiffres.seuil_pire_baisse) lignes.push({ libelle: "Pire baisse passée du portefeuille", texte: "pas au-delà de {seuil_pire_baisse}, d'après votre tolérance au risque." });
  for (const x of c.exclusions ?? []) lignes.push({ libelle: "Exclusion", texte: `« ${x} », à votre demande.` });
  return lignes;
}

/** Phrase de comparaison d'une autre proposition avec celle retenue, avec repères {id}. */
export function ecarts(s: SortiePipeline, id: string): string[] {
  const retenu = s.portefeuilles.find((p) => p.id === (s.vue?.retenu ?? s.gouvernance.portefeuille_retenu));
  const autre = s.portefeuilles.find((p) => p.id === id);
  if (!retenu || !autre || retenu.id === autre.id) return [];
  const a = new Map(retenu.lignes.map((l) => [l.symbole, l.poids])), b = new Map(autre.lignes.map((l) => [l.symbole, l.poids]));
  const pc = (x: number) => `${Math.round(x * 100)} %`;
  const ajoutees = [...b.keys()].filter((k) => !a.has(k)), retirees = [...a.keys()].filter((k) => !b.has(k));
  const changees = [...b.keys()].filter((k) => a.has(k) && Math.abs((a.get(k) ?? 0) - (b.get(k) ?? 0)) > 0.0049);
  return [
    `Variation annuelle : {${autre.volatilite}} pour la proposition ${autre.id}, {${retenu.volatilite}} pour la proposition ${retenu.id} retenue.`,
    `Pire baisse passée : {${autre.pire_baisse}} pour ${autre.id}, {${retenu.pire_baisse}} pour ${retenu.id}.`,
    ...(ajoutees.length ? [`Lignes ajoutées : ${ajoutees.map((k) => `${k} (${pc(b.get(k) ?? 0)})`).join(", ")}.`] : []),
    ...(retirees.length ? [`Lignes retirées : ${retirees.map((k) => `${k} (${pc(a.get(k) ?? 0)})`).join(", ")}.`] : []),
    ...(changees.length ? [`Poids modifiés : ${changees.map((k) => `${k} ${pc(a.get(k) ?? 0)} → ${pc(b.get(k) ?? 0)}`).join(", ")}.`] : []),
  ];
}
