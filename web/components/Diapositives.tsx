"use client";

import { useEffect, useState } from "react";
import { CarteVerifications } from "./Cartes";
import { FichesLignes, LimitesPortefeuille, MANQUE, retenu, TableauAdequation } from "./Adequation";
import { Chiffre, Texte, texteBrut, typo } from "./Chiffres";
import { Camembert, Cours, Legende, LegendeCours, PhraseCours, phraseCours, SourceCours } from "./Graphiques";
import { Pages, type Element } from "./Pages";
import type { VerdictActif } from "@/lib/api";
import { lireEventail, type Eventail as EventailDonnees } from "@/lib/scenarios";
import type { Reference, SortiePipeline } from "@/lib/types";

// Les diapositives de la présentation. Chacune a un titre, sa justification,
// son contenu et le texte que la voix lit (outil afficher_diapositive) :
// les chiffres de ce texte viennent de la table « chiffres », rien d'autre.

export type Diapositive = {
  id: "demarche" | "demande" | "adequation" | "repartition" | "lignes" | "cours" | "scenarios" | "verifications" | "limites";
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

  const ev = lireEventail(s);
  const cev = { ...c, ...(ev?.chiffres ?? {}) };
  const etapes = s.etapes ?? [];
  return [
    {
      id: "demarche", court: "Démarche", titre: "Comment ce portefeuille a été établi",
      justification: "Les étapes suivies par les agents pour votre profil, dans l'ordre, telles que le pipeline les a enregistrées.",
      contenu: etapes.length ? (
        <Pages classe="demarche" elements={etapes.map((e, i) => ({
          cle: `${i}-${e.agent}`,
          contenu: (
            <div className="demarche__etape" style={{ "--rang": i } as React.CSSProperties}>
              <span className="demarche__numero" aria-hidden="true">{i + 1}</span>
              <span><strong className="demarche__agent">{e.agent}</strong> <span className="demarche__fait">{typo(e.fait)}</span></span>
            </div>
          ),
        }))} />
      ) : <p className="diapo__manque">Information manquante : la réponse du pipeline ne contient pas ses étapes.</p>,
      texte: etapes.length ? etapes.map((e) => `${e.agent} : ${e.fait}`).join(" ") : "Information manquante : les étapes du pipeline ne sont pas dans la réponse.",
    },
    {
      id: "demande", court: "La demande", titre: "Votre demande au regard de votre profil", justification: s.messages.analyse,
      contenu: <Pages elements={elementsDemande} classe="diapo__liste" />,
      texte: [s.messages.analyse, demande && `Demande : ${demande}`, tension && brut(tension.detail, c), brut(e.niveau1, c), ...e.niveau2.map((t) => brut(t, c))].filter(Boolean).join(" "),
    },
    {
      id: "adequation", court: "Pourquoi vous", titre: "Pourquoi ce portefeuille vous correspond",
      justification: "Chaque critère de votre profil, ce que fait le portefeuille simulé pour y répondre et la preuve chiffrée. Touchez un chiffre pour son calcul.",
      contenu: <TableauAdequation s={s} />,
      texte: (retenu(s).adequation ?? s.adequation)
        ? (retenu(s).adequation ?? s.adequation)!.map((a) => `${a.critere}${a.element ? ` ${a.element}` : ""} : ${a.statut}. ${brut(a.reponse, c)}${a.raison ? ` ${a.raison}` : ""}`).join(" ")
        : `${MANQUE} : la réponse du pipeline ne contient pas l'adéquation au profil.`,
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
      id: "lignes", court: "Lignes", titre: `Les lignes du portefeuille simulé ${ptf.id}`,
      justification: "Une fiche par ligne : ce qu'elle est, pourquoi elle est là pour vous, ses chiffres et ses sources.",
      contenu: <FichesLignes s={s} />,
      texte: ptf.lignes.map((l) => `${l.nom} (${l.symbole}), ${brut(l.poids_id ? `{${l.poids_id}}` : "", c) || `${Math.round(l.poids * 100)} %`} : ${l.pourquoi ? brut(l.pourquoi, c) : `${MANQUE} sur la raison de cette ligne.`}`).join(" "),
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
      justification: "Un éventail de trajectoires possibles du portefeuille simulé, tirées des mois observés : une médiane et des bandes. Ce n'est pas une prévision.",
      contenu: ev ? <Eventail ev={ev} /> : <p className="diapo__manque">Information manquante : la réponse du pipeline ne contient pas de champ « scenarios ». Rien n&apos;est tracé à sa place.</p>,
      texte: ev
        ? ["Scénarios, pas une prévision.", `Médiane à l'horizon : ${brut("{scen_p50_fin}", cev)}.`, `Huit scénarios sur dix entre ${brut("{scen_p10_fin}", cev)} et ${brut("{scen_p90_fin}", cev)}.`, ev.avertissement ?? "", ...ev.hypotheses].join(" ")
        : "Information manquante : les scénarios ne sont pas dans la réponse du pipeline.",
    },
    {
      id: "verifications", court: "Vérifications", titre: "Ce que la gouvernance a vérifié", justification: s.messages.verifications,
      contenu: <CarteVerifications sortie={s} />,
      texte: [s.messages.verifications, ...g.controles.filter((k) => k.statut !== "ok").map((k) => `${k.titre} : ${brut(k.detail, c)}`), `${g.controles.filter((k) => k.statut === "ok").length} contrôles conformes.`].join(" "),
    },
    {
      id: "limites", court: "Limites", titre: "Limites et hypothèses de ce portefeuille", justification: s.messages.limites,
      contenu: <LimitesPortefeuille s={s} />,
      texte: s.limites.limites_specifiques
        ? [s.messages.limites, ...[...s.limites.limites_specifiques].sort((x, y) => x.importance - y.importance).map((x) => brut(x.texte, c)),
          ...(s.limites.hypotheses_specifiques ?? []).map((h) => `${brut(h.texte, c)} Si elle ne tient pas : ${brut(h.si_elle_tombe, c)}`)].join(" ")
        : [s.messages.limites, `${MANQUE} : pas de limites propres au portefeuille dans la réponse.`, ...s.limites.limites.map((t) => brut(t, c))].join(" "),
    },
  ];
}

/** Éventail de scénarios : bandes p10-p90 et p25-p75, médiane en trait. */
function Eventail({ ev }: { ev: EventailDonnees }) {
  const L = 620, H = 260, m = { h: 12, b: 24, g: 8, d: 8 };
  const toutes = [...ev.p10, ...ev.p90];
  const y0 = Math.min(...toutes), y1 = Math.max(...toutes);
  const X = (i: number) => m.g + (i / Math.max(1, ev.annees.length - 1)) * (L - m.g - m.d);
  const Y = (v: number) => m.h + (1 - (v - y0) / (y1 - y0 || 1)) * (H - m.h - m.b);
  const ligne = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const bande = (haut: number[], bas: number[]) => `${ligne(haut)}${bas.map((_, k) => { const i = bas.length - 1 - k; return `L${X(i).toFixed(1)},${Y(bas[i]).toFixed(1)}`; }).join("")}Z`;
  const n = ev.annees.length - 1;
  return (
    <div className="eventail">
      <svg viewBox={`0 0 ${L} ${H}`} className="eventail__svg" role="img" aria-label="Éventail de scénarios : médiane et bandes">
        <path className="eventail__bande eventail__bande--0" d={bande(ev.p90, ev.p10)} />
        <path className="eventail__bande eventail__bande--1" d={bande(ev.p75, ev.p25)} />
        <path d={ligne(ev.p50)} className="eventail__mediane" />
        {[0, Math.floor(n / 2), n].map((i) => <text key={i} x={X(i)} y={H - 6} className="cours__axe" textAnchor={i === 0 ? "start" : i === n ? "end" : "middle"}>{ev.annees[i]} an{ev.annees[i] > 1 ? "s" : ""}</text>)}
      </svg>
      <p className="eventail__legende">
        <span><i className="eventail__cle eventail__cle--mediane" /> Médiane : <Chiffre id="scen_p50_fin" /></span>
        <span><i className="eventail__cle eventail__bande--1" /> Un scénario sur deux</span>
        <span><i className="eventail__cle eventail__bande--0" /> Huit sur dix : de <Chiffre id="scen_p10_fin" /> à <Chiffre id="scen_p90_fin" /></span>
      </p>
      {ev.avertissement ? <p className="eventail__avertissement">{typo(ev.avertissement)}</p> : null}
      {ev.hypotheses.length ? <ul className="eventail__hypotheses">{ev.hypotheses.map((h) => <li key={h}>{typo(h)}</li>)}</ul> : null}
    </div>
  );
}

// Les agents du pipeline, dans l'ordre d'exécution (agents/pipeline.py).
// Le serveur ne transmet pas l'avancement en direct : l'écran d'attente montre
// le déroulé prévu sans prétendre savoir quelle étape est en cours ; les étapes
// réellement suivies s'affichent ensuite dans la diapositive « Démarche ».
const AGENTS = [
  ["Orchestrateur", "lit votre profil et votre demande, fixe les plafonds"],
  ["Marché et risque", "mesure volatilité et pires baisses des actifs candidats"],
  ["ESG et qualité", "écarte ou signale les titres selon vos critères, avec leurs sources"],
  ["Macro et taux", "mesure la sensibilité aux taux et la pente des courbes"],
  ["Constructeur", "propose deux ou trois portefeuilles simulés"],
  ["Gouvernance", "vérifie chaque proposition au regard de votre profil, deux essais au plus"],
  ["Explication", "rédige l'explication, chaque chiffre renvoyant à son calcul"],
] as const;

export function DiapositiveAttente({ debut }: { debut: number }) {
  const [maintenant, setMaintenant] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setMaintenant(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const ecoule = Math.max(0, Math.floor((maintenant - debut) / 1000));
  return (
    <div className="attente">
      <ol className="attente__liste">
        {AGENTS.map(([nom, fait], i) => (
          <li key={nom} className="attente__agent" style={{ "--rang": i } as React.CSSProperties}>
            <span className="attente__puce" aria-hidden="true">{i + 1}</span>
            <span><strong>{nom}</strong> {fait}</span>
          </li>
        ))}
      </ol>
      <p className="attente__temps" aria-live="off">
        <span className="attente__indicateur" aria-hidden="true" />
        Analyse en cours depuis {ecoule} s, environ une minute au total. Le détail de chaque étape s&apos;affiche avec le résultat.
      </p>
    </div>
  );
}

export function DiapositiveActif({ symbole, verdict, erreur }: { symbole: string; verdict?: VerdictActif; erreur?: string }) {
  if (erreur) {
    return (
      <div className="diapo-actif">
        <h2 className="diapo__titre">{symbole} et votre profil</h2>
        <p className="diapo__manque">Service indisponible : {erreur} Rien n&apos;est affiché à sa place.</p>
      </div>
    );
  }
  if (!verdict) return <div className="diapo-actif"><h2 className="diapo__titre">{symbole} et votre profil</h2><p className="diapo__justification">Vérification en cours…</p></div>;
  const textes = [...(verdict.raisons ?? []), ...([] as string[]).concat(verdict.explication ?? [])];
  return (
    <div className="diapo-actif">
      <h2 className={verdict.compatible ? "diapo__titre diapo__titre--ok" : "diapo__titre diapo__titre--non"}>
        {verdict.compatible ? `${symbole} : compatible avec votre profil` : `Pourquoi ${symbole} ne correspond pas à votre profil`}
      </h2>
      {verdict.verdict ? <p className="diapo__justification"><Texte>{verdict.verdict}</Texte></p> : null}
      <Pages elements={textes.map((t, i) => ({ cle: `r${i}`, contenu: <p className="puce"><Texte>{t}</Texte></p> }))} classe="diapo__liste" />
    </div>
  );
}
