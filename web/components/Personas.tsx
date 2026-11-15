"use client";

import { typo } from "./Chiffres";
import { formaterHorizon } from "@/lib/format";
import { PERSONAS, type Persona } from "@/lib/personas";

// Écran de choix : les trois personas des tests d'acceptation. Toucher une
// carte charge la sortie du pipeline de ce persona.

const RISQUE: Record<string, string> = { faible: "Risque faible", modéré: "Risque modéré", élevé: "Risque élevé" };

export function CartePersonas({ choisir, enCours }: { choisir: (p: Persona) => void; enCours: string | null }) {
  return (
    <div className="personas" role="list">
      {PERSONAS.map((p) => (
        <button key={p.id} type="button" role="listitem" className="persona" onClick={() => choisir(p)}
          disabled={enCours !== null} aria-busy={enCours === p.id}>
          <span className="persona__haut">
            <span className="persona__initiale" aria-hidden="true">{p.nom[0]}</span>
            <span className="persona__nom">{p.nom}, {p.age} ans</span>
            <span className="persona__fleche" aria-hidden="true">{enCours === p.id ? "…" : "›"}</span>
          </span>
          <span className="persona__tags">
            {RISQUE[p.tolerance] ?? p.tolerance} · horizon {formaterHorizon(p.horizon)}
          </span>
          <span className="persona__demande">{typo(`« ${p.demande} »`)}</span>
        </button>
      ))}
    </div>
  );
}
