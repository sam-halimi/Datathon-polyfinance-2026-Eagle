"use client";

import { useEffect, useState } from "react";
import { valeurDe, type Question } from "@/lib/questions";
import type { Profil, SortiePipeline } from "@/lib/types";

export function CarteQuestion({
  q, profil, choisir, vider,
}: {
  q: Question;
  profil: Profil;
  choisir: (valeur: string) => void;
  vider: () => void;
}) {
  const choisis = valeurDe(profil, q);
  return (
    <article className="carte carte--question">
      {q.aide ? <p className="carte__chapeau">{q.aide}</p> : null}
      <div className={q.options.length > 4 ? "choix choix--serres" : "choix"} role={q.multiple ? "group" : "radiogroup"}>
        {q.options.map((o) => {
          const actif = choisis.includes(o.valeur);
          return (
            <button key={o.valeur} type="button" role={q.multiple ? "checkbox" : "radio"} aria-checked={actif}
              className={actif ? "choix__bouton choix__bouton--actif" : "choix__bouton"} onClick={() => choisir(o.valeur)}>
              <span className="choix__titre">{o.titre}</span>
              {o.detail ? <span className="choix__detail">{o.detail}</span> : null}
            </button>
          );
        })}
        {q.multiple && q.aucun ? (
          <button type="button" role="checkbox" aria-checked={choisis.length === 0}
            className={choisis.length === 0 ? "choix__bouton choix__bouton--actif" : "choix__bouton"} onClick={vider}>
            <span className="choix__titre">{q.aucun}</span>
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function CarteAnalyse({ sortie, fini }: { sortie: SortiePipeline; fini: () => void }) {
  const [faites, setFaites] = useState(0);
  const total = sortie.etapes.length;
  useEffect(() => {
    if (faites >= total) {
      fini();
      return;
    }
    const lent = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t = window.setTimeout(() => setFaites((n) => n + 1), lent ? 650 : 50);
    return () => window.clearTimeout(t);
  }, [faites, total, fini]);
  return (
    <article className="carte">
      <header className="carte__entete">
        <h2 className="carte__titre">Analyse</h2>
        {sortie.exemple ? <span className="pastille">Exemple</span> : null}
      </header>
      <ol className="analyse">
        {sortie.etapes.map((e, i) => {
          const etat = i < faites ? "faite" : i === faites ? "en-cours" : "attente";
          return (
            <li key={e.agent} className={`analyse__etape analyse__etape--${etat}`}>
              <span className="analyse__puce" aria-hidden="true">{etat === "faite" ? "✓" : i + 1}</span>
              <span>
                <span className="analyse__agent">{e.agent}</span>
                <span className="analyse__fait">{e.fait}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </article>
  );
}
