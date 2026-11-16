import type { Graphiques, Part, Reference, Regroupement, SortiePipeline } from "./types";

// Pour une analyse en direct (POST /analyse), les camemberts et le cours se
// calculent ici, avec les tables de web/data/univers.json (produites par
// web/scripts/graphiques.py). Mêmes règles et mêmes références que le script.

type Univers = { note: string; actifs: Record<string, { nom: string; classe: string; secteur: string; zone: string; devise: string; source?: string; hebdo: [string, number][] }> };

function cle(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ']/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

export async function chargerUnivers(): Promise<Univers> {
  return (await import("../data/univers.json")).default as unknown as Univers;
}

// Charte Eagle (docs/da-eagle.md, « Graphiques ») : correspondance fixe des classes d'actif
// et des régions avec les couleurs chart-1 à chart-8.
export const CLASSES_DA: Record<string, { libelle: string; couleur: string }> = {
  equity: { libelle: "Actions", couleur: "var(--chart-1)" },
  etf_equity: { libelle: "Actions", couleur: "var(--chart-1)" },
  etf_commodity: { libelle: "Or", couleur: "var(--chart-2)" },
  immobilier: { libelle: "Immobilier", couleur: "var(--chart-3)" },
  etf_bond: { libelle: "Obligations", couleur: "var(--chart-4)" },
  crypto: { libelle: "Crypto-actifs", couleur: "var(--chart-5)" },
  liquidites: { libelle: "Liquidités", couleur: "var(--chart-8)" },
};

export const REGIONS_DA: Record<string, { libelle: string; couleur: string }> = {
  "amerique-du-nord": { libelle: "Amérique du Nord", couleur: "var(--chart-1)" },
  "amerique-latine": { libelle: "Amérique latine", couleur: "var(--chart-3)" },
  europe: { libelle: "Europe", couleur: "var(--chart-2)" },
  "afrique-moyen-orient": { libelle: "Afrique et Moyen-Orient", couleur: "var(--chart-4)" },
  asie: { libelle: "Asie", couleur: "var(--chart-6)" },
  oceanie: { libelle: "Océanie", couleur: "var(--chart-5)" },
};

/** Zone de web/data/univers.json (pays de cotation) -> région de la carte. Les zones sans
 *  pays (or, crypto) restent hors carte et sont listées à part. */
const REGION_DE_ZONE: Record<string, string> = {
  Canada: "amerique-du-nord", "États-Unis": "amerique-du-nord", Mexique: "amerique-du-nord",
  Brésil: "amerique-latine", Europe: "europe", France: "europe", Allemagne: "europe", "Royaume-Uni": "europe",
  Suisse: "europe", "Pays-Bas": "europe", Japon: "asie", Chine: "asie", Corée: "asie", Taïwan: "asie", Inde: "asie",
  "Hong Kong": "asie", Australie: "oceanie",
};

function chiffreRepartition(ptf: string, regroupement: string, libelle: string, poids: Record<string, number>,
  symboles: string[], outil: string, source: string): Reference {
  return {
    outil: `web/lib/repartition.ts (${outil})`,
    parametres: { portefeuille: ptf, regroupement, groupe: libelle, poids: Object.fromEntries(symboles.map((s) => [s, poids[s]])) },
    periode: { debut: null, fin: null, observations: null },
    valeur: symboles.reduce((x, s) => x + poids[s], 0), unite: "fraction du capital", formule: "somme des poids des lignes du groupe",
    sources: [source],
    details: { nature: "répartition du capital fictif, pas une mesure de marché", symboles },
  };
}

/** Répartition par classe d'actif, regroupée comme dans la charte (Actions = actions et FNB
 *  d'actions), et par région de la carte du monde. Chiffres ajoutés avec leur référence. */
export function ajouterClasses(sortie: SortiePipeline): SortiePipeline {
  const chiffres: Record<string, Reference> = {};
  const repartitions = { ...sortie.graphiques.repartitions };
  for (const ptf of sortie.portefeuilles) {
    const poids = Object.fromEntries(ptf.lignes.map((l) => [l.symbole, l.poids]));
    const somme = (ss: string[]) => ss.reduce((x, s) => x + poids[s], 0);

    const g = new Map<string, string[]>();
    for (const l of ptf.lignes) {
      const k = CLASSES_DA[l.classe_code] ? l.classe_code.replace("etf_equity", "equity") : `autre:${l.classe || "Inconnue"}`;
      g.set(k, [...(g.get(k) ?? []), l.symbole]);
    }
    const classes: Part[] = [...g.entries()].map(([k, symboles]) => {
      const da = CLASSES_DA[k];
      const libelle = da?.libelle ?? k.slice("autre:".length);
      return { libelle, symboles, couleur: da?.couleur ?? "var(--chart-7)", id: `rep_${ptf.id.toLowerCase()}_classe_${cle(libelle)}` };
    }).sort((a, b) => somme(b.symboles) - somme(a.symboles));
    for (const p of classes) {
      chiffres[p.id] = chiffreRepartition(ptf.id, "classe d'actif", p.libelle, poids, p.symboles, "ajouterClasses",
        `sortie du pipeline (portefeuille ${ptf.id} : poids et classe de chaque ligne)`);
    }

    const zones = repartitions[ptf.id]?.zone ?? [];
    const r = new Map<string, string[]>();
    const horsCarte: Part[] = [];
    for (const z of zones) {
      const region = REGION_DE_ZONE[z.libelle];
      if (region) r.set(region, [...(r.get(region) ?? []), ...z.symboles]);
      else horsCarte.push({ ...z, couleur: "var(--region-vide)" });
    }
    const regions: Part[] = [...r.entries()].map(([region, symboles]) => ({
      libelle: REGIONS_DA[region].libelle, symboles, region, couleur: REGIONS_DA[region].couleur,
      id: `rep_${ptf.id.toLowerCase()}_region_${cle(region)}`,
    })).sort((a, b) => somme(b.symboles) - somme(a.symboles));
    for (const p of regions) {
      chiffres[p.id] = chiffreRepartition(ptf.id, "région", p.libelle, poids, p.symboles, "ajouterClasses",
        "zone de cotation de chaque ligne (data/assets_universe.csv, colonne market, via web/data/univers.json)");
    }
    repartitions[ptf.id] = { ...repartitions[ptf.id], classe: classes, region: [...regions, ...horsCarte] };
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
    const groupes: Record<Exclude<Regroupement, "classe" | "region">, (s: string) => string> = {
      actif: (s) => s, secteur: (s) => u.actifs[s]?.secteur ?? "Inconnu", zone: (s) => u.actifs[s]?.zone ?? "Inconnue",
    };
    repartitions[ptf.id] = { actif: [], classe: [], secteur: [], zone: [], region: [] };
    for (const r of ["actif", "secteur", "zone"] as Regroupement[]) {
      const g = new Map<string, string[]>();
      for (const l of [...ptf.lignes].sort((a, b) => b.poids - a.poids)) {
        const k = groupes[r as Exclude<Regroupement, "classe" | "region">](l.symbole);
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
