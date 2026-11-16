"use client";

import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import {
  Bitcoin, BrainCircuit, Building2, Cpu, Gamepad2, Gem, HeartPulse, Landmark, Leaf, Plus, Rocket, Trophy, Wheat, X,
  type LucideIcon,
} from "lucide-react";
import { cleIllustration, Illustration, useDa } from "./Da";
import { formaterMontant } from "@/lib/format";
import type { QuestionChoix, QuestionCurseur } from "@/lib/questions";

// Les réponses de l'accueil : boutons de choix (avec icône pour les thèmes),
// curseurs à bulle (connaissance, capital) et champ libre.

const ICONES: Record<string, LucideIcon> = {
  technologie: Cpu, ia: BrainCircuit, jeu: Gamepad2, sante: HeartPulse, energie: Leaf, immobilier: Building2,
  finance: Landmark, luxe: Gem, sport: Trophy, aerospatiale: Rocket, alimentation: Wheat, crypto: Bitcoin,
};

export function Choix({ q, choisis, choisir, vider }: {
  q: QuestionChoix;
  choisis: unknown[];
  choisir: (valeur: string | number, titre: string) => void;
  vider: () => void;
}) {
  const [libre, setLibre] = useState("");
  const { illustrations } = useDa();
  const proposes = new Set(q.options.map((o) => String(o.valeur)));
  const ajoutes = choisis.map(String).filter((v) => !proposes.has(v));
  const avecIcones = q.options.some((o) => o.icone);
  const ajouter = (e: FormEvent) => {
    e.preventDefault();
    const v = libre.trim();
    if (!v) return;
    if (!choisis.map(String).includes(v)) choisir(v, v);
    setLibre("");
  };
  const n = q.options.length + (q.multiple ? 1 : 0);
  return (
    <div className="reponses">
      {/* Avec illustrations : tuiles pour les thèmes (libellé seul), fiches sur deux colonnes quand l'option a une précision. */}
      <div className={`choix choix--${avecIcones ? (q.options.some((o) => o.detail) ? "fiches" : "icones") : n > 6 ? "serre" : "large"}`} role={q.multiple ? "group" : "radiogroup"}>
        {q.options.map((o, i) => {
          const actif = choisis.includes(o.valeur);
          // Illustration de la charte quand elle existe pour ce thème, sinon pictogramme.
          // `icone` nomme directement un fichier de la charte (questions 5 et 6), sinon on le déduit du thème.
          const cleDa = o.icone ? (illustrations[o.icone] ? o.icone : cleIllustration(String(o.valeur))) : null;
          const Icone = o.icone && !(cleDa && illustrations[cleDa]) ? ICONES[o.icone] : null;
          return (
            <button key={String(o.valeur)} type="button" role={q.multiple ? "checkbox" : "radio"} aria-checked={actif}
              className={actif ? "choix__bouton choix__bouton--actif" : "choix__bouton"} style={{ "--rang": i } as CSSProperties}
              onClick={() => choisir(o.valeur, o.titre)}>
              {cleDa && illustrations[cleDa] ? <Illustration cle={cleDa} taille={44} /> : null}
              {Icone ? <Icone className="choix__icone" aria-hidden="true" strokeWidth={2} /> : null}
              <span className="choix__textes">
                <span className="choix__titre">{o.titre}</span>
                {o.detail ? <span className="choix__detail">{o.detail}</span> : null}
              </span>
            </button>
          );
        })}
        {q.multiple ? (
          <button type="button" role="checkbox" aria-checked={choisis.length === 0} style={{ "--rang": q.options.length } as CSSProperties}
            className={choisis.length === 0 ? "choix__bouton choix__bouton--actif choix__bouton--aucun" : "choix__bouton choix__bouton--aucun"}
            onClick={vider}>
            <span className="choix__textes"><span className="choix__titre">{q.aucun}</span></span>
          </button>
        ) : null}
      </div>
      {q.libre ? (
        <form className="libre" onSubmit={ajouter}>
          <label className="sr-only" htmlFor={`libre-${q.champ}`}>{q.libre}</label>
          <input id={`libre-${q.champ}`} value={libre} onChange={(e) => setLibre(e.target.value)} placeholder={q.libre} autoComplete="off" />
          <button type="submit" className="libre__ajouter" disabled={!libre.trim()}><Plus aria-hidden="true" size={18} /> Ajouter</button>
          {ajoutes.map((v) => (
            <button key={v} type="button" className="etiquette" onClick={() => choisir(v, v)} aria-label={`Retirer ${v}`}>
              {v} <X aria-hidden="true" size={14} />
            </button>
          ))}
        </form>
      ) : null}
    </div>
  );
}

/** Curseur à bulle : la bulle suit le pouce et change à chaque cran. */
export function Curseur({ q, valeur, changer, devise = "CAD" }: {
  q: QuestionCurseur;
  valeur: number | undefined;
  changer: (v: number) => void;
  devise?: string;
}) {
  const v = valeur ?? q.depart;
  const ratio = Math.min(1, Math.max(0, (v - q.min) / (q.max - q.min)));
  const bulle = q.crans ? q.crans[v] : formaterMontant(v, devise);
  // Montant précis : le champ accepte n'importe quel montant entre les bornes, pas seulement les
  // crans du curseur. Le texte tapé est gardé tel quel tant qu'il n'est pas un montant valide.
  const [saisie, setSaisie] = useState<string | null>(null);
  useEffect(() => { setSaisie(null); }, [q.champ]);
  const nombre = (t: string) => Number(t.replace(/[^\d]/g, ""));
  const horsBornes = saisie !== null && (nombre(saisie) < q.min || nombre(saisie) > q.max);
  const taper = (t: string) => {
    setSaisie(t);
    const n = nombre(t);
    if (n >= q.min && n <= q.max) changer(n);
  };
  return (
    <div className={`curseur${q.crans ? " curseur--crans" : " curseur--montant"}`}>
      <div className="curseur__piste" style={{ "--ratio": ratio } as CSSProperties}>
        <output className="curseur__bulle" htmlFor={`curseur-${q.champ}`} aria-live="polite">
          {q.crans ? <span className="curseur__cran">Niveau {v} sur {q.max}</span> : null}
          {bulle}
        </output>
        <input id={`curseur-${q.champ}`} type="range" min={q.min} max={q.max} step={q.pas} value={v}
          aria-valuetext={q.crans ? `Niveau ${v} : ${bulle}` : bulle}
          onChange={(e) => { setSaisie(null); changer(Number(e.target.value)); }} />
      </div>
      {q.crans ? (
        <ol className="curseur__graduations" aria-hidden="true">
          {Object.keys(q.crans).map((k) => (
            <li key={k} className={Number(k) === v ? "curseur__graduation curseur__graduation--actif" : "curseur__graduation"}
              style={{ "--pos": (Number(k) - q.min) / (q.max - q.min) } as CSSProperties}>
              <button type="button" tabIndex={-1} onClick={() => changer(Number(k))}>{k}</button>
            </li>
          ))}
        </ol>
      ) : (
        <>
          <p className="curseur__bornes" aria-hidden="true">
            <span>{formaterMontant(q.min, devise)}</span><span>{formaterMontant(q.max, devise)}</span>
          </p>
          <label className="curseur__precis">
            <span>Ou saisissez un montant précis</span>
            <span className="curseur__champ">
              <input type="text" inputMode="numeric" autoComplete="off" aria-invalid={horsBornes}
                aria-describedby={`precis-aide-${q.champ}`}
                value={saisie ?? new Intl.NumberFormat("fr-CA").format(v)}
                onChange={(e) => taper(e.target.value)} onFocus={(e) => e.target.select()}
                onBlur={() => setSaisie(null)} />
              <span aria-hidden="true">$ {devise}</span>
            </span>
            <span id={`precis-aide-${q.champ}`} className={horsBornes ? "curseur__precis-aide curseur__precis-aide--erreur" : "curseur__precis-aide"}>
              {horsBornes ? `Indiquez un montant entre ${formaterMontant(q.min, devise)} et ${formaterMontant(q.max, devise)}.` : "Au dollar près, entre les deux bornes."}
            </span>
          </label>
        </>
      )}
      {valeur === undefined ? <p className="curseur__aide">Déplacez le curseur, puis validez.</p> : null}
    </div>
  );
}
