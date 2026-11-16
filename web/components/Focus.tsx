"use client";

import { createContext, useContext } from "react";

// Ce que la présentation met en avant à l'instant : une part d'un camembert, une ligne, un actif.
// La voix le règle avec afficher_diapositive(id, element) ; les graphiques le lisent et s'y placent.
// `n` change à chaque demande, pour rejouer la mise en avant du même élément.

export type Focus = { element: string; n: number } | null;
export const FocusCtx = createContext<Focus>(null);
export function useFocus(): Focus {
  return useContext(FocusCtx);
}

/** Même mot, sans accents ni casse : « Obligations (FNB) » ~ « obligations fnb ». */
export function rapproche(a: string, b: string): boolean {
  const n = (t: string) => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const x = n(a), y = n(b);
  return Boolean(x && y) && (x === y || x.includes(y) || y.includes(x));
}
