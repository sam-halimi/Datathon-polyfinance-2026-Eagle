import type { Graphiques, Part, Reference, Regroupement, SortiePipeline } from "./types";

// Pour une analyse en direct (POST /analyse), les camemberts et le cours se
// calculent ici, avec les tables de web/data/univers.json (produites par
// web/scripts/graphiques.py). Mêmes règles et mêmes références que le script.

type Univers = { note: string; actifs: Record<string, { nom: string; classe: string; secteur: string; zone: string; devise: string; hebdo: [string, number][] }> };

function cle(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ']/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

export async function chargerUnivers(): Promise<Univers> {
  return (await import("../data/univers.json")).default as unknown as Univers;
}

/** Répartition par classe d'actif (champ `classe` des lignes du pipeline) :
 *  somme des poids, ajoutée à la table « chiffres » avec sa référence. */
export function ajouterClasses(sortie: SortiePipeline): SortiePipeline {
  const chiffres: Record<string, Reference> = {};
  const repartitions = { ...sortie.graphiques.repartitions };
  for (const ptf of sortie.portefeuilles) {
    const g = new Map<string, string[]>();
    for (const l of ptf.lignes) g.set(l.classe || "Inconnue", [...(g.get(l.classe || "Inconnue") ?? []), l.symbole]);
    const poids = Object.fromEntries(ptf.lignes.map((l) => [l.symbole, l.poids]));
    const somme = (ss: string[]) => ss.reduce((x, s) => x + poids[s], 0);
    const parts: Part[] = [...g.entries()]
      .map(([libelle, symboles]) => ({ libelle, symboles, id: `rep_${ptf.id.toLowerCase()}_classe_${cle(libelle)}` }))
      .sort((a, b) => somme(b.symboles) - somme(a.symboles));
    for (const p of parts) {
      chiffres[p.id] = {
        outil: "web/lib/repartition.ts (ajouterClasses)",
        parametres: { portefeuille: ptf.id, regroupement: "classe d'actif", groupe: p.libelle, poids: Object.fromEntries(p.symboles.map((s) => [s, poids[s]])) },
        periode: { debut: null, fin: null, observations: null },
        valeur: somme(p.symboles), unite: "fraction du capital", formule: "somme des poids des lignes de la classe",
        sources: [`sortie du pipeline (portefeuille ${ptf.id} : poids et classe de chaque ligne)`],
        details: { nature: "répartition du capital fictif, pas une mesure de marché", symboles: p.symboles },
      };
    }
    repartitions[ptf.id] = { ...repartitions[ptf.id], classe: parts };
  }
  return { ...sortie, graphiques: { ...sortie.graphiques, repartitions }, chiffres: { ...sortie.chiffres, ...chiffres } };
}

export async function completerGraphiques(sortie: SortiePipeline): Promise<SortiePipeline> {
  return ajouterClasses(await completerBase(sortie));
}

async function completerBase(sortie: SortiePipeline): Promise<SortiePipeline> {
  if (sortie.graphiques) return sortie;
  const u = await chargerUnivers();
  const chiffres: Record<string, Reference> = {};
  const repartitions: Graphiques["repartitions"] = {};
  for (const ptf of sortie.portefeuilles) {
    const poids = Object.fromEntries(ptf.lignes.map((l) => [l.symbole, l.poids]));
    const groupes: Record<Exclude<Regroupement, "classe">, (s: string) => string> = {
      actif: (s) => s, secteur: (s) => u.actifs[s]?.secteur ?? "Inconnu", zone: (s) => u.actifs[s]?.zone ?? "Inconnue",
    };
    repartitions[ptf.id] = { actif: [], classe: [], secteur: [], zone: [] };
    for (const r of ["actif", "secteur", "zone"] as Regroupement[]) {
      const g = new Map<string, string[]>();
      for (const l of [...ptf.lignes].sort((a, b) => b.poids - a.poids)) {
        const k = groupes[r as Exclude<Regroupement, "classe">](l.symbole);
        g.set(k, [...(g.get(k) ?? []), l.symbole]);
      }
      const parts: Part[] = [...g.entries()]
        .map(([libelle, symboles]) => ({ libelle, symboles, id: `rep_${ptf.id.toLowerCase()}_${r}_${cle(libelle)}` }))
        .sort((a, b) => b.symboles.reduce((x, s) => x + poids[s], 0) - a.symboles.reduce((x, s) => x + poids[s], 0));
      for (const p of parts) {
        chiffres[p.id] = {
          outil: "web/lib/repartition.ts (repartition)",
          parametres: { portefeuille: ptf.id, regroupement: r, groupe: p.libelle, poids: Object.fromEntries(p.symboles.map((s) => [s, poids[s]])) },
          periode: { debut: null, fin: null, observations: null },
          valeur: p.symboles.reduce((x, s) => x + poids[s], 0),
          unite: "fraction du capital",
          formule: "somme des poids des lignes du groupe",
          sources: [`réponse de POST /analyse (portefeuille ${ptf.id}, poids)`, "data/assets_universe.csv (sector, market), via web/data/univers.json"],
          details: { nature: "répartition du capital fictif, pas une mesure de marché", symboles: p.symboles },
        };
      }
      repartitions[ptf.id][r] = parts;
    }
  }
  // Actif commenté : celui de la demande, sinon la ligne la plus volatile du portefeuille retenu.
  const retenu = sortie.portefeuilles.find((p) => p.id === sortie.gouvernance.portefeuille_retenu) ?? sortie.portefeuilles[0];
  const vol = (s: string) => sortie.chiffres[retenu.volatilites[s]]?.valeur ?? 0;
  const cible = sortie.demande_analysee?.symboles?.[0]?.symbole
    ?? [...retenu.lignes].sort((a, b) => vol(b.symbole) - vol(a.symbole))[0]?.symbole;
  const id = cle(cible ?? "");
  const pb = sortie.chiffres[`pb_${id}`];
  const a = cible ? u.actifs[cible] : undefined;
  const cours = a && pb
    ? {
      symbole: cible!, id, nom: a.nom, devise: a.devise, points: a.hebdo,
      date_pic: String(pb.details.date_pic), date_creux: String(pb.details.date_creux), reference: `pb_${id}`,
      sources: ["data/prices_daily.csv (adj_close, dernier cours de chaque semaine), via web/data/univers.json"],
    }
    : null;
  const graphiques = { note: u.note, repartitions, cours, chiffres } as unknown as Graphiques;
  return { ...sortie, graphiques, chiffres: { ...sortie.chiffres, ...chiffres } };
}
