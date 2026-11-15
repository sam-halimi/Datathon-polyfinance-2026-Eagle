"use client";

import { createContext, useContext, type ReactNode } from "react";
import { formaterChiffre, formaterDate, majuscule } from "@/lib/format";
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

const MORCEAU = /(\{[a-z0-9_]+\}[.,;:)]?|https?:\/\/[^\s,;)]+)/g;

function hote(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Remplace les repères {id} d'un texte du pipeline par des chiffres touchables,
 *  et les adresses de sources par un lien court. La ponctuation qui suit un
 *  chiffre reste collée à lui. */
export function Texte({ children }: { children: string }) {
  const morceaux = typo(children).split(MORCEAU);
  return (
    <>
      {morceaux.map((m, i) => {
        if (/^https?:\/\//.test(m)) {
          return (
            <a key={i} className="lien" href={m} target="_blank" rel="noreferrer">{hote(m)}</a>
          );
        }
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

/** Le même texte, en clair, pour une tuile ou une étiquette. */
export function texteBrut(t: string, chiffres: Record<string, Reference>): string {
  return typo(t).replace(/\{([a-z0-9_]+)\}/g, (_, id: string) => (chiffres[id] ? formaterChiffre(chiffres[id]) : "?"));
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

function periode(ref: Reference): string {
  const p = ref.periode;
  if (!p.debut) return "Sans objet : une limite du profil, pas une mesure de marché";
  return `${formaterDate(p.debut)} au ${formaterDate(p.fin)}${p.observations ? ` · ${p.observations} jours` : ""}`;
}

function sansAccent(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/_/g, " ");
}

/** Un outil qui renvoie plusieurs valeurs (stats_portefeuille) a une formule
 *  par valeur : on montre celle du champ extrait, telle quelle. */
function formule(ref: Reference): string {
  if (!ref.champ) return ref.formule;
  const parts = ref.formule.split(" ; ");
  const champ = sansAccent(ref.champ);
  const trouve = parts.filter((f) => sansAccent(f).startsWith(champ));
  return trouve.length ? trouve.join(" ; ") : ref.formule;
}

export function FicheReference({ id, fermer }: { id: string; fermer: () => void }) {
  const { chiffres } = useChiffres();
  const ref = chiffres[id];
  if (!ref) return null;
  const d = ref.details ?? {};
  const pb = (d.pire_baisse ?? d) as Record<string, unknown>;
  const estBaisse = ref.outil === "pire_baisse" || ref.champ === "pire_baisse";
  const notes = [
    estBaisse && typeof pb.date_pic === "string" && typeof pb.date_creux === "string"
      ? `Du sommet du ${formaterDate(pb.date_pic)} au creux du ${formaterDate(pb.date_creux)}.`
      : null,
    typeof d.hypothese === "string" ? d.hypothese : null,
    typeof d.nature === "string" ? majuscule(d.nature) + "." : null,
    typeof d.avertissement === "string" ? d.avertissement : null,
  ].filter(Boolean) as string[];
  return (
    <div className="voile" role="dialog" aria-modal="true" aria-labelledby="fiche-titre" onClick={fermer}>
      <div className="fiche" onClick={(e) => e.stopPropagation()}>
        <p className="fiche__surtitre">D&apos;où vient ce chiffre ? <code>{id}</code></p>
        <p id="fiche-titre" className="fiche__valeur">
          {formaterChiffre(ref)}
          <span className="fiche__decrit">{ref.unite}</span>
        </p>
        <dl className="fiche__liste">
          <dt>Outil</dt>
          <dd><code>{ref.outil}</code>{ref.champ ? <> · <code>{ref.champ}</code></> : null}</dd>
          <dt>Paramètres</dt>
          <dd><Parametres p={ref.parametres} /></dd>
          <dt>Période</dt>
          <dd>{periode(ref)}</dd>
          <dt>Formule</dt>
          <dd>{formule(ref)}</dd>
          <dt>Source</dt>
          <dd>{ref.sources.join(", ")}</dd>
        </dl>
        {notes.length ? <p className="fiche__note">{notes.join(" ")}</p> : null}
        <button type="button" className="bouton bouton--principal" onClick={fermer} autoFocus>
          Fermer
        </button>
      </div>
    </div>
  );
}
