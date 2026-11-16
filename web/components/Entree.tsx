"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Eagle } from "./Eagle";
import { ecouterDeconnexion } from "@/lib/api";
import {
  COMPTES_ACTIFS, fermerSession, lireSession, ouvrirSession, REGLE_IDENTIFIANT, REGLE_MOT_DE_PASSE, type Session,
} from "@/lib/compte";
import type { DirectionArtistique } from "@/lib/da";

// L'entrée du site : une présentation en cinq diapositives (ce qu'est Eagle, comment s'en servir),
// puis, sur le site déployé, la connexion à un compte, puis le tableau de bord (components/Eagle.tsx).
// Le tableau de bord reste monté dès qu'on y est entré : rouvrir le mode d'emploi ou se reconnecter
// après l'expiration du jeton ne fait pas perdre le profil ni l'analyse en cours.

const CLE_INTRO = "eagle:intro-vue";
const CLE_COMPTE_CONNU = "eagle:compte-connu";

type Visuel = { titre: string; lignes: string[]; numerote?: boolean };
type Diapo = { surtitre: string; titre: string; texte: string; points: string[]; visuel: Visuel };

const DIAPOS: Diapo[] = [
  {
    surtitre: "Bienvenue",
    titre: "Eagle établit avec vous un portefeuille simulé",
    texte: "Vous décrivez votre situation, des agents spécialisés construisent une proposition, et chaque chiffre affiché renvoie au calcul qui l'a produit.",
    points: [
      "Simulation uniquement : aucune somme n'est investie, aucune transaction n'est passée.",
      "Aucune prévision de rendement : les données passées décrivent, elles ne promettent rien.",
      "Eagle est un assistant : il explique et vérifie, la décision reste la vôtre.",
    ],
    visuel: { titre: "Ce que vous obtenez", lignes: ["Un portefeuille simulé adapté à votre profil", "Les raisons de chaque ligne, avec leurs sources", "Les contrôles effectués et les limites de l'exercice"] },
  },
  {
    surtitre: "Étape 1",
    titre: "Votre profil, en huit questions",
    texte: "Répondez à l'écran, ou à voix haute avec le bouton « Démarrer l'appel ». Le profil se remplit en direct, à droite.",
    points: [
      "Une question à la fois ; le bouton « Précédente » permet de revenir en arrière.",
      "Si vous hésitez, dites-le : Eagle explique chaque choix avec un exemple concret.",
      "Le montant se règle au curseur ou se saisit au dollar près.",
    ],
    visuel: { titre: "Les huit questions", numerote: true, lignes: ["Horizon de placement", "Objectif", "Réaction à une baisse", "Connaissance des marchés", "Préférences", "Exclusions", "Thèmes d'intérêt", "Montant à simuler"] },
  },
  {
    surtitre: "Étape 2",
    titre: "Sept agents analysent votre profil",
    texte: "Après le récapitulatif, lancez l'analyse. Elle prend de une à trois minutes ; l'écran indique ce que fait chaque agent.",
    points: [
      "Trois spécialistes mesurent le risque, les taux et les critères ESG, chacun dans son domaine.",
      "La gouvernance vérifie chaque proposition contre votre profil, et la renvoie si elle ne passe pas.",
      "Si une demande dépasse votre profil, Eagle le dit et la plafonne au lieu d'acquiescer.",
    ],
    visuel: { titre: "Les agents, dans l'ordre", numerote: true, lignes: ["Orchestrateur", "ESG et qualité", "Marché et risque", "Macro et taux", "Constructeur", "Gouvernance", "Explication"] },
  },
  {
    surtitre: "Étape 3",
    titre: "Neuf diapositives pour comprendre le résultat",
    texte: "Le résultat se lit une diapositive à la fois, avec les boutons « Suivante » et « Précédente » ou les onglets du haut.",
    points: [
      "Touchez un chiffre souligné : sa fiche montre l'outil, les paramètres, la période et la source.",
      "Une carte plus longue que l'écran défile : rien n'est masqué.",
      "« Scénarios » montre un éventail de trajectoires possibles, jamais une prévision.",
    ],
    visuel: { titre: "Les diapositives", numerote: true, lignes: ["Démarche des agents", "Votre demande", "Pourquoi ce portefeuille", "Répartition", "Lignes", "Cours commentés", "Scénarios", "Vérifications", "Limites"] },
  },
  {
    surtitre: "À tout moment",
    titre: "Interrogez, exportez, comparez",
    texte: "Le champ en bas de l'écran reste disponible pendant tout le parcours.",
    points: [
      "Écrivez le nom d'un actif, par exemple « et Tesla ? » : Eagle dit s'il est compatible avec votre profil, et pourquoi.",
      "« Exporter le dossier » ouvre une version imprimable, à enregistrer en PDF.",
      "Trois démonstrations (Robert, Amira, Mateo) montrent un résultat complet sans attendre.",
    ],
    visuel: { titre: "Bon à savoir", lignes: ["Ce mode d'emploi se rouvre depuis le tableau de bord", "La voix est facultative : tout se fait aussi par écrit", "Sans micro ou sans réseau audio, l'écrit prend le relais"] },
  },
];

function Presentation({ da, terminer, suite }: { da: DirectionArtistique | null; terminer: () => void; suite: string }) {
  const [i, setI] = useState(0);
  const d = DIAPOS[i];
  const dernier = i === DIAPOS.length - 1;
  const aller = useCallback((k: number) => setI(Math.min(DIAPOS.length - 1, Math.max(0, k))), []);
  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") aller(i + 1);
      if (e.key === "ArrowLeft") aller(i - 1);
    };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [i, aller]);
  return (
    <div className="entree" role="dialog" aria-modal="true" aria-label="Présentation d'Eagle">
      <header className="entree__haut">
        {da?.logoHorizontal ? <img className="entree__logo" src={da.logoHorizontal} alt="Eagle" /> : <strong className="entree__nom">Eagle</strong>}
        <button type="button" className="entree__passer" onClick={terminer}>Passer la présentation</button>
      </header>
      <main className="entree__carte" key={i}>
        <section className="entree__texte" aria-live="polite">
          <p className="entree__surtitre">{d.surtitre} · {i + 1} sur {DIAPOS.length}</p>
          <h1 className="entree__titre">{d.titre}</h1>
          <p className="entree__chapeau">{d.texte}</p>
          <ul className="entree__points">{d.points.map((p) => <li key={p}>{p}</li>)}</ul>
        </section>
        <aside className="entree__visuel">
          {i === 0 && da?.avatar.ecoute ? <img className="entree__avatar" src={da.avatar.ecoute} alt="" width={132} height={132} /> : null}
          <p className="entree__visuel-titre">{d.visuel.titre}</p>
          {d.visuel.numerote
            ? <ol className="entree__liste entree__liste--numerotee">{d.visuel.lignes.map((l) => <li key={l}>{l}</li>)}</ol>
            : <ul className="entree__liste">{d.visuel.lignes.map((l) => <li key={l}>{l}</li>)}</ul>}
        </aside>
      </main>
      <footer className="entree__bas">
        <button type="button" className="bouton bouton--secondaire" onClick={() => aller(i - 1)} disabled={i === 0}>Précédente</button>
        <ol className="entree__pas" aria-label="Diapositives de la présentation">
          {DIAPOS.map((x, k) => (
            <li key={x.titre}>
              <button type="button" aria-label={`Diapositive ${k + 1} : ${x.titre}`} aria-current={k === i ? "step" : undefined}
                className={k === i ? "entree__pastille entree__pastille--actif" : "entree__pastille"} onClick={() => aller(k)} />
            </li>
          ))}
        </ol>
        {dernier
          ? <button type="button" className="bouton bouton--principal" onClick={terminer}>{suite}</button>
          : <button type="button" className="bouton bouton--principal" onClick={() => aller(i + 1)}>Suivante</button>}
      </footer>
      <p className="entree__mention">Simulation seulement : aucune transaction réelle.</p>
    </div>
  );
}

function Compte({ da, ouvert, raison }: { da: DirectionArtistique | null; ouvert: (s: Session) => void; raison: string | null }) {
  // Première visite sur ce navigateur : on propose de créer un compte ; sinon, de se connecter.
  const [mode, setMode] = useState<"connexion" | "creer">(() => {
    try { return window.localStorage.getItem(CLE_COMPTE_CONNU) === "1" ? "connexion" : "creer"; } catch { return "creer"; }
  });
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const creer = mode === "creer";
  const envoyer = async (e: FormEvent) => {
    e.preventDefault();
    if (envoi) return;
    if (creer && motDePasse !== confirmation) { setErreur("Les deux mots de passe ne sont pas identiques."); return; }
    setErreur(null);
    setEnvoi(true);
    try {
      const s = await ouvrirSession(mode, identifiant.trim(), motDePasse);
      try { window.localStorage.setItem(CLE_COMPTE_CONNU, "1"); } catch { /* sans effet sur la connexion */ }
      ouvert(s);
    } catch (x) {
      setErreur((x as Error).message);
    } finally {
      setEnvoi(false);
    }
  };
  const changerMode = (m: "connexion" | "creer") => { setMode(m); setErreur(null); setConfirmation(""); };
  return (
    <div className="entree entree--compte" role="dialog" aria-modal="true" aria-label="Compte Eagle">
      <form className="compte" onSubmit={envoyer}>
        {da?.logoHorizontal ? <img className="entree__logo" src={da.logoHorizontal} alt="Eagle" /> : <strong className="entree__nom">Eagle</strong>}
        <h1 className="compte__titre">{creer ? "Créer votre compte" : "Connexion à votre compte"}</h1>
        {raison ? <p className="compte__raison" role="status">{raison}</p> : null}
        <div className="compte__modes" role="tablist" aria-label="Connexion ou création de compte">
          <button type="button" role="tab" aria-selected={!creer} className={!creer ? "compte__mode compte__mode--actif" : "compte__mode"} onClick={() => changerMode("connexion")}>Se connecter</button>
          <button type="button" role="tab" aria-selected={creer} className={creer ? "compte__mode compte__mode--actif" : "compte__mode"} onClick={() => changerMode("creer")}>Créer un compte</button>
        </div>
        <label className="champ-texte">Identifiant
          <input value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false}
            required minLength={3} maxLength={32} aria-describedby={creer ? "aide-identifiant" : undefined} />
          {creer ? <span id="aide-identifiant" className="compte__aide">{REGLE_IDENTIFIANT} Un pseudonyme suffit.</span> : null}
        </label>
        <label className="champ-texte">Mot de passe
          <span className="compte__secret">
            <input type={visible ? "text" : "password"} value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)}
              autoComplete={creer ? "new-password" : "current-password"} required minLength={creer ? 8 : 1}
              aria-describedby={creer ? "aide-mdp" : undefined} />
            <button type="button" className="compte__voir" onClick={() => setVisible(!visible)} aria-pressed={visible}>{visible ? "Masquer" : "Afficher"}</button>
          </span>
          {creer ? <span id="aide-mdp" className="compte__aide">{REGLE_MOT_DE_PASSE}</span> : null}
        </label>
        {creer ? (
          <label className="champ-texte">Confirmer le mot de passe
            <input type={visible ? "text" : "password"} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} autoComplete="new-password" required />
          </label>
        ) : null}
        {erreur ? <p className="compte__erreur" role="alert">{erreur}</p> : null}
        <button type="submit" className="bouton bouton--principal" disabled={envoi}>
          {envoi ? "Un instant…" : creer ? "Créer le compte et entrer" : "Se connecter"}
        </button>
        <p className="compte__note">
          Aucune adresse courriel n&apos;est demandée. Le mot de passe est conservé par Amazon Cognito, sous forme hachée ; Eagle ne le stocke pas.
          Le compte protège l&apos;accès à l&apos;analyse. Simulation seulement : aucune transaction réelle.
        </p>
      </form>
    </div>
  );
}

export function Entree({ da }: { da: DirectionArtistique | null }) {
  // « attente » : le temps de lire le stockage du navigateur (présentation déjà vue ? session ouverte ?).
  const [ecran, setEcran] = useState<"attente" | "intro" | "compte" | null>("attente");
  const [tableau, setTableau] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [raison, setRaison] = useState<string | null>(null);

  const entrer = useCallback((s: Session | null) => {
    if (COMPTES_ACTIFS && !s) { setEcran("compte"); return; }
    setTableau(true);
    setEcran(null);
  }, []);

  useEffect(() => {
    let vue = false;
    try { vue = window.localStorage.getItem(CLE_INTRO) === "1"; } catch { /* stockage indisponible : on montre la présentation */ }
    const s = COMPTES_ACTIFS ? lireSession() : null;
    setSession(s);
    if (vue) entrer(s); else setEcran("intro");
    // Jeton refusé par le service en cours de route : on redemande la connexion par-dessus le tableau de bord.
    ecouterDeconnexion(() => { setSession(null); setRaison("Votre session a expiré. Reconnectez-vous : votre profil est conservé à l'écran."); setEcran("compte"); });
  }, [entrer]);

  const finIntro = () => {
    try { window.localStorage.setItem(CLE_INTRO, "1"); } catch { /* elle sera remontrée à la prochaine visite */ }
    entrer(session);
  };
  const deconnecter = () => { fermerSession(); setSession(null); setRaison(null); setEcran("compte"); };

  return (
    <>
      {tableau ? (
        <div aria-hidden={ecran ? true : undefined} inert={ecran ? true : undefined}>
          <Eagle da={da} compte={session ? { identifiant: session.identifiant, deconnecter } : null} ouvrirModeEmploi={() => setEcran("intro")} />
        </div>
      ) : null}
      {ecran === "intro" ? <Presentation da={da} terminer={finIntro} suite={tableau ? "Revenir au tableau de bord" : COMPTES_ACTIFS && !session ? "Continuer" : "Commencer"} /> : null}
      {ecran === "compte" ? <Compte da={da} raison={raison} ouvert={(s) => { setSession(s); setRaison(null); setTableau(true); setEcran(null); }} /> : null}
      {ecran === "attente" ? <div className="entree entree--attente" aria-busy="true" /> : null}
    </>
  );
}
