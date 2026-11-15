"use client";

import { useEffect, useState } from "react";
import { CarteLimites, CarteVerifications } from "./Cartes";
import { Chiffre, Texte, texteBrut, typo } from "./Chiffres";
import { Camembert, Cours, Legende, LegendeCours, PhraseCours, phraseCours, SourceCours } from "./Graphiques";
import { Pages, type Element } from "./Pages";
import type { VerdictActif } from "@/lib/api";
import type { Reference, Scenarios, SortiePipeline } from "@/lib/types";

// Les diapositives de la présentation. Chacune a un titre, sa justification,
// son contenu et le texte que la voix lit (outil afficher_diapositive) :
// les chiffres de ce texte viennent de la table « chiffres », rien d'autre.

export type Diapositive = {
  id: "demande" | "repartition" | "cours" | "scenarios" | "verifications" | "limites";
  court: string;
  titre: string;
  justification: string;
  contenu: React.ReactNode;
  texte: string;
};

function brut(t: string, c: Record<string, Reference>) {
  return texteBrut(t, c);
}

export function construireDiapositives(s: SortiePipeline): Diapositive[] {
  const c = s.chiffres;
  const g = s.gouvernance;
  const ptf = s.portefeuilles.find((p) => p.id === g.portefeuille_retenu) ?? s.portefeuilles[0];
  const demande = s.demande_analysee?.texte ?? s.profil.demande ?? "";
  const tension = g.controles.find((k) => k.controle === "demande_hors_profil") ?? g.controles.find((k) => k.titre === "Votre demande");
  const e = s.explication;
  const reps = s.graphiques.repartitions[ptf.id];
  const cours = s.graphiques.cours;

  const elementsDemande: Element[] = [
    ...(demande ? [{ cle: "citation", contenu: <blockquote className="diapo__citation">{typo(`« ${demande} »`)}</blockquote> }] : []),
    ...(tension ? [{ cle: "tension", contenu: <p className="diapo__alerte"><strong>{tension.titre}.</strong> <Texte>{tension.detail}</Texte></p> }] : []),
    { cle: "n1", contenu: <p className="diapo__phrase"><Texte>{e.niveau1}</Texte></p> },
    ...e.niveau2.map((t, i) => ({ cle: `n2-${i}`, contenu: <p className="puce"><Texte>{t}</Texte></p> })),
  ];

  const sc = s.scenarios;
  return [
    {
      id: "demande", court: "La demande", titre: "Ta demande, face à ton profil", justification: s.messages.analyse,
      contenu: <Pages elements={elementsDemande} classe="diapo__liste" />,
      texte: [s.messages.analyse, demande && `Demande : ${demande}`, tension && brut(tension.detail, c), brut(e.niveau1, c), ...e.niveau2.map((t) => brut(t, c))].filter(Boolean).join(" "),
    },
    {
      id: "repartition", court: "Répartition", titre: `Répartition du portefeuille simulé ${ptf.id} : ${ptf.nom}`, justification: ptf.intention,
      contenu: (
        <div className="diapo__camemberts">
          {([["actif", "Par actif"], ["secteur", "Par secteur"], ["zone", "Par zone géographique"]] as const).map(([k, nom]) => (
            <figure key={k}>
              <figcaption>{nom}</figcaption>
              <Camembert parts={reps[k]} taille={150} libelle={`Répartition ${nom.toLowerCase()}`} />
              <Legende parts={reps[k]} />
            </figure>
          ))}
        </div>
      ),
      texte: [ptf.intention, ...(["secteur", "zone"] as const).map((k) => `${k === "secteur" ? "Par secteur" : "Par zone"} : ${reps[k].map((p) => `${p.libelle} ${brut(`{${p.id}}`, c)}`).join(", ")}.`)].join(" "),
    },
    {
      id: "cours", court: "Cours", titre: cours ? `Cours de ${cours.nom} (${cours.symbole})` : "Cours de l'actif demandé", justification: s.messages.risque,
      contenu: cours ? (
        <Pages classe="diapo__liste diapo__cours" elements={[
          { cle: "graphique", contenu: <Cours sortie={s} hauteur={190} /> },
          { cle: "marques", contenu: <LegendeCours sortie={s} /> },
          { cle: "phrase", contenu: <PhraseCours sortie={s} /> },
          { cle: "source", contenu: <SourceCours sortie={s} /> },
        ]} />
      ) : <p className="diapo__manque">Information manquante : pas de cours ou pas de pire baisse calculée pour l&apos;actif demandé.</p>,
      texte: cours ? brut(phraseCours(s), c) : "Information manquante pour le cours de l'actif demandé.",
    },
    {
      id: "scenarios", court: "Scénarios", titre: "Scénarios, pas une prévision",
      justification: sc?.methode ?? "Un éventail de trajectoires possibles du portefeuille simulé : une médiane et des bandes. Ce n'est pas une prévision.",
      contenu: sc ? <Eventail sc={sc} /> : <p className="diapo__manque">Information manquante : la réponse du pipeline ne contient pas de champ « scenarios ». Rien n&apos;est tracé à sa place.</p>,
      texte: sc
        ? ["Scénarios, pas une prévision.", sc.reference ? `Médiane à l'horizon : ${brut(`{${sc.reference}}`, { ...c, ...(sc.chiffres ?? {}) })}.` : "", ...(sc.hypotheses ?? []).map((h) => brut(h, { ...c, ...(sc.chiffres ?? {}) }))].join(" ")
        : "Les scénarios ne sont pas disponibles pour cette analyse.",
    },
    {
      id: "verifications", court: "Vérifications", titre: "Ce que la gouvernance a vérifié", justification: s.messages.verifications,
      contenu: <CarteVerifications sortie={s} />,
      texte: [s.messages.verifications, ...g.controles.filter((k) => k.statut !== "ok").map((k) => `${k.titre} : ${brut(k.detail, c)}`), `${g.controles.filter((k) => k.statut === "ok").length} contrôles conformes.`].join(" "),
    },
    {
      id: "limites", court: "Limites", titre: "Faits, hypothèses et limites", justification: s.messages.limites,
      contenu: <CarteLimites sortie={s} />,
      texte: [s.messages.limites, ...s.limites.limites.map((t) => brut(t, c))].join(" "),
    },
  ];
}

/** Éventail de scénarios : bandes et médiane, sans graduation chiffrée
 *  (chaque chiffre montré a sa référence). */
function Eventail({ sc }: { sc: Scenarios }) {
  const x = sc.abscisses ?? sc.annees ?? sc.mediane.map((_, i) => i);
  const bandes = [...(sc.bandes ?? [])].sort((a, b) => Math.max(...b.haut.map((v, i) => v - b.bas[i])) - Math.max(...a.haut.map((v, i) => v - a.bas[i])));
  const toutes = [...sc.mediane, ...bandes.flatMap((b) => [...b.bas, ...b.haut])];
  const L = 620, H = 260, m = { h: 12, b: 24, g: 8, d: 8 };
  const y0 = Math.min(...toutes), y1 = Math.max(...toutes);
  const X = (i: number) => m.g + (i / Math.max(1, x.length - 1)) * (L - m.g - m.d);
  const Y = (v: number) => m.h + (1 - (v - y0) / (y1 - y0 || 1)) * (H - m.h - m.b);
  const ligne = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const etiquettes = [0, Math.floor((x.length - 1) / 2), x.length - 1];
  return (
    <div className="eventail">
      <svg viewBox={`0 0 ${L} ${H}`} className="eventail__svg" role="img" aria-label="Éventail de scénarios : médiane et bandes">
        {bandes.map((b, k) => (
          <path key={k} className={`eventail__bande eventail__bande--${k}`}
            d={`${ligne(b.haut)}${b.bas.map((v, i) => `L${X(b.bas.length - 1 - i).toFixed(1)},${Y(b.bas[b.bas.length - 1 - i]).toFixed(1)}`).join("")}Z`} />
        ))}
        <path d={ligne(sc.mediane)} className="eventail__mediane" />
        {etiquettes.map((i) => <text key={i} x={X(i)} y={H - 6} className="cours__axe" textAnchor={i === 0 ? "start" : i === x.length - 1 ? "end" : "middle"}>{String(x[i])}</text>)}
      </svg>
      <p className="eventail__legende">
        <span><i className="eventail__cle eventail__cle--mediane" /> Médiane</span>
        {bandes.map((b, k) => <span key={k}><i className={`eventail__cle eventail__bande--${k}`} /> {b.nom ?? `Bande ${b.niveau ?? k + 1}`}</span>)}
        {sc.reference ? <span>Médiane à l&apos;horizon : <Chiffre id={sc.reference} /></span> : null}
      </p>
      {sc.hypotheses?.length ? <ul className="eventail__hypotheses">{sc.hypotheses.map((h) => <li key={h}><Texte>{h}</Texte></li>)}</ul> : null}
    </div>
  );
}

const AGENTS = [
  ["Orchestrateur", "lit ton profil et fixe les plafonds"],
  ["ESG et qualité", "écarte ou signale les titres selon tes critères"],
  ["Marché et risque", "mesure volatilité et pires baisses"],
  ["Macro et taux", "mesure la sensibilité aux taux"],
  ["Constructeur", "propose deux ou trois portefeuilles simulés"],
  ["Gouvernance", "vérifie chaque proposition contre ton profil"],
  ["Explication", "prépare les chiffres et leurs références"],
] as const;

export function DiapositiveAttente({ debut }: { debut: number }) {
  const [maintenant, setMaintenant] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setMaintenant(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const ecoule = Math.max(0, Math.floor((maintenant - debut) / 1000));
  // Le service ne dit pas où il en est : l'animation avance au rythme d'environ une minute.
  const actif = Math.min(AGENTS.length - 1, Math.floor(ecoule / 9));
  return (
    <ol className="attente">
      {AGENTS.map(([nom, fait], i) => (
        <li key={nom} className={i < actif ? "attente__agent attente__agent--fait" : i === actif ? "attente__agent attente__agent--actif" : "attente__agent"}>
          <span className="attente__puce" aria-hidden="true">{i < actif ? "✓" : ""}</span>
          <span><strong>{nom}</strong> {fait}</span>
        </li>
      ))}
      <li className="attente__temps">Depuis {ecoule} s · environ une minute</li>
    </ol>
  );
}

export function DiapositiveActif({ symbole, verdict, erreur }: { symbole: string; verdict?: VerdictActif; erreur?: string }) {
  if (erreur) {
    return (
      <div className="diapo-actif">
        <h2 className="diapo__titre">{symbole} et ton profil</h2>
        <p className="diapo__manque">Service indisponible : {erreur} Rien n&apos;est affiché à sa place.</p>
      </div>
    );
  }
  if (!verdict) return <div className="diapo-actif"><h2 className="diapo__titre">{symbole} et ton profil</h2><p className="diapo__justification">Vérification en cours…</p></div>;
  const textes = [...(verdict.raisons ?? []), ...([] as string[]).concat(verdict.explication ?? [])];
  return (
    <div className="diapo-actif">
      <h2 className={verdict.compatible ? "diapo__titre diapo__titre--ok" : "diapo__titre diapo__titre--non"}>
        {verdict.compatible ? `${symbole} : compatible avec ton profil` : `Pourquoi ${symbole} ne convient pas à ton profil`}
      </h2>
      {verdict.verdict ? <p className="diapo__justification"><Texte>{verdict.verdict}</Texte></p> : null}
      <Pages elements={textes.map((t, i) => ({ cle: `r${i}`, contenu: <p className="puce"><Texte>{t}</Texte></p> }))} classe="diapo__liste" />
    </div>
  );
}
