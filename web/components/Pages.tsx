"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

// Une liste plus longue que la place disponible défile à l'intérieur de sa carte :
// tout le contenu reste atteignable (molette, glissement, clavier), quelle que soit
// la hauteur de l'écran. Un fondu en bas, tant qu'il reste du contenu, et la barre de
// défilement signalent la suite. La page elle-même ne défile pas.

export type Element = { cle: string; contenu: ReactNode };

export function Pages({ elements, classe }: { elements: Element[]; classe: string }) {
  const zone = useRef<HTMLDivElement>(null);
  const [suite, setSuite] = useState(false);
  const signature = elements.map((e) => e.cle).join("|");

  useEffect(() => {
    const z = zone.current;
    if (!z) return;
    z.scrollTop = 0;
    const mesurer = () => setSuite(z.scrollHeight - z.clientHeight - z.scrollTop > 8);
    mesurer();
    z.addEventListener("scroll", mesurer, { passive: true });
    const obs = new ResizeObserver(mesurer);
    obs.observe(z);
    if (z.firstElementChild) obs.observe(z.firstElementChild);
    return () => { z.removeEventListener("scroll", mesurer); obs.disconnect(); };
  }, [signature]);

  return (
    <div className={suite ? "pages pages--suite" : "pages"}>
      {/* tabIndex : la zone se parcourt aussi au clavier (flèches, espace). */}
      <div className="pages__zone" ref={zone} tabIndex={0} role="group" aria-label="Contenu de la diapositive, défilement vertical">
        <ul className={classe}>
          {elements.map((e) => <li key={e.cle}>{e.contenu}</li>)}
        </ul>
      </div>
      {suite ? <p className="pages__indice" aria-hidden="true">Faites défiler pour lire la suite</p> : null}
    </div>
  );
}
