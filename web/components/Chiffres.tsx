"use client";

import { createContext, useContext, type ReactNode } from "react";
import { formaterChiffre, formaterDate } from "@/lib/format";
import type { Reference } from "@/lib/types";

// Tout chiffre affiché passe par <Chiffre id="…"> : on peut le toucher pour
// voir l'appel d'outil qui l'a produit. Un repère inconnu s'affiche « ? » :
// on ne comble pas un trou en silence.

type Ctx = { chiffres: Record<string, Reference>; ouvrir: (id: string) => void };
const ChiffresCtx = createContext<Ctx>({ chiffres: {}, ouvrir: () => {} });

export function FournisseurChiffres({ valeur, children }: { valeur: Ctx; children: ReactNode }) {
  return <ChiffresCtx.Provider value={valeur}>{children}</ChiffresCtx.Provider>;
}

export function useChiffres() {
  return useContext(ChiffresCtx);
}

export function Chiffre({ id }: { id: string }) {
  const { chiffres, ouvrir } = useChiffres();
  const ref = chiffres[id];
  if (!ref) return <span className="chiffre chiffre--manquant" title={`Chiffre absent : ${id}`}>?</span>;
  return (
    <button type="button" className="chiffre" onClick={() => ouvrir(id)} aria-label={`${formaterChiffre(ref)}, voir le calcul`}>
      {formaterChiffre(ref)}
    </button>
  );
}

/** Espaces insécables du français : avant ? ! : ; » et après «. */
export function typo(t: string): string {
  return t.replace(/ ([?!:;»])/g, "\u00a0$1").replace(/« /g, "«\u00a0");
}

/** Remplace les repères {id} d'un texte du pipeline par des chiffres touchables.
 *  La ponctuation qui suit un chiffre reste collée à lui. */
export function Texte({ children }: { children: string }) {
  const morceaux = typo(children).split(/(\{[a-z0-9_]+\}[.,;:)]?)/g);
  return (
    <>
      {morceaux.map((m, i) => {
        const r = /^\{([a-z0-9_]+)\}([.,;:)]?)$/.exec(m);
        if (!r) return <span key={i}>{m}</span>;
        return (
          <span key={i} className="insecable">
            <Chiffre id={r[1]} />
            {r[2]}
          </span>
        );
      })}
    </>
  );
}

function Parametres({ p }: { p: Record<string, unknown> }) {
  const lignes = Object.entries(p)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => {
      const texte =
        typeof v === "object"
          ? Object.entries(v as Record<string, unknown>).map(([a, b]) => `${a} ${b}`).join(", ")
          : String(v);
      return `${k} = ${texte}`;
    });
  return <>{lignes.join(" · ") || "aucun"}</>;
}

export function FicheReference({ id, fermer }: { id: string; fermer: () => void }) {
  const { chiffres } = useChiffres();
  const ref = chiffres[id];
  if (!ref) return null;
  const decrit = ref.details?.decrit as string | undefined;
  const enAttente = ref.details?.en_attente as string | undefined;
  return (
    <div className="voile" role="dialog" aria-modal="true" aria-labelledby="fiche-titre" onClick={fermer}>
      <div className="fiche" onClick={(e) => e.stopPropagation()}>
        <p className="fiche__surtitre">D&apos;où vient ce chiffre ?</p>
        <p id="fiche-titre" className="fiche__valeur">
          {formaterChiffre(ref)}
          {decrit ? <span className="fiche__decrit"> {decrit}</span> : null}
        </p>
        <dl className="fiche__liste">
          <dt>Outil</dt>
          <dd><code>{ref.outil}</code></dd>
          <dt>Paramètres</dt>
          <dd><Parametres p={ref.parametres} /></dd>
          <dt>Période</dt>
          <dd>
            {formaterDate(ref.periode.debut)} au {formaterDate(ref.periode.fin)}
            {ref.periode.observations ? ` · ${ref.periode.observations} jours` : ""}
          </dd>
          <dt>Formule</dt>
          <dd>{ref.formule}</dd>
          <dt>Source</dt>
          <dd>{ref.sources.join(", ")}</dd>
        </dl>
        {enAttente ? <p className="fiche__note">{enAttente}</p> : null}
        <button type="button" className="bouton bouton--principal" onClick={fermer} autoFocus>
          Fermer
        </button>
      </div>
    </div>
  );
}
