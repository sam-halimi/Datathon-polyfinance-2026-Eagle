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
          aria-pressed={l === x} lang={x} onClick={() => choisirLangue(x)} aria-label={x === "fr" ? "Français" : "English"}>
          {/* Nom entier sur ordinateur, sigle sur téléphone : l'en-tête doit tenir sur 390 px. */}
          <span className="langue__long">{x === "fr" ? "Français" : "English"}</span>
          <span className="langue__court" aria-hidden="true">{x === "fr" ? "FR" : "EN"}</span>
        </button>
      ))}
    </div>
  );
}
