"use client";

import { useEffect, useState } from "react";
import { typo } from "./Chiffres";
import { formaterDate } from "@/lib/format";
import type { SortiePipeline } from "@/lib/types";

// Ce que chaque agent du pipeline a fait, dans l'ordre (champ « etapes »).

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
      </header>
      <ol className="analyse">
        {sortie.etapes.map((e, i) => {
          const etat = i < faites ? "faite" : i === faites ? "en-cours" : "attente";
          return (
            <li key={e.agent} className={`analyse__etape analyse__etape--${etat}`}>
              <span className="analyse__puce" aria-hidden="true">{etat === "faite" ? "✓" : i + 1}</span>
              <span className="analyse__texte">
                <span className="analyse__agent">{e.agent}</span>
                <span className="analyse__fait">{typo(e.fait)}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="carte__pied">Sortie du pipeline du {formaterDate(sortie.meta?.date ?? null)} · agents/sorties/{sortie.scenario}.json</p>
    </article>
  );
}
