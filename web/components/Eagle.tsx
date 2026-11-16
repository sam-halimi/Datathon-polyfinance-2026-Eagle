"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Aigle } from "./Aigle";
import { Avatar, FournisseurDa } from "./Da";
import type { DirectionArtistique } from "@/lib/da";
import { Voix } from "./Voix";
import { FocusCtx, type Focus } from "./Focus";
import { propositions, vueSur } from "@/lib/portefeuilles";
import { FicheReference, FournisseurChiffres, typo } from "./Chiffres";
import { construireDiapositives, DiapositiveActif, DiapositiveAttente, type Diapositive } from "./Diapositives";
import { analyser, ADRESSE_API, COMMANDE_SERVEUR, ErreurService, SERVICE_LOCAL, verifierActif, type VerdictActif } from "@/lib/api";
import { formaterHorizon, formaterMontant, majuscule } from "@/lib/format";
import { chargerSortie, CLE_DOSSIER, PERSONAS, type Persona } from "@/lib/personas";
import { complet, estRepondue, listeDite, noter, PROFIL_VIDE, QUESTIONS } from "@/lib/questions";
import { Choix, Curseur } from "./Questions";
import { chargerUnivers, completerGraphiques } from "@/lib/repartition";
import { lireEventail } from "@/lib/scenarios";
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

/** Envoyée quand la personne n'écrit pas de demande : le serveur en exige une. Affichée telle quelle. */
const DEMANDE_PAR_DEFAUT = "Aucune demande particulière : un portefeuille simulé adapté à mon profil.";

function normaliser(t: string) {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export type EagleApi = {
  noterProfil: (champ: string, valeur: unknown) => string;
  lancerAnalyse: () => Promise<string>;
  /** `element` : ce que la présentation met en avant sur la diapositive (part d'un camembert, ligne, actif). */
  afficherDiapositive: (id: string, element?: string) => string;
};

type Props = {
  onApi?: (api: EagleApi) => void;
  da?: DirectionArtistique | null;
  /** Compte connecté (site déployé) : identifiant affiché et déconnexion. */
  compte?: { identifiant: string; deconnecter: () => void } | null;
  /** Rouvre la présentation du début (components/Entree.tsx). */
  ouvrirModeEmploi?: () => void;
  /** Choix fait à la fin de la présentation : son propre profil, ou l'un des trois cas du datathon. */
  depart?: ({ type: "profil" } | { type: "cas"; id: Persona["id"] }) & { n: number } | null;
};

export function Eagle({ onApi, da = null, compte = null, ouvrirModeEmploi, depart = null }: Props) {
  const [voixParle, setVoixParle] = useState(false);
  // Appel vocal en cours : l'agent dit lui-même chaque question, l'écran ne la répète pas dans la transcription.
  const voixEnLigne = useRef(false);
  const surLigne = useCallback((enLigne: boolean) => { voixEnLigne.current = enLigne; }, []);
  const [phase, setPhase] = useState<Phase>("accueil");
  const [question, setQuestion] = useState(0);
  const [profil, setProfil] = useState<Partial<Profil>>(PROFIL_VIDE);
  const [dernierChamp, setDernierChamp] = useState<string | null>(null);
  const [prenom, setPrenom] = useState("");
  const [demande, setDemande] = useState("");
  const [brute, setSortie] = useState<SortiePipeline | null>(null);
  // Proposition affichée quand ce n'est pas celle retenue par la gouvernance ; null = la retenue.
  const [vueId, setVueId] = useState<string | null>(null);
  // Ce que la présentation met en avant (voix) : part de camembert, ligne, actif.
  const [focus, setFocus] = useState<Focus>(null);
  // Persona de démonstration affiché ; null pour une analyse en direct.
  const [demo, setDemo] = useState<Persona["id"] | null>(null);
  const [diapo, setDiapoBrut] = useState(0);
  // Sens de la dernière navigation, pour faire glisser la diapositive du bon côté.
  const [sens, setSens] = useState<"avant" | "arriere">("avant");
  const setDiapo = useCallback((k: number) => {
    setDiapoBrut((avant) => { setSens(k < avant ? "arriere" : "avant"); return k; });
  }, []);
  const [actif, setActif] = useState<{ symbole: string; verdict?: VerdictActif; erreur?: string } | null>(null);
  const [transcription, setTranscription] = useState<Replique[]>([
    { qui: "eagle", texte: "Bonjour, je suis Eagle, votre assistant. Je vais établir avec vous un portefeuille simulé et vous détailler chacun de ses chiffres. Aucune transaction réelle n'est effectuée. Commençons par votre profil." },
    { qui: "eagle", texte: QUESTIONS[0].texte },
  ]);
  const [saisie, setSaisie] = useState("");
  const [fiche, setFiche] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  // Serveur injoignable : on donne la commande pour le lancer. Serveur qui répond par une erreur :
  // il tourne déjà, on renvoie à son terminal et à la vérification des clés.
  const [injoignable, setInjoignable] = useState(false);
  const [debutAnalyse, setDebutAnalyse] = useState(0);
  const [univers, setUnivers] = useState<Record<string, { nom: string }>>({});

  useEffect(() => { chargerUnivers().then((u) => setUnivers(u.actifs)); }, []);

  const dire = useCallback((texte: string, qui: Replique["qui"] = "eagle") => {
    setTranscription((t) => [...t.slice(-200), { qui, texte }]);
  }, []);
  // La transcription défile : elle suit le dernier message, et on peut remonter lire le début.
  const filTranscription = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const f = filTranscription.current;
    if (f) f.scrollTop = f.scrollHeight;
  }, [transcription]);

  // `brute` : la réponse du pipeline. `sortie` : la même, vue sur la proposition choisie (lib/portefeuilles.ts).
  const sortie = useMemo(() => (brute && vueId ? vueSur(brute, vueId) : brute), [brute, vueId]);
  const diapos = useMemo<Diapositive[]>(() => (sortie ? construireDiapositives(sortie) : []), [sortie]);
  const chiffres = useMemo<Record<string, Reference>>(() => ({
    ...(sortie?.chiffres ?? {}),
    ...(sortie ? lireEventail(sortie)?.chiffres ?? {} : {}),
    ...(actif?.verdict?.chiffres ?? {}),
  }), [sortie, actif]);
  // Lexique au survol aux niveaux 1 et 2 seulement (registre renvoyé par le pipeline).
  const registre = sortie?.explication?.registre;
  const lexique = registre && registre.niveau <= 2 ? sortie?.explication?.lexique ?? [] : [];
  const ctx = useMemo(() => ({ chiffres, ouvrir: setFiche, lexique }), [chiffres, lexique]);

  // ---------- Accueil ----------

  // Questions auxquelles la personne a répondu. Une liste vide (« rien de particulier ») est une
  // réponse : sans ce suivi, l'outil vocal croyait les trois questions à liste déjà traitées.
  const repondues = useRef<Set<string>>(new Set());
  // Minuterie de l'avance automatique après une réponse dictée (le temps de voir la case se cocher).
  const avance = useRef<number | undefined>(undefined);

  const repondre = (champ: string, valeur: unknown, titre?: string) => {
    repondues.current.add(champ);
    setProfil((p) => noter(p, champ, valeur));
    setDernierChamp(champ);
    const q = QUESTIONS[question];
    if (titre) dire(titre, "vous");
    if (q && q.champ === champ && q.type === "choix" && !q.multiple) suivante();
  };

  const suivante = () => {
    setSens("avant");
    // Quitter une question, c'est y avoir répondu, même par « rien de particulier » (liste vide).
    if (QUESTIONS[question]) repondues.current.add(QUESTIONS[question].champ);
    const i = question + 1;
    if (i < QUESTIONS.length) {
      setQuestion(i);
      if (!voixEnLigne.current) dire(QUESTIONS[i].texte);
    } else {
      setPhase("recap");
      if (!voixEnLigne.current) dire("Voici le profil que j'ai retenu. Indiquez votre prénom et, si vous le souhaitez, votre demande en vos propres termes, puis lancez l'analyse.");
    }
  };

  // ---------- Analyse ----------

  const presenter = useCallback(async (s: SortiePipeline, origine: string) => {
    const complete = await completerGraphiques(s);
    setSortie(complete);
    setVueId(null);
    setFocus(null);
    setDiapo(0);
    setActif(null);
    setPhase("presentation");
    dire(`${origine} Je vous présente le résultat, une diapositive à la fois.`);
  }, [dire]);

  // Une seule analyse à la fois : un second appel (voix qui relance, double clic) rejoint celle en cours
  // au lieu d'en démarrer une autre. Le 16 novembre, huit relances vocales en avaient lancé plusieurs de front.
  const analyseEnCours = useRef<Promise<string> | null>(null);
  const lancerUneFois = useCallback(async (): Promise<string> => {
    if (!complet(profil)) return "Le profil n'est pas complet : il manque une réponse.";
    setPhase("analyse");
    setErreur(null);
    setDebutAnalyse(Date.now());
    dire("Je transmets votre profil aux spécialistes. L'analyse prend de une à trois minutes.");
    try {
      const s = await analyser(profil, demande.trim() || DEMANDE_PAR_DEFAUT, prenom);
      setDemo(null);
      await presenter(s, "L'analyse de votre profil est prête.");
      return "Analyse terminée.";
    } catch (e) {
      const message = e instanceof ErreurService ? e.message : `L'analyse a échoué : ${(e as Error).message}.`;
      setErreur(message);
      setInjoignable(e instanceof ErreurService ? e.injoignable : false);
      setPhase("erreur");
      dire(message);
      return message;
    }
  }, [profil, demande, prenom, dire, presenter]);
  const lancer = useCallback((): Promise<string> => {
    if (!analyseEnCours.current) analyseEnCours.current = lancerUneFois().finally(() => { analyseEnCours.current = null; });
    return analyseEnCours.current;
  }, [lancerUneFois]);

  const demonstration = async (p: Persona) => {
    const s = await chargerSortie(p.id);
    setProfil(s.profil);
    setPrenom(s.profil.prenom ?? p.nom);
    setDemande(s.profil.demande ?? "");
    setQuestion(QUESTIONS.length);
    setDemo(p.id);
    dire(`Démonstration : ${p.nom}, ${p.age} ans. « ${p.demande} »`, "vous");
    await presenter(s, `Voici l'analyse enregistrée pour ${p.nom} (agents/sorties/${p.id}.json).`);
  };

  // Choix de la fin de la présentation : ouvrir un cas du datathon, ou repartir sur ses propres réponses.
  useEffect(() => {
    if (!depart) return;
    if (depart.type === "cas") {
      const p = PERSONAS.find((x) => x.id === depart.id);
      if (p) void demonstration(p);
    } else if (demo) {
      // On quitte un cas pour créer son propre profil : questions remises à zéro.
      setDemo(null); setSortie(null); setVueId(null); setActif(null); setProfil(PROFIL_VIDE); setPrenom(""); setDemande("");
      repondues.current = new Set(); setQuestion(0); setPhase("accueil");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depart?.n]);

  // Dossier imprimable. Persona de démonstration : sa sortie enregistrée. Analyse en direct :
  // la réponse du pipeline, déposée dans le stockage local du navigateur pour la page /rapport.
  const exporter = () => {
    if (!sortie) return;
    if (demo && !vueId) { window.open(`/rapport/?persona=${demo}`, "_blank"); return; }
    try {
      window.localStorage.setItem(CLE_DOSSIER, JSON.stringify(sortie));
      window.open("/rapport/?source=analyse", "_blank");
    } catch {
      dire("Le navigateur refuse d'enregistrer le dossier (stockage local indisponible). L'analyse reste affichée ici.");
    }
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
      dire(v.compatible ? `${symbole} est compatible avec votre profil. En voici les raisons.`
        : v.statut === "à plafonner" ? `${symbole} ne convient qu'en petite position pour votre profil. En voici les raisons.`
        : v.statut === "inconnu" ? `${symbole} n'est pas dans les tables d'actifs : je ne donne aucun chiffre sans donnée.`
        : `Voici pourquoi ${symbole} ne correspond pas à votre profil.`);
    } catch (e) {
      setActif({ symbole, erreur: e instanceof ErreurService ? e.message : (e as Error).message });
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
      if (q.type === "curseur") {
        const n = Number(texte.replace(/\s/g, "").match(/\d+/)?.[0]);
        if (n >= q.min && n <= q.max) { repondre(q.champ, n); suivante(); return; }
        dire(`Indiquez une valeur entre ${q.min} et ${q.max}, ou utilisez le curseur.`);
        return;
      }
      const o = q.options.find((x) => normaliser(x.titre).includes(t) || t.includes(normaliser(String(x.valeur))) || (x.detail && normaliser(x.detail).includes(t)));
      if (o) {
        repondre(q.champ, o.valeur);
        if (q.multiple) suivante();
        return;
      }
      if (q.champ === "horizon_annees") {
        const n = Number(texte.replace(/\s/g, "").match(/\d+/)?.[0]);
        if (n > 0) { repondre(q.champ, n); return; }
      }
      if (q.multiple && q.libre) { repondre(q.champ, texte); return; }
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

  /** Passe à la proposition suivante (retenue -> autres -> retenue). Renvoie le texte que la voix lit. */
  const autreProposition = useCallback((): string => {
    if (!brute) return "Aucune analyse à l'écran : il n'y a pas encore de proposition.";
    const ids = propositions(brute);
    if (ids.length < 2) return "Le pipeline n'a retenu qu'une proposition pour ce profil : il n'y en a pas d'autre à montrer. Pour un résultat différent, il faut modifier une réponse du profil.";
    const suivant = ids[(ids.indexOf(vueId ?? ids[0]) + 1) % ids.length];
    setActif(null);
    setFocus(null);
    setDiapo(0);
    if (suivant === ids[0]) {
      setVueId(null);
      dire(`Retour à la proposition ${ids[0]}, celle que la gouvernance a retenue.`);
      return `Retour à la proposition ${ids[0]}, celle que la gouvernance a retenue. Toutes les propositions ont été montrées.`;
    }
    setVueId(suivant);
    dire(`Voici la proposition ${suivant}. La gouvernance avait retenu la proposition ${ids[0]}.`);
    return construireDiapositives(vueSur(brute, suivant)).find((d) => d.id === "alternative")?.texte ?? `Proposition ${suivant} affichée.`;
  }, [brute, vueId, dire]);

  const afficher = useCallback((id: string, element?: string): string => {
    if (id === "alternative") return autreProposition();
    const k = diapos.findIndex((d) => d.id === id);
    if (k < 0) return `Diapositive inconnue. Disponibles : ${diapos.map((d) => d.id).join(", ") || "aucune (analyse pas encore faite)"}.`;
    setActif(null);
    setDiapo(k);
    // La voix montre ce dont elle parle : la part, la ligne ou l'actif s'allume à l'écran.
    const e = (element ?? "").trim();
    setFocus((f) => (e ? { element: e, n: (f?.n ?? 0) + 1 } : null));
    return e ? `« ${e} » est mis en avant sur la diapositive ${id}. ${diapos[k].texte}` : diapos[k].texte;
  }, [diapos, autreProposition]);

  /** Rouvre les questions avec les réponses déjà données : on corrige, puis on relance l'analyse. */
  const modifierProfil = () => {
    setActif(null);
    setPhase("accueil");
    setSens("arriere");
    setQuestion(0);
    dire("Reprenons votre profil : vos réponses sont conservées. Modifiez celles que vous souhaitez, puis relancez l'analyse.");
  };

  const api = useRef<EagleApi | null>(null);
  api.current = {
    noterProfil: (champ, valeur) => {
      if (!QUESTIONS.some((q) => q.champ === champ) && champ !== "prenom" && champ !== "demande") return `Champ inconnu : ${champ}.`;
      if (champ === "prenom") setPrenom(String(valeur));
      else if (champ === "demande") setDemande(String(valeur));
      else {
        const k = QUESTIONS.findIndex((q) => q.champ === champ);
        const q = QUESTIONS[k];
        if (q.type === "choix" && q.multiple) valeur = listeDite(q, profil[q.champ] as string[] | undefined, valeur);
        repondues.current.add(champ);
        setProfil((p) => noter(p, champ, valeur));
        setDernierChamp(champ);
        if (phase === "accueil") {
          // L'écran montre la question dont on parle, avec la réponse cochée, puis avance de lui-même.
          setSens(k < question ? "arriere" : "avant");
          setQuestion(k);
          window.clearTimeout(avance.current);
          avance.current = window.setTimeout(() => {
            const suivant = QUESTIONS.findIndex((x, i) => i > k && !repondues.current.has(x.champ));
            setSens("avant");
            if (suivant >= 0) setQuestion(suivant);
            else if (QUESTIONS.every((x) => repondues.current.has(x.champ))) setPhase("recap");
          }, 1800);
        }
      }
      // La voix apprend ce qui manque encore, dans l'ordre des questions.
      const apres = noter(profil, champ, valeur);
      const manque = QUESTIONS.filter((q) => q.champ !== champ && (q.type === "choix" && q.multiple
        ? !repondues.current.has(q.champ)
        : apres[q.champ] === undefined || apres[q.champ] === ""));
      const m = manque[0];
      const choix = !m ? "" : m.type === "choix"
        ? `Choix : ${m.options.map((o) => `${o.titre} = ${o.valeur}`).join(" ; ")}${m.multiple ? " (plusieurs réponses possibles, ou une réponse libre)" : ""}.`
        : m.crans
          ? `Curseur de ${m.min} à ${m.max} : ${Object.entries(m.crans).map(([k, t]) => `${k} = « ${t} »`).join(" ; ")}.`
          : `Curseur de montant, de ${m.min} à ${m.max} dollars canadiens, par pas de ${m.pas}.`;
      return m
        ? `Noté : ${champ}. Question suivante (${m.champ}) : ${m.texte} ${choix}`
        : `Noté : ${champ}. Le profil est complet : demande le prénom et la demande en ses mots, puis appelle lancer_analyse.`;
    },
    lancerAnalyse: lancer,
    afficherDiapositive: afficher,
  };
  useEffect(() => {
    onApi?.({
      noterProfil: (c, v) => api.current!.noterProfil(c, v),
      lancerAnalyse: () => api.current!.lancerAnalyse(),
      afficherDiapositive: (id, element) => api.current!.afficherDiapositive(id, element),
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
    contenu = q.type === "curseur" ? (
      <Curseur q={q} valeur={profil[q.champ] as number | undefined} devise={profil.devise ?? "CAD"}
        changer={(v) => { setProfil((p) => noter(p, q.champ, v)); setDernierChamp(q.champ); }} />
    ) : (
      <Choix q={q} choisis={choisis} choisir={(v, t) => repondre(q.champ, v, t)}
        vider={() => { setProfil((p) => ({ ...p, [q.champ]: [] })); setDernierChamp(q.champ); }} />
    );
    navigation = (
      <>
        <button type="button" className="bouton bouton--secondaire" disabled={question === 0}
          onClick={() => { setSens("arriere"); setQuestion(question - 1); dire(QUESTIONS[question - 1].texte); }}>Précédente</button>
        {q.type === "curseur" ? (
          <button type="button" className="bouton bouton--principal"
            onClick={() => { if (!estRepondue(profil, q)) { setProfil((p) => noter(p, q.champ, q.depart)); setDernierChamp(q.champ); } suivante(); }}>Valider</button>
        ) : q.multiple ? <button type="button" className="bouton bouton--principal" onClick={suivante}>Continuer</button> : null}
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
            placeholder={`Facultatif. Par exemple : « Je souhaite placer une part importante sur Tesla. » Sans demande, le service reçoit : « ${DEMANDE_PAR_DEFAUT} »`} />
        </label>
        <p className="recap__note">{SERVICE_LOCAL ? <>Le profil sera envoyé à <code>{ADRESSE_API}/analyse</code>. </> : "Le profil sera transmis au service d'analyse d'Eagle. "}Simulation seulement : aucune transaction réelle.</p>
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
    justification = "Aucun portefeuille n'est affiché à la place du vôtre.";
    contenu = (
      <div className="panne">
        <p className="diapo__manque">{erreur ? typo(erreur) : null}</p>
        {!SERVICE_LOCAL ? (
          // Site en ligne : la personne n'a rien à installer ni à vérifier. Son profil est conservé.
          <p className="panne__aide">Votre profil est conservé à droite. Le bouton « Relancer » reprend l&apos;analyse avec les mêmes réponses.</p>
        ) : injoignable ? (
          <>
            <p className="panne__aide">Commande, à lancer à la racine du dépôt :</p>
            <pre className="panne__commande"><code>{COMMANDE_SERVEUR}</code></pre>
          </>
        ) : (
          <>
            <p className="panne__aide">Le serveur répond : le détail est dans son terminal. Pour vérifier les clés (Bedrock, données), à la racine du dépôt :</p>
            <pre className="panne__commande"><code>python -m tools.verifier_cles</code></pre>
          </>
        )}
        {SERVICE_LOCAL ? <p className="panne__aide">Adresse appelée : <code>{ADRESSE_API}/analyse</code> (réglable par NEXT_PUBLIC_API_URL).</p> : null}
      </div>
    );
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
  // État de l'avatar (docs/da-eagle.md) : réfléchit pendant un calcul, parle quand la voix émet, écoute sinon.
  const etatAvatar = enCours ? "reflechit" : voixParle ? "parle" : "ecoute";
  const resultat = phase === "presentation" || Boolean(actif?.verdict);
  const lignesProfil: [string, string, string | undefined][] = [
    ["prenom", "Prénom", prenom || undefined],
    ["horizon_annees", "Horizon", profil.horizon_annees ? formaterHorizon(profil.horizon_annees) : undefined],
    ["objectif", "Objectif", profil.objectif ? majuscule(profil.objectif) : undefined],
    ["tolerance_risque", "Tolérance", profil.tolerance_risque ? majuscule(profil.tolerance_risque) : undefined],
    ["connaissance_niveau", "Connaissance", profil.connaissance_niveau
      ? `Niveau ${profil.connaissance_niveau} sur 5`
      : profil.connaissance ? majuscule(profil.connaissance) : undefined],
    ["preferences", "Préférences", question > 4 || profil.preferences?.length ? (profil.preferences?.join(", ") || "Rien de particulier") : undefined],
    ["exclusions", "Exclusions", question > 5 || profil.exclusions?.length ? (profil.exclusions?.join(", ") || "Rien") : undefined],
    ["centres_interet", "Intérêts", question > 6 || profil.centres_interet?.length ? (profil.centres_interet?.join(", ") || "Aucun") : undefined],
    ["capital_fictif", "Capital fictif", profil.capital_fictif ? formaterMontant(profil.capital_fictif, profil.devise ?? "CAD") : undefined],
    ["demande", "Demande", demande ? `« ${demande} »` : phase === "accueil" || phase === "recap" ? undefined : "Aucune demande particulière"],
  ];

  return (
    <FournisseurDa da={da}>
    <FournisseurChiffres valeur={ctx}>
    <FocusCtx.Provider value={focus}>
      <div className="eagle">
        <aside className="eagle__gauche">
          {da?.logoHorizontal ? (
            <h1 className="eagle__logo-ligne"><img className="eagle__logo" src={da.logoHorizontal} alt="Eagle" /></h1>
          ) : <h1 className="eagle__nom">Eagle</h1>}
          <div className="eagle__identite">
            <Avatar etat={etatAvatar} taille={132} repli={<Aigle taille={120} actif={enCours} />} />
            <p className={`eagle__etat eagle__etat--${phase}`}><span aria-hidden="true" />{actif ? `Question sur ${actif.symbole}` : ETAT[phase]}</p>
          </div>
          <Voix api={api} dire={dire} surParole={setVoixParle} surLigne={surLigne} reflechit={enCours} />
          <div className="transcription" ref={filTranscription} tabIndex={0} aria-live="polite" aria-label="Transcription, défilement vertical">
            {transcription.map((r, i) => (
              <p key={i} className={`replique replique--${r.qui}`}>
                <span className="replique__qui">{r.qui === "eagle" ? "Eagle" : prenom || "Vous"}</span>
                {typo(r.texte)}
              </p>
            ))}
          </div>
          <p className={resultat ? "eagle__mention eagle__mention--resultat" : "eagle__mention"}>
            {resultat ? "Simulation, pas un conseil financier. Aucune transaction réelle." : "Simulation seulement : aucune transaction réelle."}
          </p>
        </aside>

        <main className="eagle__centre">
          {phase === "presentation" && !actif ? (
            <div className="diapo__haut">
            <ol className="diapo__plan" aria-label="Diapositives">
              {diapos.map((d, i) => (
                <li key={d.id}><button type="button" className={i === diapo ? "diapo__point diapo__point--actif" : "diapo__point"} onClick={() => setDiapo(i)}>{d.court}</button></li>
              ))}
            </ol>
            <p className="registre" tabIndex={0}>
              {registre ? <>Registre {registre.nom} · niveau {registre.niveau} sur 5</> : "Registre : information manquante"}
              <span className="terme__bulle registre__bulle" role="tooltip">
                {registre ? typo(registre.description) : "La réponse du pipeline ne contient pas de registre de langage (format v2)."}
                {registre && registre.niveau <= 2 ? (lexique.length ? ` ${lexique.length} terme${lexique.length > 1 ? "s" : ""} défini${lexique.length > 1 ? "s" : ""} au survol.` : " Lexique : information manquante.") : null}
              </span>
            </p>
            </div>
          ) : null}
          <section className={`diapo diapo--${sens}`} key={actif ? `actif-${actif.symbole}` : `${phase}-${question}-${diapo}`}>
            {titre ? <h2 className={phase === "accueil" && !actif ? "diapo__titre eg-title-question" : "diapo__titre eg-title-2"}>{typo(titre)}</h2> : null}
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
          {compte || ouvrirModeEmploi ? (
            <div className="eagle__compte">
              {ouvrirModeEmploi ? <button type="button" className="eagle__lien" onClick={ouvrirModeEmploi}>Mode d&apos;emploi</button> : null}
              {compte ? (
                <>
                  <span className="eagle__identifiant" title="Compte connecté">{compte.identifiant}</span>
                  <button type="button" className="eagle__lien" onClick={compte.deconnecter}>Se déconnecter</button>
                </>
              ) : null}
            </div>
          ) : null}
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
            <div className="eagle__actions">
              {phase === "presentation" && brute && propositions(brute).length > 1 ? (
                <button type="button" className="bouton bouton--secondaire" onClick={() => void autreProposition()}
                  title="Le pipeline a vérifié plusieurs propositions : voyez les autres, et ce que votre profil impose à toutes.">
                  {vueId ? `Proposition ${vueId} affichée · suivante` : "Voir une autre proposition"}
                </button>
              ) : null}
              {phase === "presentation" ? (
                <button type="button" className="bouton bouton--secondaire" onClick={modifierProfil}>Modifier mon profil</button>
              ) : null}
              <button type="button" className="bouton bouton--secondaire" onClick={exporter}>Exporter le dossier</button>
            </div>
          ) : null}
          <div className="demos">
            <p className="demos__titre">Cas du datathon</p>
            {PERSONAS.map((p) => (
              <button key={p.id} type="button" className={demo === p.id ? "demo demo--actif" : "demo"} onClick={() => void demonstration(p)}>
                <img className="demo__avatar" src={`/da/personas/${p.id}.svg`} alt="" width={40} height={40} />
                <span className="demo__textes">
                  <strong>{p.nom}, {p.age} ans</strong>
                  <span>{typo(`« ${p.demande} »`)}</span>
                </span>
              </button>
            ))}
          </div>
        </aside>
        {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
      </div>
    </FocusCtx.Provider>
    </FournisseurChiffres>
    </FournisseurDa>
  );
}
