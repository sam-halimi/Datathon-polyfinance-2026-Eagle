"use client";

import { Chiffre, Texte, useChiffres } from "./Chiffres";
import { formaterDate } from "@/lib/format";
import type { Part, SortiePipeline } from "@/lib/types";

// Les graphiques : camemberts de répartition et cours de l'actif visé.
// Leurs valeurs viennent de web/data/graphiques/ (web/scripts/graphiques.py).

export const PALETTE = [
  "var(--serie-1)", "var(--serie-2)", "var(--serie-3)", "var(--serie-4)",
  "var(--serie-5)", "var(--serie-6)", "var(--serie-7)", "var(--serie-8)",
];

/** Un anneau dont chaque arc est une part. Jamais la couleur seule : la
 *  légende donne toujours le nom et le pourcentage. */
export function Camembert({ parts, taille = 92, libelle }: { parts: Part[]; taille?: number; libelle: string }) {
  const { chiffres } = useChiffres();
  const r = 15.9155; // circonférence de 100
  let debut = 0;
  return (
    <svg className="camembert" width={taille} height={taille} viewBox="0 0 42 42" role="img" aria-label={libelle}>
      <circle cx="21" cy="21" r={r} fill="none" stroke="var(--trait)" strokeWidth="9" />
      {parts.map((p, i) => {
        const v = Math.max(0, (chiffres[p.id]?.valeur ?? 0) * 100);
        const arc = (
          <circle key={p.id} cx="21" cy="21" r={r} fill="none" stroke={PALETTE[i % PALETTE.length]} strokeWidth="9"
            strokeDasharray={`${v} ${100 - v}`} strokeDashoffset={25 - debut} />
        );
        debut += v;
        return arc;
      })}
    </svg>
  );
}

export function Legende({ parts }: { parts: Part[] }) {
  return (
    <ul className="legende-parts">
      {parts.map((p, i) => (
        <li key={p.id}>
          <span className="ligne__pastille" style={{ background: PALETTE[i % PALETTE.length] }} aria-hidden="true" />
          <span className="legende-parts__nom">{p.libelle}</span>
          <Chiffre id={p.id} />
        </li>
      ))}
    </ul>
  );
}

/** Cours hebdomadaire de l'actif visé, avec son sommet et son creux. */
export function Cours({ sortie, hauteur = 150 }: { sortie: SortiePipeline; hauteur?: number }) {
  const c = sortie.graphiques.cours;
  const L = 340, H = hauteur, m = { h: 22, b: 18, g: 4, d: 4 };
  const t = c.points.map(([d]) => Date.parse(d));
  const v = c.points.map(([, x]) => x);
  const t0 = Math.min(...t), t1 = Math.max(...t), v0 = Math.min(...v), v1 = Math.max(...v);
  const X = (d: number) => m.g + ((d - t0) / (t1 - t0)) * (L - m.g - m.d);
  const Y = (x: number) => m.h + (1 - (x - v0) / (v1 - v0)) * (H - m.h - m.b);
  const chemin = c.points.map(([d, x], i) => `${i ? "L" : "M"}${X(Date.parse(d)).toFixed(1)},${Y(x).toFixed(1)}`).join("");
  // Le point le plus proche de la date (les cours sont hebdomadaires).
  const point = (date: string) => {
    const cible = Date.parse(date);
    let k = -1;
    t.forEach((x, i) => { if (k < 0 || Math.abs(x - cible) < Math.abs(t[k] - cible)) k = i; });
    return k < 0 ? null : { x: X(t[k]), y: Y(c.points[k][1]) };
  };
  const pic = point(c.date_pic), creux = point(c.date_creux);
  const annees = Array.from(new Set(c.points.map(([d]) => d.slice(0, 4)))).slice(1);
  return (
    <svg className="cours" viewBox={`0 0 ${L} ${H}`} role="img"
      aria-label={`Cours hebdomadaire de ${c.nom}, sommet le ${formaterDate(c.date_pic)}, creux le ${formaterDate(c.date_creux)}`}>
      {annees.map((a) => {
        const x = X(Date.parse(`${a}-01-01`));
        return (
          <g key={a}>
            <line x1={x} x2={x} y1={m.h - 6} y2={H - m.b} className="cours__grille" />
            <text x={x + 2} y={H - 4} className="cours__axe">{a}</text>
          </g>
        );
      })}
      {pic && creux ? (
        <rect x={pic.x} width={Math.max(1, creux.x - pic.x)} y={m.h - 6} height={H - m.b - m.h + 6} className="cours__baisse" />
      ) : null}
      <path d={chemin} className="cours__ligne" />
      {pic ? (
        <g>
          <circle cx={pic.x} cy={pic.y} r="4" className="cours__sommet" />
          <text x={pic.x + 6} y={Math.max(12, pic.y - 4)} className="cours__marque">▲ sommet</text>
        </g>
      ) : null}
      {creux ? (
        <g>
          <circle cx={creux.x} cy={creux.y} r="4" className="cours__creux" />
          <text x={creux.x + 6} y={Math.min(H - m.b - 2, creux.y + 14)} className="cours__marque">▼ creux</text>
        </g>
      ) : null}
    </svg>
  );
}

/** Les marques et la phrase sous le graphique : dates de la référence
 *  pire_baisse, chiffres par repères. */
export function LegendeCours({ sortie }: { sortie: SortiePipeline }) {
  const c = sortie.graphiques.cours;
  return (
    <p className="cours__legende">
      ▲ Sommet : {formaterDate(c.date_pic)} · ▼ Creux : {formaterDate(c.date_creux)} · Baisse : <Chiffre id={c.reference} />
    </p>
  );
}

export function phraseCours(sortie: SortiePipeline): string {
  const c = sortie.graphiques.cours;
  const ch = sortie.chiffres;
  let t = `Sur la fenêtre, ${c.nom} (${c.symbole}) a perdu {${c.reference}} entre son sommet du ${formaterDate(c.date_pic)} et son creux du ${formaterDate(c.date_creux)}.`;
  if (ch[`rattrapage_${c.id}`]) t += ` Pour revenir au sommet, il faudrait un gain de {rattrapage_${c.id}}.`;
  if (ch[`vol_${c.id}`]) t += ` Variation typique par an : {vol_${c.id}}.`;
  return t;
}

export function PhraseCours({ sortie }: { sortie: SortiePipeline }) {
  return <p className="cours__phrase"><Texte>{phraseCours(sortie)}</Texte></p>;
}

export function SourceCours({ sortie }: { sortie: SortiePipeline }) {
  const c = sortie.graphiques.cours;
  return <p className="cours__source">Cours ajusté hebdomadaire, en {c.devise} · {c.sources.join(", ")}. Le passé ne promet rien.</p>;
}
