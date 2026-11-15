"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area, CartesianGrid, Cell, ComposedChart, Line, LineChart, Pie, PieChart, ReferenceArea, ReferenceDot, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Chiffre, Texte, useChiffres } from "./Chiffres";
import { formaterChiffre, formaterDate, formaterMontant } from "@/lib/format";
import { chargerUnivers } from "@/lib/repartition";
import type { Eventail } from "@/lib/scenarios";
import type { Part, Portefeuille, SortiePipeline } from "@/lib/types";

// Les graphiques de la présentation, avec Recharts. Toutes les valeurs viennent
// de la sortie du pipeline (poids, chiffres de tools/) ou des prix de
// data/prices_daily.csv relus par web/scripts/graphiques.py (web/data/univers.json).
// Couleurs : palette catégorielle validée (variables --serie-1 à 8), dans un ordre fixe.

export const SERIES = Array.from({ length: 8 }, (_, i) => `var(--serie-${i + 1})`);

const pct = new Intl.NumberFormat("fr-CA", { style: "percent", maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("fr-CA", { notation: "compact", maximumFractionDigits: 1 });

function cle(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ']/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

// ---------- Anneaux de répartition ----------

type Tranche = Part & { valeur: number; couleur: string };

const RADIAN = Math.PI / 180;
/** Étiquette directe, dans l'anneau, pour les parts d'au moins 12 % (la légende porte les autres). */
function etiquette(props: { cx?: number; cy?: number; midAngle?: number; innerRadius?: number; outerRadius?: number; percent?: number; value?: number; fill?: string }) {
  const { cx = 0, cy = 0, midAngle = 0, innerRadius = 0, outerRadius = 0, value = 0, fill } = props;
  if (value < 0.12) return null;
  const r = (innerRadius + outerRadius) / 2;
  return (
    <text x={cx + r * Math.cos(-midAngle * RADIAN)} y={cy + r * Math.sin(-midAngle * RADIAN)} className="anneau__etiquette"
      textAnchor="middle" dominantBaseline="central" pointerEvents="none"
      style={fill === "var(--serie-4)" ? { fill: "#0b0b0b" } : undefined}>{pct.format(value)}</text>
  );
}

export function Anneau({ titre, parts }: { titre: string; parts: Part[] }) {
  const { chiffres } = useChiffres();
  const [actif, setActif] = useState<string | null>(null);
  // La couleur suit l'entité dans l'ordre reçu (le pipeline trie déjà par poids) ;
  // la légende est triée par valeur décroissante.
  const tranches: Tranche[] = parts
    .map((p, i) => ({ ...p, valeur: chiffres[p.id]?.valeur ?? 0, couleur: SERIES[i % SERIES.length] }))
    .filter((t) => t.valeur > 0);
  const legende = [...tranches].sort((a, b) => b.valeur - a.valeur);
  const survol = tranches.find((t) => t.id === actif);
  if (!tranches.length) return <figure className="anneau"><figcaption>{titre}</figcaption><p className="manque">Information manquante</p></figure>;
  return (
    <figure className="anneau" onMouseLeave={() => setActif(null)}>
      <figcaption>{titre}</figcaption>
      <div className="anneau__graphique">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={tranches} dataKey="valeur" nameKey="libelle" innerRadius="60%" outerRadius="84%" startAngle={90} endAngle={-270}
              paddingAngle={tranches.length > 1 ? 1.5 : 0} stroke="var(--surface)" strokeWidth={2} isAnimationActive
              animationDuration={600} onMouseEnter={(_, i) => setActif(tranches[i]?.id ?? null)}
              labelLine={false} label={etiquette}>
              {tranches.map((t) => (
                <Cell key={t.id} fill={t.couleur} className="anneau__part"
                  opacity={actif && actif !== t.id ? 0.28 : 1} />
              ))}
            </Pie>
            <Tooltip content={() => null} />
          </PieChart>
        </ResponsiveContainer>
        <div className="anneau__centre" aria-hidden="true">
          {survol ? (
            <>
              <strong>{formaterChiffre(chiffres[survol.id])}</strong>
              <span>{survol.libelle}</span>
            </>
          ) : (
            <>
              <strong>{legende[0] ? pct.format(legende[0].valeur) : ""}</strong>
              <span>{legende[0]?.libelle}</span>
            </>
          )}
        </div>
      </div>
      <ul className="anneau__legende">
        {legende.map((t) => (
          <li key={t.id} className={actif === t.id ? "anneau__entree anneau__entree--actif" : actif ? "anneau__entree anneau__entree--terne" : "anneau__entree"}
            onMouseEnter={() => setActif(t.id)} onFocus={() => setActif(t.id)}
            title={t.symboles.length > 1 || t.symboles[0] !== t.libelle ? t.symboles.join(", ") : undefined}>
            <span className="anneau__pastille" style={{ background: t.couleur }} aria-hidden="true" />
            <span className="anneau__nom">{t.libelle}</span>
            <Chiffre id={t.id} />
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function TroisAnneaux({ s, ptf }: { s: SortiePipeline; ptf: Portefeuille }) {
  const reps = s.graphiques?.repartitions?.[ptf.id];
  if (!reps) return <p className="diapo__manque">Information manquante : pas de répartition calculée pour ce portefeuille.</p>;
  return (
    <div className="anneaux">
      <Anneau titre="Par classe d'actif" parts={reps.classe ?? []} />
      <Anneau titre="Par secteur" parts={reps.secteur ?? []} />
      <Anneau titre="Par zone géographique" parts={reps.zone ?? []} />
    </div>
  );
}

// ---------- Cours commentés ----------

type Univers = Awaited<ReturnType<typeof chargerUnivers>>["actifs"];

function idPb(s: SortiePipeline, ptf: Portefeuille, symbole: string): string | null {
  const id = ptf.pires_baisses?.[symbole] ?? `pb_${cle(symbole)}`;
  return s.chiffres[id] ? id : null;
}

function dates(s: SortiePipeline, id: string | null) {
  const d = (id ? s.chiffres[id]?.details : null) ?? {};
  return {
    pic: typeof d.date_pic === "string" ? d.date_pic : null,
    creux: typeof d.date_creux === "string" ? d.date_creux : null,
    retour: typeof d.date_retour === "string" ? d.date_retour : null,
  };
}

/** Le point hebdomadaire le plus proche d'une date. */
function proche(points: { date: string; prix: number }[], date: string | null) {
  if (!date) return null;
  const t = Date.parse(date);
  return points.reduce((a, b) => (Math.abs(Date.parse(b.date) - t) < Math.abs(Date.parse(a.date) - t) ? b : a), points[0]);
}

export function CoursCommentes({ s, ptf }: { s: SortiePipeline; ptf: Portefeuille }) {
  const [univers, setUnivers] = useState<Univers | null>(null);
  useEffect(() => { chargerUnivers().then((u) => setUnivers(u.actifs)); }, []);
  const demande = s.graphiques?.cours?.symbole ?? s.demande_analysee?.symboles?.[0]?.symbole;
  const symboles = useMemo(() => Array.from(new Set([...(demande ? [demande] : []), ...ptf.lignes.map((l) => l.symbole)])), [demande, ptf]);
  const [choix, setChoix] = useState(symboles[0]);
  const symbole = symboles.includes(choix) ? choix : symboles[0];
  const actif = univers?.[symbole];
  const pb = idPb(s, ptf, symbole);
  const d = dates(s, pb);
  const points = useMemo(() => (actif?.hebdo ?? []).map(([date, prix]) => ({ date, prix })), [actif]);
  const pic = proche(points, d.pic), creux = proche(points, d.creux);
  const vol = ptf.volatilites?.[symbole] ?? (s.chiffres[`vol_${cle(symbole)}`] ? `vol_${cle(symbole)}` : null);
  const ratt = s.chiffres[`rattrapage_${cle(symbole)}`] ? `rattrapage_${cle(symbole)}` : null;
  const annees = Array.from(new Set(points.map((p) => p.date.slice(0, 4)))).slice(1).map((a) => proche(points, `${a}-01-01`)!.date);

  return (
    <div className="cours-commentes">
      <div className="fiches-lignes__onglets" role="tablist" aria-label="Actif affiché">
        {symboles.map((x) => (
          <button key={x} type="button" role="tab" aria-selected={x === symbole} onClick={() => setChoix(x)}
            className={x === symbole ? "onglet onglet--actif" : "onglet"}>
            <span className="onglet__symbole">{x}</span>{x === demande ? <span className="onglet__poids">demandé</span> : null}
          </button>
        ))}
      </div>
      {!univers ? <p className="diapo__justification">Chargement des cours…</p> : !actif ? (
        <p className="diapo__manque">Information manquante : pas de cours pour {symbole} dans web/data/univers.json.</p>
      ) : (
        <>
          <div className="cours-commentes__graphique">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 22, right: 18, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--grille)" strokeWidth={1} />
                <XAxis dataKey="date" ticks={annees} interval={0} tickFormatter={(v: string) => v.slice(0, 4)} tick={{ fill: "var(--encre-discrete)", fontSize: 12 }}
                  axisLine={{ stroke: "var(--axe)" }} tickLine={false} />
                <YAxis width={56} tick={{ fill: "var(--encre-discrete)", fontSize: 12 }} axisLine={false} tickLine={false}
                  tickFormatter={(v: number) => compact.format(v)} domain={["auto", "auto"]} />
                {pic && creux ? <ReferenceArea x1={pic.date} x2={creux.date} fill="var(--echec)" fillOpacity={0.08} stroke="none" /> : null}
                <Tooltip cursor={{ stroke: "var(--axe)", strokeWidth: 1 }} content={({ active, payload }) => {
                  const p = payload?.[0]?.payload as { date: string; prix: number } | undefined;
                  return active && p ? (
                    <div className="infobulle"><strong>{formaterDate(p.date)}</strong>
                      <span>{p.prix.toLocaleString("fr-CA", { maximumFractionDigits: 2 })} {actif.devise}, cours ajusté</span></div>
                  ) : null;
                }} />
                <Line type="monotone" dataKey="prix" stroke="var(--serie-1)" strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }}
                  isAnimationActive animationDuration={700} />
                {pic ? <ReferenceDot x={pic.date} y={pic.prix} r={5} fill="var(--encre)" stroke="var(--surface)" strokeWidth={2}
                  label={{ value: "Sommet", position: "top", fill: "var(--encre)", fontSize: 12, fontWeight: 700 }} /> : null}
                {creux ? <ReferenceDot x={creux.date} y={creux.prix} r={5} fill="var(--echec)" stroke="var(--surface)" strokeWidth={2}
                  label={{ value: "Creux", position: "bottom", fill: "var(--encre)", fontSize: 12, fontWeight: 700 }} /> : null}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="cours-commentes__commentaire">
            <p>
              <strong>{actif.nom} ({symbole})</strong>{" "}
              {pb && d.pic && d.creux ? (
                <>a perdu <Chiffre id={pb} /> entre son sommet du {formaterDate(d.pic)} et son creux du {formaterDate(d.creux)}
                  {d.retour ? <>, puis a retrouvé son sommet le {formaterDate(d.retour)}.</> : <> ; il n&apos;avait pas retrouvé son sommet à la fin de la fenêtre.</>}</>
              ) : <span className="manque">Information manquante : pas de pire baisse calculée pour cet actif.</span>}
              {ratt ? <> Pour effacer cette baisse, il fallait un gain de <Chiffre id={ratt} />.</> : null}
              {vol ? <> Variation typique par an : <Chiffre id={vol} />.</> : null}
            </p>
            <p className="cours__source">Cours ajusté hebdomadaire, en {actif.devise} · data/prices_daily.csv (adj_close), via web/data/univers.json. Le passé ne promet rien.</p>
          </div>
        </>
      )}
    </div>
  );
}

// ---------- Éventail de scénarios ----------

export function EventailGraphique({ ev }: { ev: Eventail }) {
  const donnees = ev.annees.map((a, i) => ({
    annee: a, large: [ev.p10[i], ev.p90[i]], central: [ev.p25[i], ev.p75[i]], p50: ev.p50[i],
    p10: ev.p10[i], p25: ev.p25[i], p75: ev.p75[i], p90: ev.p90[i],
  }));
  const m = (v: number) => formaterMontant(v, ev.devise);
  return (
    <div className="eventail">
      <div className="eventail__graphique">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={donnees} margin={{ top: 12, right: 24, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grille)" strokeWidth={1} />
            <XAxis dataKey="annee" tickFormatter={(a: number) => `${a} an${a > 1 ? "s" : ""}`} tick={{ fill: "var(--encre-discrete)", fontSize: 12 }}
              axisLine={{ stroke: "var(--axe)" }} tickLine={false} />
            <YAxis width={64} tick={{ fill: "var(--encre-discrete)", fontSize: 12 }} axisLine={false} tickLine={false}
              tickFormatter={(v: number) => `${compact.format(v)} $`} domain={["auto", "auto"]} />
            {ev.capital ? <ReferenceLine y={ev.capital} stroke="var(--axe)" strokeWidth={1}
              label={{ value: "Capital de départ", position: "insideBottomLeft", fill: "var(--encre-discrete)", fontSize: 12 }} /> : null}
            <Tooltip cursor={{ stroke: "var(--axe)", strokeWidth: 1 }} content={({ active, payload }) => {
              const p = payload?.[0]?.payload as (typeof donnees)[number] | undefined;
              return active && p ? (
                <div className="infobulle">
                  <strong>Après {p.annee} an{p.annee > 1 ? "s" : ""}</strong>
                  <span>9 scénarios sur 10 au-dessus de {m(p.p10)}</span>
                  <span>Un sur deux entre {m(p.p25)} et {m(p.p75)}</span>
                  <span>Médiane : {m(p.p50)}</span>
                  <span>1 sur 10 au-dessus de {m(p.p90)}</span>
                </div>
              ) : null;
            }} />
            <Area dataKey="large" stroke="none" fill="var(--serie-1)" fillOpacity={0.12} isAnimationActive animationDuration={700} activeDot={false} />
            <Area dataKey="central" stroke="none" fill="var(--serie-1)" fillOpacity={0.26} isAnimationActive animationDuration={700} activeDot={false} />
            <Line dataKey="p50" stroke="var(--serie-1)" strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive animationDuration={700} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="eventail__legende">
        <span><i className="eventail__cle eventail__cle--mediane" /> Médiane à l&apos;horizon : <Chiffre id="scen_p50_fin" /></span>
        <span><i className="eventail__cle eventail__cle--central" /> Un scénario sur deux</span>
        <span><i className="eventail__cle eventail__cle--large" /> Huit sur dix : de <Chiffre id="scen_p10_fin" /> à <Chiffre id="scen_p90_fin" /></span>
        {ev.chiffres.scen_sous_capital ? <span>Sous le capital de départ à l&apos;horizon : <Chiffre id="scen_sous_capital" /> des scénarios</span> : null}
      </p>
      {ev.avertissement ? <p className="eventail__avertissement"><Texte>{ev.avertissement}</Texte></p> : null}
      {ev.hypotheses.length ? <ul className="eventail__hypotheses">{ev.hypotheses.map((h) => <li key={h}><Texte>{h}</Texte></li>)}</ul> : null}
    </div>
  );
}
