"use client";

import { useCallback, useMemo, useState, type FormEvent } from "react";
import { CarteAnalyse, CarteQuestion } from "./Accueil";
import { CarteLimites, CartePourquoi, CarteProfil, CarteRepartition, CarteRisque, CarteVerifications } from "./Cartes";
import { FicheReference, FournisseurChiffres } from "./Chiffres";
import { Assistant, BarreEtapes } from "./Entete";
import { ToutVoir } from "./ToutVoir";
import { choisir, estRepondue, QUESTIONS, viderListe } from "@/lib/questions";
import type { Carte, Profil, SortiePipeline } from "@/lib/types";

// L'écran d'appel : l'assistant en haut, une carte au milieu, la saisie en bas.
// Une seule chose à la fois. La voix (étape 3) ne fera que choisir la carte.

type Vue =
  | { type: "depart" }
  | { type: "question"; i: number }
  | { type: "recap" }
  | { type: "analyse" }
  | { type: "carte"; carte: Carte; depuisTout?: boolean }
  | { type: "tout" };

const PARCOURS: Carte[] = ["repartition", "risque", "verifications", "pourquoi", "limites"];

const ETAPE_DE_CARTE: Record<Carte, number> = {
  profil: 0, repartition: 2, risque: 2, verifications: 3, pourquoi: 4, limites: 4,
};

const MOTS: [Carte | "tout", RegExp][] = [
  ["tout", /\btout\b/],
  ["profil", /profil/],
  ["repartition", /repartition|portefeuille|allocation|actifs?\b/],
  ["risque", /risque|volatilite|baisse/],
  ["verifications", /verif|controle|gouvernance/],
  ["pourquoi", /pourquoi|explication|expliqu/],
  ["limites", /limite|hypothese|fait/],
];

function normaliser(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function memeProfil(a: Profil, b: Profil): boolean {
  const cle = (p: Profil) =>
    JSON.stringify([p.horizon_annees, p.objectif, p.tolerance_risque, p.connaissance, [...p.preferences].sort(),
      [...p.exclusions].sort(), [...p.centres_interet].sort(), p.capital_fictif]);
  return cle(a) === cle(b);
}

export function Appel({ sortie }: { sortie: SortiePipeline }) {
  const [vue, setVue] = useState<Vue>({ type: "depart" });
  // Réponses d'exemple déjà cochées : celles du profil de la sortie.
  const [profil, setProfil] = useState<Profil>(sortie.profil);
  const [analyseFinie, setAnalyseFinie] = useState(false);
  const [fiche, setFiche] = useState<string | null>(null);
  const [saisie, setSaisie] = useState("");
  const [reponse, setReponse] = useState<string | null>(null);

  const ctx = useMemo(() => ({ chiffres: sortie.chiffres, ouvrir: setFiche }), [sortie.chiffres]);
  const finAnalyse = useCallback(() => setAnalyseFinie(true), []);
  const ptf = sortie.portefeuilles[0];

  const aller = (v: Vue) => {
    setReponse(null);
    setSaisie("");
    if (v.type === "analyse") setAnalyseFinie(false);
    setVue(v);
  };

  const suivant = () => {
    switch (vue.type) {
      case "depart": return aller({ type: "question", i: 0 });
      case "question": return aller(vue.i + 1 < QUESTIONS.length ? { type: "question", i: vue.i + 1 } : { type: "recap" });
      case "recap": return aller({ type: "analyse" });
      case "analyse": return aller({ type: "carte", carte: PARCOURS[0] });
      case "carte": {
        if (vue.depuisTout) return aller({ type: "tout" });
        const k = PARCOURS.indexOf(vue.carte);
        return aller(k + 1 < PARCOURS.length ? { type: "carte", carte: PARCOURS[k + 1] } : { type: "tout" });
      }
      case "tout": return aller({ type: "depart" });
    }
  };

  const retour = () => {
    switch (vue.type) {
      case "question": return aller(vue.i > 0 ? { type: "question", i: vue.i - 1 } : { type: "depart" });
      case "recap": return aller({ type: "question", i: QUESTIONS.length - 1 });
      case "analyse": return aller({ type: "recap" });
      case "carte": {
        if (vue.depuisTout) return aller({ type: "tout" });
        const k = PARCOURS.indexOf(vue.carte);
        return aller(k > 0 ? { type: "carte", carte: PARCOURS[k - 1] } : { type: "analyse" });
      }
      case "tout": return aller({ type: "carte", carte: PARCOURS[PARCOURS.length - 1] });
    }
  };

  // Repli en texte : la saisie fait ce que fera la voix, choisir une carte.
  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    const t = normaliser(saisie.trim());
    if (!t) return;
    const trouve = MOTS.find(([, re]) => re.test(t));
    setSaisie("");
    if (!trouve) {
      setReponse("Je peux vous montrer : profil, répartition, risque, vérifications, pourquoi, limites, ou tout.");
      return;
    }
    const [cible] = trouve;
    aller(cible === "tout" ? { type: "tout" } : { type: "carte", carte: cible, depuisTout: vue.type === "tout" });
  };

  // ---- Contenu de chaque zone selon la vue ----
  let etape = 0;
  let message = "";
  let sousTitre: string | undefined;
  let carte: React.ReactNode = null;
  let libelleSuivant = "Suivant";
  let libelleRetour = "Retour";
  let suivantActif = true;

  switch (vue.type) {
    case "question": {
      const q = QUESTIONS[vue.i];
      sousTitre = `Question ${vue.i + 1} sur ${QUESTIONS.length}`;
      message = q.texte;
      suivantActif = estRepondue(profil, q);
      carte = (
        <CarteQuestion q={q} profil={profil}
          choisir={(v) => setProfil((p) => choisir(p, q, v))} vider={() => setProfil((p) => viderListe(p, q))} />
      );
      break;
    }
    case "recap":
      message = "Voici ce que j'ai compris. C'est bien ça ?";
      carte = <CarteProfil profil={profil} titre="Récapitulatif" />;
      libelleRetour = "Modifier";
      libelleSuivant = "C'est bien ça";
      break;
    case "analyse":
      etape = 1;
      message = sortie.messages.analyse;
      if (sortie.exemple && !memeProfil(profil, sortie.profil)) {
        message += ` Pour l'instant, je montre un exemple : le profil de ${sortie.profil.prenom ?? "démonstration"}.`;
      }
      carte = <CarteAnalyse sortie={sortie} fini={finAnalyse} />;
      suivantActif = analyseFinie;
      libelleSuivant = analyseFinie ? "Voir la proposition" : "Analyse en cours…";
      break;
    case "carte": {
      etape = ETAPE_DE_CARTE[vue.carte];
      message = vue.carte === "profil" ? "Votre profil, tel que vous l'avez validé." : sortie.messages[vue.carte];
      const cartes: Record<Carte, React.ReactNode> = {
        profil: <CarteProfil profil={profil} />,
        repartition: <CarteRepartition sortie={sortie} ptf={ptf} />,
        risque: <CarteRisque sortie={sortie} ptf={ptf} />,
        verifications: <CarteVerifications sortie={sortie} />,
        pourquoi: <CartePourquoi sortie={sortie} />,
        limites: <CarteLimites sortie={sortie} />,
      };
      carte = cartes[vue.carte];
      if (vue.depuisTout) {
        libelleSuivant = "Revenir à tout voir";
      } else if (vue.carte === PARCOURS[PARCOURS.length - 1]) {
        libelleSuivant = "Tout voir";
      }
      break;
    }
    case "tout":
      etape = 4;
      message = sortie.messages.tout;
      carte = <ToutVoir sortie={sortie} profil={profil} ouvrir={(c) => aller({ type: "carte", carte: c, depuisTout: true })} />;
      libelleSuivant = "Recommencer";
      break;
  }

  if (vue.type === "depart") {
    return (
      <main className="depart">
        <div className="depart__haut">
          <div className="assistant__avatar assistant__avatar--grand" aria-hidden="true"><span /><span /><span /></div>
          <h1 className="depart__titre">AlphaForge</h1>
          <p className="depart__phrase">
            Un assistant construit avec vous un portefeuille simulé. Il explique chaque chiffre.
          </p>
        </div>
        <ul className="depart__promesses">
          <li>8 questions courtes</li>
          <li>Une chose à la fois</li>
          <li>Simulation seulement : aucune transaction réelle</li>
        </ul>
        <div className="depart__bas">
          <button type="button" className="bouton bouton--principal bouton--appel" onClick={suivant}>
            Démarrer l&apos;appel
          </button>
          {sortie.exemple ? <p className="depart__note">Démonstration : les réponses d&apos;exemple sont déjà cochées.</p> : null}
        </div>
      </main>
    );
  }

  const q = vue.type === "question" ? QUESTIONS[vue.i] : null;
  const champLibre = q?.saisie;
  const resultat = vue.type === "carte" || vue.type === "tout";

  return (
    <FournisseurChiffres valeur={ctx}>
      <main className="appel">
        <BarreEtapes active={etape} />
        <Assistant message={reponse ?? message} sousTitre={reponse ? undefined : sousTitre} />
        <div className="appel__carte" key={vue.type === "carte" ? vue.carte : vue.type === "question" ? `q${vue.i}` : vue.type}>
          {carte}
        </div>
        <footer className="saisie">
          {champLibre ? (
            <label className="champ">
              <span className="sr-only">{champLibre.invite}</span>
              <input type="text" value={String(profil[champLibre.champ] ?? "")} placeholder={champLibre.invite}
                onChange={(e) => setProfil((p) => ({ ...p, [champLibre.champ]: e.target.value }))} />
            </label>
          ) : null}
          {resultat ? (
            <form className="champ champ--envoi" onSubmit={envoyer}>
              <label className="sr-only" htmlFor="saisie">Écrire à l&apos;assistant</label>
              <input id="saisie" type="text" value={saisie} onChange={(e) => setSaisie(e.target.value)}
                placeholder="Écrire : risque, pourquoi, tout…" autoComplete="off" />
              <button type="submit" className="champ__envoyer" aria-label="Envoyer">→</button>
            </form>
          ) : null}
          <div className="saisie__boutons">
            {vue.type === "tout" || (vue.type === "carte" && vue.depuisTout) ? null : (
              <button type="button" className="bouton bouton--secondaire" onClick={retour}>{libelleRetour}</button>
            )}
            <button type="button" className="bouton bouton--principal" onClick={suivant} disabled={!suivantActif}>
              {libelleSuivant}
            </button>
          </div>
        </footer>
        {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
      </main>
    </FournisseurChiffres>
  );
}
