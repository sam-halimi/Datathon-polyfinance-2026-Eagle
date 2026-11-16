"use client";

import { Chiffre, useChiffres } from "./Chiffres";
import { formaterChiffre, formaterDate } from "@/lib/format";
import type { Eventail } from "@/lib/scenarios";
import type { Part, Reference } from "@/lib/types";

// Graphiques du dossier exporté. Dessinés en SVG fixe (pas d'animation, pas de survol) pour s'imprimer
// tels qu'à l'écran : camemberts pleins, courbe de cours avec axes, éventail de scénarios.
// Toutes les valeurs viennent de la table « chiffres » ou des cours hebdomadaires de web/data/.

export const COULEURS = Array.from({ length: 8 }, (_, i) => `var(--chart-${i + 1})`);
const pct0 = new Intl.NumberFormat("fr-CA", { style: "percent", maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("fr-CA", { notation: "compact", maximumFractionDigits: 1 });
const CLAIRES = new Set(["var(--chart-2)", "var(--chart-5)", "var(--chart-6)", "var(--chart-8)"]);

/** Mention de provenance, entre parenthèses, à côté d'une donnée clé. */
export function Source({ children }: { children: React.ReactNode }) {
  return <span className="dossier__source"> (source : {children})</span>;
}

/** Provenance courte d'un chiffre : l'outil qui l'a calculé et son premier fichier de données. */
export function sourceCourte(ref: Reference | undefined): string | null {
  if (!ref) return null;
  const fichier = (ref.sources?.[0] ?? "").replace(/\s*\(.*$/, "");
  return [ref.outil.replace(/^web\/lib\/repartition\.ts.*$/, "poids du portefeuille simulé"), fichier].filter(Boolean).join(", ");
}

type Tranche = Part & { valeur: number; couleur: string };

export function tranchesDe(parts: Part[], chiffres: Record<string, Reference>): Tranche[] {
  return parts.map((p) => ({ ...p, valeur: chiffres[p.id]?.valeur ?? 0 })).filter((t) => t.valeur > 0)
    .sort((a, b) => b.valeur - a.valeur).map((t, i) => ({ ...t, couleur: t.couleur ?? COULEURS[i % COULEURS.length] }));
}

/** Camembert plein, avec sa légende alignée : pastille, libellé, valeur à droite. */
export function CamembertPlein({ titre, parts }: { titre: string; parts: Part[] }) {
  const { chiffres } = useChiffres();
  const tranches = tranchesDe(parts, chiffres);
  const total = tranches.reduce((x, t) => x + t.valeur, 0) || 1;
  const R = 96, C = 100;
  let angle = -Math.PI / 2;
  const secteurs = tranches.map((t) => {
    const a0 = angle, a1 = angle + (t.valeur / total) * 2 * Math.PI;
    angle = a1;
    const milieu = (a0 + a1) / 2;
    const p = (a: number, r: number) => `${(C + r * Math.cos(a)).toFixed(2)},${(C + r * Math.sin(a)).toFixed(2)}`;
    return {
      t, milieu,
      d: tranches.length === 1 ? null : `M${C},${C} L${p(a0, R)} A${R},${R} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${p(a1, R)} Z`,
      x: C + R * 0.62 * Math.cos(milieu), y: C + R * 0.62 * Math.sin(milieu),
    };
  });
  return (
    <figure className="dossier__camembert">
      <figcaption>{titre}</figcaption>
      {tranches.length ? (
        <svg viewBox="0 0 200 200" role="img" aria-label={`${titre} : ${tranches.map((t) => `${t.libelle} ${pct0.format(t.valeur)}`).join(", ")}`}>
          {secteurs.map(({ t, d }) => (d
            ? <path key={t.id} d={d} fill={t.couleur} stroke="var(--surface)" strokeWidth="1.5" strokeLinejoin="round" />
            : <circle key={t.id} cx={C} cy={C} r={R} fill={t.couleur} />))}
          {secteurs.map(({ t, x, y }) => (t.valeur / total >= 0.08 ? (
            <text key={t.id} x={tranches.length === 1 ? C : x} y={tranches.length === 1 ? C : y} textAnchor="middle" dominantBaseline="central"
              className={CLAIRES.has(t.couleur) ? "dossier__etiquette dossier__etiquette--sombre" : "dossier__etiquette"}>{pct0.format(t.valeur)}</text>
          ) : null))}
        </svg>
      ) : <p className="manque">Information manquante</p>}
      <ul className="dossier__legende">
        {tranches.map((t) => (
          <li key={t.id}>
            <span className="dossier__pastille" style={{ background: t.couleur }} aria-hidden="true" />
            <span className="dossier__libelle">{t.libelle}</span>
            <span className="dossier__valeur"><Chiffre id={t.id} /></span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

function graduations(min: number, max: number, n = 4): number[] {
  const brut = (max - min) / n || 1;
  const p = Math.pow(10, Math.floor(Math.log10(brut)));
  const pas = [1, 2, 2.5, 5, 10].map((k) => k * p).find((k) => k >= brut) ?? brut;
  const t: number[] = [];
  for (let v = Math.ceil(min / pas) * pas; v <= max + 1e-9; v += pas) t.push(Math.round(v * 1e6) / 1e6);
  return t;
}

/** Cours hebdomadaire d'un actif : axes gradués, baisse ombrée, sommet et creux étiquetés par un point plein. */
export function CourbeCours({ points, devise, pic, creux, retour, nom }: {
  points: [string, number][]; devise: string; pic: string | null; creux: string | null; retour?: string | null; nom: string;
}) {
  const L = 720, H = 300, m = { g: 58, d: 18, h: 34, b: 34 };
  const t = points.map(([d]) => Date.parse(d)), v = points.map(([, x]) => x);
  if (points.length < 2) return <p className="manque">Information manquante : pas de cours pour {nom}.</p>;
  const t0 = t[0], t1 = t[t.length - 1];
  const marge = (Math.max(...v) - Math.min(...v)) * 0.08 || 1;
  const v0 = Math.min(...v) - marge, v1 = Math.max(...v) + marge;
  const X = (d: number) => m.g + ((d - t0) / (t1 - t0)) * (L - m.g - m.d);
  const Y = (x: number) => m.h + (1 - (x - v0) / (v1 - v0)) * (H - m.h - m.b);
  const chemin = points.map(([d, x], i) => `${i ? "L" : "M"}${X(Date.parse(d)).toFixed(1)},${Y(x).toFixed(1)}`).join("");
  const proche = (date: string | null | undefined) => {
    if (!date) return null;
    const cible = Date.parse(date);
    let k = 0;
    t.forEach((x, i) => { if (Math.abs(x - cible) < Math.abs(t[k] - cible)) k = i; });
    return { x: X(t[k]), y: Y(v[k]), date: points[k][0], prix: v[k] };
  };
  const P = proche(pic), C = proche(creux), R = proche(retour);
  const annees = Array.from(new Set(points.map(([d]) => d.slice(0, 4)))).slice(1).map((a) => points.find(([d]) => d.slice(0, 4) === a)![0]);
  const nombre = new Intl.NumberFormat("fr-CA", { maximumFractionDigits: 2 });
  // Étiquette d'un repère : au-dessus ou au-dessous du point, ancrée à gauche ou à droite pour rester dans le cadre.
  const etiquette = (p: { x: number; y: number; date: string; prix: number }, texte: string, dessus: boolean, couleur: string) => {
    const ancre = p.x > L - 190 ? "end" : p.x < m.g + 90 ? "start" : "middle";
    const y = dessus ? Math.max(14, p.y - 12) : Math.min(H - m.b - 6, p.y + 20);
    return (
      <g>
        <circle cx={p.x} cy={p.y} r="5.5" fill={couleur} stroke="var(--surface)" strokeWidth="2" />
        <text x={p.x} y={y} textAnchor={ancre} className="dossier__repere" fill={couleur}>{texte} · {formaterDate(p.date)} · {nombre.format(p.prix)} {devise}</text>
      </g>
    );
  };
  return (
    <svg className="dossier__courbe" viewBox={`0 0 ${L} ${H}`} role="img"
      aria-label={`Cours hebdomadaire de ${nom}${P && C ? `, sommet le ${formaterDate(P.date)}, creux le ${formaterDate(C.date)}` : ""}`}>
      {graduations(v0, v1).map((g) => (
        <g key={g}>
          <line x1={m.g} x2={L - m.d} y1={Y(g)} y2={Y(g)} className="dossier__grille" />
          <text x={m.g - 8} y={Y(g)} textAnchor="end" dominantBaseline="central" className="dossier__axe">{compact.format(g)}</text>
        </g>
      ))}
      {annees.map((d) => (
        <g key={d}>
          <line x1={X(Date.parse(d))} x2={X(Date.parse(d))} y1={H - m.b} y2={H - m.b + 5} className="dossier__grille" />
          <text x={X(Date.parse(d))} y={H - m.b + 19} textAnchor="middle" className="dossier__axe">{d.slice(0, 4)}</text>
        </g>
      ))}
      <line x1={m.g} x2={L - m.d} y1={H - m.b} y2={H - m.b} className="dossier__ligne-axe" />
      {P && C ? <rect x={P.x} width={Math.max(1, C.x - P.x)} y={m.h} height={H - m.h - m.b} className="dossier__baisse" /> : null}
      <path d={chemin} className="dossier__cours" />
      {P ? etiquette(P, "Sommet", true, "var(--chart-2)") : null}
      {C ? etiquette(C, "Creux", false, "var(--danger)") : null}
      {R ? etiquette(R, "Retour au sommet", true, "var(--success)") : null}
      <text x={m.g} y={14} className="dossier__axe">Cours ajusté, en {devise}</text>
    </svg>
  );
}

/** Éventail de scénarios, en trois teintes : huit scénarios sur dix, un sur deux, médiane. */
export function EventailFixe({ ev }: { ev: Eventail }) {
  const L = 720, H = 300, m = { g: 70, d: 18, h: 18, b: 34 };
  const n = ev.annees.length - 1;
  const v0b = Math.min(...ev.p10, ev.capital ?? Infinity), v1b = Math.max(...ev.p90);
  const marge = (v1b - v0b) * 0.06 || 1;
  const v0 = v0b - marge, v1 = v1b + marge;
  const X = (i: number) => m.g + (i / n) * (L - m.g - m.d);
  const Y = (x: number) => m.h + (1 - (x - v0) / (v1 - v0)) * (H - m.h - m.b);
  const bande = (bas: number[], haut: number[]) => [...haut.map((x, i) => `${X(i).toFixed(1)},${Y(x).toFixed(1)}`),
    ...bas.map((x, i) => `${X(i).toFixed(1)},${Y(x).toFixed(1)}`).reverse()].join(" ");
  const pas = Math.max(1, Math.ceil(n / 8));
  return (
    <svg className="dossier__courbe" viewBox={`0 0 ${L} ${H}`} role="img" aria-label="Éventail de scénarios, pas une prévision">
      {graduations(v0, v1).map((g) => (
        <g key={g}>
          <line x1={m.g} x2={L - m.d} y1={Y(g)} y2={Y(g)} className="dossier__grille" />
          <text x={m.g - 8} y={Y(g)} textAnchor="end" dominantBaseline="central" className="dossier__axe">{compact.format(g)} $</text>
        </g>
      ))}
      {ev.annees.filter((a) => a % pas === 0).map((a) => (
        <text key={a} x={X(a)} y={H - m.b + 19} textAnchor="middle" className="dossier__axe">{a} an{a > 1 ? "s" : ""}</text>
      ))}
      <line x1={m.g} x2={L - m.d} y1={H - m.b} y2={H - m.b} className="dossier__ligne-axe" />
      <polygon points={bande(ev.p10, ev.p90)} fill="var(--chart-1)" fillOpacity="0.28" />
      <polygon points={bande(ev.p25, ev.p75)} fill="var(--chart-3)" fillOpacity="0.5" />
      <path d={ev.p50.map((x, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(x).toFixed(1)}`).join("")} fill="none" stroke="var(--chart-2)" strokeWidth="3" strokeLinejoin="round" />
      {ev.capital ? (
        <>
          <line x1={m.g} x2={L - m.d} y1={Y(ev.capital)} y2={Y(ev.capital)} className="dossier__capital" />
          <text x={L - m.d - 4} y={Y(ev.capital) - 6} textAnchor="end" className="dossier__axe">Capital de départ</text>
        </>
      ) : null}
    </svg>
  );
}

/** Barre de poids d'une ligne, dans le tableau des lignes. */
export function BarrePoids({ poids, couleur }: { poids: number; couleur: string }) {
  return <span className="dossier__barre" aria-hidden="true"><span style={{ width: `${Math.min(100, poids * 100)}%`, background: couleur }} /></span>;
}

export { formaterChiffre };
