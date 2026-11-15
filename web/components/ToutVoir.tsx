"use client";

import { BarreRepartition } from "./Cartes";
import { useChiffres } from "./Chiffres";
import { formaterChiffre } from "@/lib/format";
import type { Carte, Profil, Reference, SortiePipeline } from "@/lib/types";

function texteSimple(t: string, chiffres: Record<string, Reference>): string {
  return t.replace(/\{([a-z0-9_]+)\}/g, (_, id: string) => (chiffres[id] ? formaterChiffre(chiffres[id]) : "?"));
}

const RISQUE: Record<string, string> = { faible: "Risque faible", modéré: "Risque modéré", élevé: "Risque élevé" };

export function ToutVoir({
  sortie, profil, ouvrir,
}: {
  sortie: SortiePipeline;
  profil: Profil;
  ouvrir: (c: Carte) => void;
}) {
  const { chiffres } = useChiffres();
  const ptf = sortie.portefeuilles[0];
  const ctrl = sortie.gouvernance.controles;
  const ok = ctrl.filter((c) => c.statut === "ok").length;
  const alertes = ctrl.filter((c) => c.statut === "alerte").length;
  const echecs = ctrl.filter((c) => c.statut === "echec").length;
  const l = sortie.limites;

  const tuiles: { carte: Carte; titre: string; contenu: React.ReactNode }[] = [
    { carte: "profil", titre: "Profil", contenu: <>{RISQUE[profil.tolerance_risque] ?? "—"}<br />{profil.horizon_annees}</> },
    {
      carte: "repartition", titre: "Répartition",
      contenu: <><BarreRepartition ptf={ptf} mince />{ptf.lignes.length} actifs</>,
    },
    {
      carte: "risque", titre: "Risque",
      contenu: <>Variation typique<br /><strong className="tuile__fort">{formaterChiffre(chiffres[ptf.volatilite])}</strong></>,
    },
    {
      carte: "verifications", titre: "Vérifications",
      contenu: <>{ok} ✓{alertes ? ` · ${alertes} alerte${alertes > 1 ? "s" : ""}` : ""}{echecs ? ` · ${echecs} échec` : ""}</>,
    },
    { carte: "pourquoi", titre: "Pourquoi", contenu: texteSimple(sortie.explication.niveau1, chiffres) },
    {
      carte: "limites", titre: "Limites",
      contenu: <>{l.faits.length} faits<br />{l.hypotheses.length} hypothèses<br />{l.limites.length} limites</>,
    },
  ];

  return (
    <div className="tout">
      {tuiles.map((t) => (
        <button key={t.carte} type="button" className="tuile" onClick={() => ouvrir(t.carte)}>
          <span className="tuile__titre">{t.titre}</span>
          <span className="tuile__contenu">{t.contenu}</span>
        </button>
      ))}
    </div>
  );
}
