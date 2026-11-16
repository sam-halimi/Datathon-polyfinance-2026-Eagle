"use client";

import { useEffect, useState } from "react";
import { CarteVerifications } from "./Cartes";
import { FichesLignes, LimitesPortefeuille, MANQUE, retenu, TableauAdequation } from "./Adequation";
import { Chiffre, Texte, texteBrut, typo } from "./Chiffres";
import { CoursCommentes, EventailGraphique, TroisAnneaux } from "./Visualisations";
import { phraseCours } from "./Graphiques";
import { Pages, type Element } from "./Pages";
import type { VerdictActif } from "@/lib/api";
import { lireEventail } from "@/lib/scenarios";
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

/** Un constat de spécialiste : repères {id} touchables, et le gras « **…** » que le modèle
 *  met parfois en tête de phrase rendu en gras plutôt qu'affiché tel quel. */
function Constat({ texte }: { texte: string }) {
  return (
    <>
      {texte.split(/\*\*(.+?)\*\*/g).map((m, i) => (
        i % 2 ? <strong key={i}><Texte>{m}</Texte></strong> : m ? <Texte key={i}>{m}</Texte> : null
      ))}
    </>
  );
}

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
  const reps = s.graphiques?.repartitions?.[ptf.id];
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
  // Le diagnostic de chaque spécialiste (champ « specialistes » de la sortie), sous son étape.
  const sp = s.specialistes;
  const constats: Record<string, string[]> = {
    "Marché et risque": sp?.marche_et_risque ?? [],
    "Macro et taux": sp?.macro ?? [],
    "ESG et qualité": sp?.esg?.constats ?? [],
  };
  const nbConstats = Object.values(constats).reduce((n, t) => n + t.length, 0);
  return [
    {
      id: "demarche", court: "Démarche", titre: "Comment ce portefeuille a été établi",
      justification: nbConstats
        ? "Les étapes suivies par les agents pour votre profil, dans l'ordre, et le diagnostic que chaque spécialiste a rédigé. Touchez un chiffre pour son calcul."
        : "Les étapes suivies par les agents pour votre profil, dans l'ordre, telles que le pipeline les a enregistrées.",
      contenu: etapes.length ? (
        <Pages classe="demarche" elements={etapes.map((e, i) => ({
          cle: `${i}-${e.agent}`,
          contenu: (
            <div className="demarche__etape" style={{ "--rang": i } as React.CSSProperties}>
              <span className="demarche__numero" aria-hidden="true">{i + 1}</span>
              <div className="demarche__corps">
                <p><strong className="demarche__agent">{e.agent}</strong> <span className="demarche__fait">{typo(e.fait)}</span></p>
                {constats[e.agent]?.length ? (
                  <ul className="demarche__constats" aria-label={`Diagnostic de l'agent ${e.agent}`}>
                    {constats[e.agent].map((t, k) => <li key={k}><Constat texte={t} /></li>)}
                  </ul>
                ) : null}
              </div>
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
      contenu: <TroisAnneaux s={s} ptf={ptf} />,
      texte: [ptf.intention, ...(["classe", "secteur", "zone"] as const).map((k) => `${{ classe: "Par classe d'actif", secteur: "Par secteur", zone: "Par zone" }[k]} : ${(reps?.[k] ?? []).map((p) => `${p.libelle} ${brut(`{${p.id}}`, c)}`).join(", ")}.`)].join(" "),
    },
    {
      id: "lignes", court: "Lignes", titre: `Les lignes du portefeuille simulé ${ptf.id}`,
      justification: "Une fiche par ligne : ce qu'elle est, pourquoi elle est là pour vous, ses chiffres et ses sources.",
      contenu: <FichesLignes s={s} />,
      texte: ptf.lignes.map((l) => `${l.nom} (${l.symbole}), ${brut(l.poids_id ? `{${l.poids_id}}` : "", c) || `${Math.round(l.poids * 100)} %`} : ${l.pourquoi ? brut(l.pourquoi, c) : `${MANQUE} sur la raison de cette ligne.`}`).join(" "),
    },
    {
      id: "cours", court: "Cours", titre: "Cours commentés", justification: "Le cours de l'actif demandé et de chaque ligne du portefeuille simulé, avec sa pire baisse sur la fenêtre. Survolez la courbe pour lire une date.",
      contenu: <CoursCommentes s={s} ptf={ptf} />,
      texte: cours ? brut(phraseCours(s), c) : `Cours des lignes du portefeuille ${ptf.id} : ${ptf.lignes.map((l) => `${l.symbole}, pire baisse ${brut(`{${ptf.pires_baisses?.[l.symbole]}}`, c)}`).join(" ; ")}.`,
    },
    {
      id: "scenarios", court: "Scénarios", titre: "Scénarios, pas une prévision",
      justification: "Un éventail de trajectoires possibles du portefeuille simulé, tirées des mois observés : une médiane et des bandes. Ce n'est pas une prévision.",
      contenu: ev ? <EventailGraphique ev={ev} /> : <p className="diapo__manque">Information manquante : la réponse du pipeline ne contient pas de champ « scenarios ». Rien n&apos;est tracé à sa place.</p>,
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

// Les agents du pipeline, dans l'ordre d'exécution (agents/pipeline.py).
// Le serveur ne transmet pas l'avancement en direct : l'écran d'attente montre
// le déroulé prévu sans prétendre savoir quelle étape est en cours ; les étapes
// réellement suivies s'affichent ensuite dans la diapositive « Démarche ».
const AGENTS = [
  ["Orchestrateur", "lit votre profil et votre demande, fixe les plafonds"],
  ["ESG et qualité", "écarte ou signale les titres selon vos critères, avec leurs sources"],
  ["Marché et risque", "mesure volatilité et pires baisses des actifs candidats"],
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
        Analyse en cours depuis {ecoule} s. Comptez de une à trois minutes selon le profil. Le détail de chaque étape s&apos;affiche avec le résultat.
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
