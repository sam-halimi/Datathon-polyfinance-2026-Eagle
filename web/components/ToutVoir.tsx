"use client";

import { BarreRepartition } from "./Cartes";
import { texteBrut, useChiffres } from "./Chiffres";
import { formaterChiffre, formaterHorizon } from "@/lib/format";
import type { Carte, Portefeuille, SortiePipeline } from "@/lib/types";

// « Tout voir » : les six cartes sur un écran, chacune réduite à l'essentiel.
// Toucher une tuile ouvre la carte entière.

const RISQUE: Record<string, string> = { faible: "Risque faible", modéré: "Risque modéré", élevé: "Risque élevé" };

export function ToutVoir({ sortie, ptf, ouvrir }: { sortie: SortiePipeline; ptf: Portefeuille; ouvrir: (c: Carte) => void }) {
  const { chiffres } = useChiffres();
  const profil = sortie.profil;
  const ctrl = sortie.gouvernance.controles;
  const ok = ctrl.filter((c) => c.statut === "ok").length;
  const alertes = ctrl.filter((c) => c.statut === "alerte").length;
  const echecs = ctrl.filter((c) => c.statut === "echec").length;
  const l = sortie.limites;
  const vol = chiffres[ptf.volatilite];

  const tuiles: { carte: Carte; titre: string; contenu: React.ReactNode }[] = [
    {
      carte: "profil", titre: "Profil",
      contenu: <>{profil.prenom}<br />{RISQUE[profil.tolerance_risque] ?? "—"}<br />{formaterHorizon(profil.horizon_annees)}</>,
    },
    {
      carte: "repartition", titre: "Répartition",
      contenu: <><BarreRepartition ptf={ptf} mince />Portefeuille {ptf.id} · {ptf.lignes.length} actifs</>,
    },
    {
      carte: "risque", titre: "Risque",
      contenu: <>Variation typique<br /><strong className="tuile__fort">{vol ? formaterChiffre(vol) : "?"}</strong></>,
    },
    {
      carte: "verifications", titre: "Vérifications",
      contenu: <>{ok} ✓{alertes ? ` · ${alertes} à signaler` : ""}{echecs ? ` · ${echecs} échec` : ""}</>,
    },
    { carte: "pourquoi", titre: "Pourquoi", contenu: <span className="tuile__extrait">{texteBrut(sortie.explication.niveau1, chiffres)}</span> },
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
