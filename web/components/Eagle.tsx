"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Aigle } from "./Aigle";
import { Voix } from "./Voix";
import { FicheReference, FournisseurChiffres, typo } from "./Chiffres";
import { construireDiapositives, DiapositiveActif, DiapositiveAttente, type Diapositive } from "./Diapositives";
import { analyser, ADRESSE_API, verifierActif, type VerdictActif } from "@/lib/api";
import { formaterHorizon, formaterMontant, majuscule } from "@/lib/format";
import { chargerSortie, PERSONAS, type Persona } from "@/lib/personas";
import { complet, noter, PROFIL_VIDE, QUESTIONS } from "@/lib/questions";
import { chargerUnivers, completerGraphiques } from "@/lib/repartition";
import type { Profil, Reference, SortiePipeline } from "@/lib/types";

// Eagle, sur ordinateur : un seul écran en trois colonnes.
// À gauche l'aigle, l'état de l'appel et la transcription ; au centre une
// diapositive à la fois ; à droite le profil qui se remplit en direct.

type Phase = "accueil" | "recap" | "analyse" | "presentation" | "erreur";
type Replique = { qui: "eagle" | "vous"; texte: string };

const ETAT: Record<Phase, string> = {
  accueil: "Questions d'accueil",
  recap: "Récapitulatif",
  analyse: "Analyse en cours",
  presentation: "Présentation",
  erreur: "Analyse indisponible",
};

function normaliser(t: string) {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export type EagleApi = {
  noterProfil: (champ: string, valeur: unknown) => string;
  lancerAnalyse: () => Promise<string>;
  afficherDiapositive: (id: string) => string;
};

export function Eagle({ onApi }: { onApi?: (api: EagleApi) => void }) {
  const [phase, setPhase] = useState<Phase>("accueil");
  const [question, setQuestion] = useState(0);
  const [profil, setProfil] = useState<Partial<Profil>>(PROFIL_VIDE);
  const [dernierChamp, setDernierChamp] = useState<string | null>(null);
  const [prenom, setPrenom] = useState("");
  const [demande, setDemande] = useState("");
  const [sortie, setSortie] = useState<SortiePipeline | null>(null);
  const [diapo, setDiapo] = useState(0);
  const [actif, setActif] = useState<{ symbole: string; verdict?: VerdictActif; erreur?: string } | null>(null);
  const [transcription, setTranscription] = useState<Replique[]>([
    { qui: "eagle", texte: "Bonjour, je suis Eagle, votre assistant. Je vais établir avec vous un portefeuille simulé et vous détailler chacun de ses chiffres. Aucune transaction réelle n'est effectuée. Commençons par votre profil." },
    { qui: "eagle", texte: QUESTIONS[0].texte },
  ]);
  const [saisie, setSaisie] = useState("");
  const [fiche, setFiche] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [debutAnalyse, setDebutAnalyse] = useState(0);
  const [univers, setUnivers] = useState<Record<string, { nom: string }>>({});

  useEffect(() => { chargerUnivers().then((u) => setUnivers(u.actifs)); }, []);

  const dire = useCallback((texte: string, qui: Replique["qui"] = "eagle") => {
    setTranscription((t) => [...t.slice(-30), { qui, texte }]);
  }, []);

  const diapos = useMemo<Diapositive[]>(() => (sortie ? construireDiapositives(sortie) : []), [sortie]);
  const chiffres = useMemo<Record<string, Reference>>(() => ({
    ...(sortie?.chiffres ?? {}),
    ...(sortie?.scenarios?.chiffres ?? {}),
    ...(actif?.verdict?.chiffres ?? {}),
  }), [sortie, actif]);
  const ctx = useMemo(() => ({ chiffres, ouvrir: setFiche }), [chiffres]);

  // ---------- Accueil ----------

  const repondre = (champ: string, valeur: unknown, titre?: string) => {
    setProfil((p) => noter(p, champ, valeur));
    setDernierChamp(champ);
    const q = QUESTIONS[question];
    if (titre) dire(titre, "vous");
    if (q && q.champ === champ && !q.multiple) suivante();
  };

  const suivante = () => {
    const i = question + 1;
    if (i < QUESTIONS.length) {
      setQuestion(i);
      dire(QUESTIONS[i].texte);
    } else {
      setPhase("recap");
      dire("Voici le profil que j'ai retenu. Indiquez votre prénom et, si vous le souhaitez, votre demande en vos propres termes, puis lancez l'analyse.");
    }
  };

  // ---------- Analyse ----------

  const presenter = useCallback(async (s: SortiePipeline, origine: string) => {
    const complete = await completerGraphiques(s);
    setSortie(complete);
    setDiapo(0);
    setActif(null);
    setPhase("presentation");
    dire(`${origine} Je vous présente le résultat, une diapositive à la fois.`);
  }, [dire]);

  const lancer = useCallback(async (): Promise<string> => {
    if (!complet(profil)) return "Le profil n'est pas complet : il manque une réponse.";
    setPhase("analyse");
    setErreur(null);
    setDebutAnalyse(Date.now());
    dire("Je transmets votre profil aux spécialistes. L'analyse prend environ une minute.");
    try {
      const s = await analyser(profil, demande, prenom);
      await presenter(s, "L'analyse est prête.");
      return "Analyse terminée.";
    } catch (e) {
      setErreur(`${(e as Error).message || "Service injoignable"} (${ADRESSE_API}).`);
      setPhase("erreur");
      dire("Le service d'analyse ne répond pas. Aucun résultat ne vous est présenté à sa place.");
      return "Le service d'analyse est injoignable.";
    }
  }, [profil, demande, prenom, dire, presenter]);

  const demonstration = async (p: Persona) => {
    const s = await chargerSortie(p.id);
    setProfil(s.profil);
    setPrenom(s.profil.prenom ?? p.nom);
    setDemande(s.profil.demande ?? "");
    setQuestion(QUESTIONS.length);
    dire(`Démonstration : ${p.nom}, ${p.age} ans. « ${p.demande} »`, "vous");
    await presenter(s, `Voici l'analyse enregistrée pour ${p.nom} (agents/sorties/${p.id}.json).`);
  };

  // ---------- Questions sur un actif, à tout moment ----------

  const trouverActif = (texte: string): string | null => {
    const t = normaliser(texte);
    const alias: Record<string, string> = { bitcoin: "BTC-USD", ether: "ETH-USD", ethereum: "ETH-USD", or: "GLD" };
    for (const [mot, s] of Object.entries(alias)) if (new RegExp(`\\b${mot}\\b`).test(t)) return s;
    for (const s of Object.keys(univers)) {
      const court = normaliser(s.replace(/\.TO$|-USD$/, ""));
      if (new RegExp(`(^|[^a-z0-9])${court.replace(/[.-]/g, "\\$&")}([^a-z0-9]|$)`).test(t) && court.length >= 2) return s;
      const nom = normaliser(univers[s].nom).split(/[ ,.]/)[0];
      if (nom.length >= 4 && t.includes(nom)) return s;
    }
    return null;
  };

  const questionActif = async (symbole: string) => {
    if (!profil.tolerance_risque || !profil.horizon_annees) {
      dire(`Pour situer ${symbole}, il me faut d'abord votre horizon et votre tolérance au risque.`);
      return;
    }
    setActif({ symbole });
    dire(`J'examine ${symbole} au regard de votre profil.`);
    try {
      const v = await verifierActif(symbole, profil.tolerance_risque, profil.horizon_annees);
      setActif({ symbole, verdict: v });
      dire(v.compatible ? `${symbole} est compatible avec votre profil. En voici les raisons.` : `Voici pourquoi ${symbole} ne correspond pas à votre profil.`);
    } catch (e) {
      setActif({ symbole, erreur: `${(e as Error).message || "Service injoignable"} (${ADRESSE_API}).` });
      dire(`Le service ne répond pas : je ne peux pas examiner ${symbole} pour le moment.`);
    }
  };

  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    const texte = saisie.trim();
    if (!texte) return;
    setSaisie("");
    dire(texte, "vous");
    const s = trouverActif(texte);
    if (s) {
      void questionActif(s);
      return;
    }
    if (phase === "accueil") {
      const q = QUESTIONS[question];
      const t = normaliser(texte);
      const o = q.options.find((x) => normaliser(x.titre).includes(t) || t.includes(normaliser(String(x.valeur))) || (x.detail && normaliser(x.detail).includes(t)));
      if (o) {
        repondre(q.champ, o.valeur);
        if (q.multiple) suivante();
        return;
      }
      if (q.champ === "horizon_annees" || q.champ === "capital_fictif") {
        const n = Number(texte.replace(/\s/g, "").match(/\d+/)?.[0]);
        if (n > 0) { repondre(q.champ, n); return; }
      }
      dire("Je n'ai pas reconnu cette réponse. Choisissez une option au centre, ou reformulez-la.");
      return;
    }
    if (phase === "recap") {
      setDemande(texte);
      dire("Votre demande est notée.");
      return;
    }
    dire("Vous pouvez m'interroger sur un actif, par exemple « Tesla », « TSLA » ou « bitcoin ».");
  };

  // ---------- Outils de la voix ----------

  const afficher = useCallback((id: string): string => {
    const k = diapos.findIndex((d) => d.id === id);
    if (k < 0) return `Diapositive inconnue. Disponibles : ${diapos.map((d) => d.id).join(", ") || "aucune (analyse pas encore faite)"}.`;
    setActif(null);
    setDiapo(k);
    return diapos[k].texte;
  }, [diapos]);

  const api = useRef<EagleApi | null>(null);
  api.current = {
    noterProfil: (champ, valeur) => {
      if (!QUESTIONS.some((q) => q.champ === champ) && champ !== "prenom" && champ !== "demande") return `Champ inconnu : ${champ}.`;
      if (champ === "prenom") setPrenom(String(valeur));
      else if (champ === "demande") setDemande(String(valeur));
      else repondre(champ, valeur);
      // La voix apprend ce qui manque encore, dans l'ordre des questions.
      const apres = noter(profil, champ, valeur);
      const manque = QUESTIONS.filter((q) => q.champ !== champ && (apres[q.champ] === undefined || apres[q.champ] === ""));
      return manque.length
        ? `Noté : ${champ}. Question suivante (${manque[0].champ}) : ${manque[0].texte} Choix : ${manque[0].options.map((o) => `${o.titre} = ${o.valeur}`).join(" ; ")}.`
        : `Noté : ${champ}. Le profil est complet : demande le prénom et la demande en ses mots, puis appelle lancer_analyse.`;
    },
    lancerAnalyse: lancer,
    afficherDiapositive: afficher,
  };
  useEffect(() => {
    onApi?.({
      noterProfil: (c, v) => api.current!.noterProfil(c, v),
      lancerAnalyse: () => api.current!.lancerAnalyse(),
      afficherDiapositive: (id) => api.current!.afficherDiapositive(id),
    });
  }, [onApi]);

  // ---------- Colonne centrale ----------

  let titre = "";
  let justification: React.ReactNode = null;
  let contenu: React.ReactNode = null;
  let navigation: React.ReactNode = null;

  if (actif) {
    contenu = <DiapositiveActif symbole={actif.symbole} verdict={actif.verdict} erreur={actif.erreur} />;
    navigation = <button type="button" className="bouton bouton--secondaire" onClick={() => setActif(null)}>Revenir à la présentation</button>;
  } else if (phase === "accueil") {
    const q = QUESTIONS[question];
    const choisis = ([] as unknown[]).concat(profil[q.champ] ?? []);
    titre = q.texte;
    justification = <>Question {question + 1} sur {QUESTIONS.length}{q.aide ? ` · ${q.aide}` : ""}</>;
    contenu = (
      <div className={`choix choix--${q.options.length}`}>
        {q.options.map((o) => {
          const actifChoix = choisis.includes(o.valeur);
          return (
            <button key={String(o.valeur)} type="button" className={actifChoix ? "choix__bouton choix__bouton--actif" : "choix__bouton"}
              aria-pressed={actifChoix} onClick={() => repondre(q.champ, o.valeur, o.titre)}>
              <span className="choix__titre">{o.titre}</span>
              {o.detail ? <span className="choix__detail">{o.detail}</span> : null}
            </button>
          );
        })}
        {q.multiple ? (
          <button type="button" className={choisis.length === 0 ? "choix__bouton choix__bouton--actif" : "choix__bouton"}
            onClick={() => { setProfil((p) => ({ ...p, [q.champ]: [] })); setDernierChamp(q.champ); }}>
            <span className="choix__titre">{q.aucun}</span>
          </button>
        ) : null}
      </div>
    );
    navigation = (
      <>
        <button type="button" className="bouton bouton--secondaire" disabled={question === 0}
          onClick={() => { setQuestion(question - 1); dire(QUESTIONS[question - 1].texte); }}>Précédente</button>
        {q.multiple ? <button type="button" className="bouton bouton--principal" onClick={suivante}>Continuer</button> : null}
      </>
    );
  } else if (phase === "recap") {
    titre = "Récapitulatif";
    justification = "Vérifiez le profil à droite, indiquez votre prénom et votre demande, puis lancez l'analyse.";
    contenu = (
      <div className="recap">
        <label className="champ-texte">Votre prénom
          <input value={prenom} onChange={(e) => setPrenom(e.target.value)} placeholder="Prénom" />
        </label>
        <label className="champ-texte">Votre demande, en vos propres termes
          <textarea value={demande} onChange={(e) => setDemande(e.target.value)} rows={4}
            placeholder="Par exemple : « Je souhaite placer une part importante sur Tesla. »" />
        </label>
        <p className="recap__note">Le profil sera envoyé à <code>{ADRESSE_API}/analyse</code>. Simulation seulement : aucune transaction réelle.</p>
      </div>
    );
    navigation = (
      <>
        <button type="button" className="bouton bouton--secondaire" onClick={() => { setPhase("accueil"); setQuestion(QUESTIONS.length - 1); }}>Modifier</button>
        <button type="button" className="bouton bouton--principal" disabled={!complet(profil)} onClick={() => void lancer()}>Lancer l&apos;analyse</button>
      </>
    );
  } else if (phase === "analyse") {
    titre = "Les spécialistes travaillent";
    justification = "Chaque agent traite son domaine. La gouvernance vérifie chaque proposition au regard de votre profil avant la présentation.";
    contenu = <DiapositiveAttente debut={debutAnalyse} />;
  } else if (phase === "erreur") {
    titre = "Analyse indisponible";
    justification = erreur;
    contenu = <p className="diapo__texte">Le service du pipeline ne répond pas. Aucun résultat n&apos;est présenté à sa place.</p>;
    navigation = <button type="button" className="bouton bouton--principal" onClick={() => void lancer()}>Relancer</button>;
  } else if (phase === "presentation" && diapos[diapo]) {
    const d = diapos[diapo];
    titre = d.titre;
    justification = d.justification;
    contenu = d.contenu;
    navigation = (
      <>
        <button type="button" className="bouton bouton--secondaire" disabled={diapo === 0} onClick={() => setDiapo(diapo - 1)}>Précédente</button>
        <span className="diapo__compte">{diapo + 1} / {diapos.length}</span>
        <button type="button" className="bouton bouton--principal" disabled={diapo === diapos.length - 1} onClick={() => setDiapo(diapo + 1)}>Suivante</button>
      </>
    );
  }

  const enCours = phase === "analyse" || Boolean(actif && !actif.verdict && !actif.erreur);
  const lignesProfil: [string, string, string | undefined][] = [
    ["prenom", "Prénom", prenom || undefined],
    ["horizon_annees", "Horizon", profil.horizon_annees ? formaterHorizon(profil.horizon_annees) : undefined],
    ["objectif", "Objectif", profil.objectif ? majuscule(profil.objectif) : undefined],
    ["tolerance_risque", "Tolérance", profil.tolerance_risque ? majuscule(profil.tolerance_risque) : undefined],
    ["connaissance", "Connaissance", profil.connaissance ? majuscule(profil.connaissance) : undefined],
    ["preferences", "Préférences", question > 4 || profil.preferences?.length ? (profil.preferences?.join(", ") || "Rien de particulier") : undefined],
    ["exclusions", "Exclusions", question > 5 || profil.exclusions?.length ? (profil.exclusions?.join(", ") || "Rien") : undefined],
    ["centres_interet", "Intérêts", question > 6 || profil.centres_interet?.length ? (profil.centres_interet?.join(", ") || "Aucun") : undefined],
    ["capital_fictif", "Capital fictif", profil.capital_fictif ? formaterMontant(profil.capital_fictif, profil.devise ?? "CAD") : undefined],
    ["demande", "Demande", demande ? `« ${demande} »` : undefined],
  ];

  return (
    <FournisseurChiffres valeur={ctx}>
      <div className="eagle">
        <aside className="eagle__gauche">
          <div className="eagle__identite">
            <Aigle taille={120} actif={enCours} />
            <div>
              <h1 className="eagle__nom">Eagle</h1>
              <p className={`eagle__etat eagle__etat--${phase}`}><span aria-hidden="true" />{actif ? `Question sur ${actif.symbole}` : ETAT[phase]}</p>
            </div>
          </div>
          <Voix api={api} dire={dire} />
          <div className="transcription" aria-live="polite" aria-label="Transcription">
            {transcription.map((r, i) => (
              <p key={i} className={`replique replique--${r.qui}`}>
                <span className="replique__qui">{r.qui === "eagle" ? "Eagle" : prenom || "Vous"}</span>
                {typo(r.texte)}
              </p>
            ))}
          </div>
          <p className="eagle__mention">Simulation seulement : aucune transaction réelle.</p>
        </aside>

        <main className="eagle__centre">
          {phase === "presentation" && !actif ? (
            <ol className="diapo__plan" aria-label="Diapositives">
              {diapos.map((d, i) => (
                <li key={d.id}><button type="button" className={i === diapo ? "diapo__point diapo__point--actif" : "diapo__point"} onClick={() => setDiapo(i)}>{d.court}</button></li>
              ))}
            </ol>
          ) : null}
          <section className="diapo" key={actif ? `actif-${actif.symbole}` : `${phase}-${question}-${diapo}`}>
            {titre ? <h2 className="diapo__titre">{typo(titre)}</h2> : null}
            {justification ? <p className="diapo__justification">{typeof justification === "string" ? typo(justification) : justification}</p> : null}
            <div className="diapo__contenu">{contenu}</div>
          </section>
          <div className="diapo__nav">{navigation}</div>
          <form className="champ champ--envoi" onSubmit={envoyer}>
            <label className="sr-only" htmlFor="saisie">Écrire à Eagle</label>
            <input id="saisie" value={saisie} onChange={(e) => setSaisie(e.target.value)} autoComplete="off"
              placeholder={phase === "accueil" ? "Saisissez votre réponse, ou interrogez-moi sur un actif : « et Tesla ? »" : "Interrogez-moi sur un actif : « Tesla », « TSLA », « bitcoin »…"} />
            <button type="submit" className="champ__envoyer" aria-label="Envoyer">→</button>
          </form>
        </main>

        <aside className="eagle__droite">
          <h2 className="profil-direct__titre">Votre profil <span>en direct</span></h2>
          <dl className="profil-direct">
            {lignesProfil.map(([cle, nom, valeur]) => (
              <div key={cle} className={`profil-direct__ligne${valeur ? " profil-direct__ligne--rempli" : ""}${dernierChamp === cle ? " profil-direct__ligne--nouveau" : ""}`}>
                <dt>{nom}</dt>
                <dd>{valeur ? typo(valeur) : "…"}</dd>
              </div>
            ))}
          </dl>
          {sortie ? (
            <button type="button" className="bouton bouton--secondaire" onClick={() => window.open(`/rapport?persona=${sortie.scenario}`, "_blank")}
              disabled={!PERSONAS.some((p) => p.id === sortie.scenario)}>Exporter le dossier</button>
          ) : null}
          <div className="demos">
            <p className="demos__titre">Démonstration</p>
            {PERSONAS.map((p) => (
              <button key={p.id} type="button" className="demo" onClick={() => void demonstration(p)}>
                <strong>{p.nom}, {p.age} ans</strong>
                <span>{typo(`« ${p.demande} »`)}</span>
              </button>
            ))}
          </div>
        </aside>
        {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
      </div>
    </FournisseurChiffres>
  );
}
