"use client";

import { useEffect, useState } from "react";
import { choisirLangue, ecouterLangue, installerTraduction, lireLangue, type Langue } from "@/lib/langue";

/** Langue choisie, pour les composants qui en dépendent (démonstrations, analyse, voix). */
export function useLangue(): Langue {
  const [l, setL] = useState<Langue>("fr");
  useEffect(() => {
    installerTraduction();
    setL(lireLangue());
    return ecouterLangue(setL);
  }, []);
  return l;
}

/** Bascule FR / EN. Les deux libellés sont des sigles : ils ne passent pas par le dictionnaire. */
export function ChoixLangue() {
  const l = useLangue();
  return (
    <div className="langue" role="group" aria-label="Langue / Language" data-sans-traduction>
      {(["fr", "en"] as const).map((x) => (
        <button key={x} type="button" className={l === x ? "langue__choix langue__choix--actif" : "langue__choix"}
          aria-pressed={l === x} lang={x} onClick={() => choisirLangue(x)}>{x === "fr" ? "Français" : "English"}</button>
      ))}
    </div>
  );
}
