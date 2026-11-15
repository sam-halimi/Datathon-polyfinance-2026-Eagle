"use client";

import { useLayoutEffect, useRef, useState, type ReactNode, type TouchEvent } from "react";

// Aucun défilement dans un écran : une liste trop longue pour la place
// disponible est coupée en pages, qu'on tourne avec ‹ › ou d'un glissement.
// Les éléments sont d'abord posés dans un calque invisible de même largeur,
// mesurés, puis répartis : rien n'est tronqué, rien ne défile.

export type Element = { cle: string; contenu: ReactNode };

/** Hauteur de la barre ‹ • • › et de son écart (voir .pages__nav dans globals.css). */
const NAV = 42;

export function Pages({ elements, classe }: { elements: Element[]; classe: string }) {
  const cadre = useRef<HTMLDivElement>(null);
  const mesure = useRef<HTMLUListElement>(null);
  const [pages, setPages] = useState<number[][]>([elements.map((_, i) => i)]);
  const [page, setPage] = useState(0);
  const toucher = useRef<number | null>(null);
  const signature = elements.map((e) => e.cle).join("|");

  useLayoutEffect(() => {
    setPage(0);
  }, [signature]);

  useLayoutEffect(() => {
    const c = cadre.current;
    const m = mesure.current;
    if (!c || !m) return;
    const calculer = () => {
      // Toute la place si tout tient, sinon la place moins la barre de pages :
      // le calcul ne dépend pas de la barre déjà affichée ou non.
      const items = Array.from(m.children) as HTMLElement[];
      const total = items.length ? items[items.length - 1].offsetTop + items[items.length - 1].offsetHeight : 0;
      const hauteur = total <= c.clientHeight ? c.clientHeight : c.clientHeight - NAV;
      const decoupe: number[][] = [];
      let courante: number[] = [];
      let debut = 0;
      items.forEach((el, i) => {
        const haut = el.offsetTop;
        const bas = haut + el.offsetHeight;
        if (courante.length && bas - debut > hauteur) {
          decoupe.push(courante);
          courante = [];
        }
        if (!courante.length) debut = haut;
        courante.push(i);
      });
      if (courante.length) decoupe.push(courante);
      setPages((avant) => (JSON.stringify(avant) === JSON.stringify(decoupe) ? avant : decoupe));
    };
    calculer();
    const obs = new ResizeObserver(calculer);
    obs.observe(c);
    obs.observe(m);
    return () => obs.disconnect();
  }, [signature]);

  const n = Math.max(pages.length, 1);
  const p = Math.min(page, n - 1);
  const visibles = (pages[p] ?? []).map((i) => elements[i]).filter(Boolean);

  const debutToucher = (e: TouchEvent) => { toucher.current = e.touches[0].clientX; };
  const finToucher = (e: TouchEvent) => {
    if (toucher.current === null) return;
    const dx = e.changedTouches[0].clientX - toucher.current;
    toucher.current = null;
    if (dx < -40 && p < n - 1) setPage(p + 1);
    if (dx > 40 && p > 0) setPage(p - 1);
  };

  return (
    <div className="pages" ref={cadre}>
      <div className="pages__zone" onTouchStart={debutToucher} onTouchEnd={finToucher}>
        <ul className={`${classe} pages__mesure`} ref={mesure} aria-hidden="true" inert>
          {elements.map((e) => <li key={e.cle}>{e.contenu}</li>)}
        </ul>
        <ul className={classe} key={p}>
          {visibles.map((e) => <li key={e.cle}>{e.contenu}</li>)}
        </ul>
      </div>
      {n > 1 ? (
        <nav className="pages__nav" aria-label="Pages de la carte">
          <button type="button" className="pages__fleche" onClick={() => setPage(p - 1)} disabled={p === 0} aria-label="Page précédente">‹</button>
          <span className="pages__points" aria-live="polite">
            <span className="sr-only">Page {p + 1} sur {n}</span>
            {Array.from({ length: n }, (_, i) => (
              <span key={i} aria-hidden="true" className={i === p ? "pages__point pages__point--actif" : "pages__point"} />
            ))}
          </span>
          <button type="button" className="pages__fleche" onClick={() => setPage(p + 1)} disabled={p === n - 1} aria-label="Page suivante">›</button>
        </nav>
      ) : null}
    </div>
  );
}
