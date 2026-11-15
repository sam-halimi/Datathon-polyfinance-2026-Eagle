"use client";

import { useCallback, useMemo, useState, type FormEvent } from "react";
import { CarteAnalyse } from "./Analyse";
import { CarteLimites, CartePourquoi, CarteProfil, CarteRepartition, CarteRisque, CarteVerifications } from "./Cartes";
import { FicheReference, FournisseurChiffres } from "./Chiffres";
import { Assistant, BarreEtapes } from "./Entete";
import { CartePersonas } from "./Personas";
import { ToutVoir } from "./ToutVoir";
import { chargerSortie, type Persona } from "@/lib/personas";
import type { Carte, SortiePipeline } from "@/lib/types";

// L'écran d'appel : l'assistant en haut, une carte au milieu, la saisie en bas.
// Une seule chose à la fois. La voix (étape 3) ne fera que choisir la carte.

type Vue =
  | { type: "depart" }
  | { type: "persona" }
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
  ["verifications", /verif|controle|gouvernance|ecarte/],
  ["pourquoi", /pourquoi|explication|expliqu/],
  ["limites", /limite|hypothese|fait/],
];

function normaliser(t: string): string {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function Appel() {
  const [vue, setVue] = useState<Vue>({ type: "depart" });
  const [persona, setPersona] = useState<Persona | null>(null);
  const [sortie, setSortie] = useState<SortiePipeline | null>(null);
  const [chargement, setChargement] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ptfId, setPtfId] = useState<string | null>(null);
  const [analyseFinie, setAnalyseFinie] = useState(false);
  const [fiche, setFiche] = useState<string | null>(null);
  const [saisie, setSaisie] = useState("");
  const [reponse, setReponse] = useState<string | null>(null);

  const ctx = useMemo(() => ({ chiffres: sortie?.chiffres ?? {}, ouvrir: setFiche }), [sortie]);
  const finAnalyse = useCallback(() => setAnalyseFinie(true), []);

  const aller = (v: Vue) => {
    setReponse(null);
    setSaisie("");
    if (v.type === "analyse") setAnalyseFinie(false);
    setVue(v);
  };

  const choisirPersona = async (p: Persona) => {
    setChargement(p.id);
    setErreur(null);
    try {
      const s = await chargerSortie(p.id);
      setPersona(p);
      setSortie(s);
      setPtfId(s.gouvernance.portefeuille_retenu);
      aller({ type: "recap" });
    } catch {
      setErreur(`Je n'arrive pas à lire agents/sorties/${p.id}.json.`);
    } finally {
      setChargement(null);
    }
  };

  const suivant = () => {
    switch (vue.type) {
      case "depart": return aller({ type: "persona" });
      case "persona": return;
      case "recap": return aller({ type: "analyse" });
      case "analyse": return aller({ type: "carte", carte: PARCOURS[0] });
      case "carte": {
        if (vue.depuisTout) return aller({ type: "tout" });
        const k = PARCOURS.indexOf(vue.carte);
        return aller(k + 1 < PARCOURS.length ? { type: "carte", carte: PARCOURS[k + 1] } : { type: "tout" });
      }
      case "tout": return aller({ type: "persona" });
    }
  };

  const retour = () => {
    switch (vue.type) {
      case "persona": return aller({ type: "depart" });
      case "recap": return aller({ type: "persona" });
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
          <li>Trois profils, trois vraies analyses</li>
          <li>Une chose à la fois</li>
          <li>Simulation seulement : aucune transaction réelle</li>
        </ul>
        <div className="depart__bas">
          <button type="button" className="bouton bouton--principal bouton--appel" onClick={suivant}>
            Démarrer l&apos;appel
          </button>
        </div>
      </main>
    );
  }

  // ---- Contenu de chaque zone selon la vue ----
  let etape = 0;
  let message = "";
  let sousTitre: string | undefined;
  let carte: React.ReactNode = null;
  let libelleSuivant: string | null = "Suivant";
  let libelleRetour = "Retour";
  let suivantActif = true;
  const ptf = sortie ? sortie.portefeuilles.find((p) => p.id === ptfId) ?? sortie.portefeuilles[0] : null;

  if (vue.type === "persona" || !sortie || !persona || !ptf) {
    message = erreur ?? "Quel profil voulez-vous essayer ?";
    sousTitre = erreur ? undefined : "Trois personas, chacun avec sa demande";
    carte = <CartePersonas choisir={choisirPersona} enCours={chargement} />;
    libelleSuivant = null;
  } else {
    switch (vue.type) {
      case "recap":
        message = "Voici ce que j'ai compris. C'est bien ça ?";
        carte = <CarteProfil profil={sortie.profil} titre={`Profil de ${persona.nom}`} notes={persona.choix} />;
        libelleRetour = "Changer";
        libelleSuivant = "C'est bien ça";
        break;
      case "analyse":
        etape = 1;
        message = analyseFinie ? sortie.messages.analyse : "Les spécialistes analysent le profil…";
        carte = <CarteAnalyse sortie={sortie} fini={finAnalyse} />;
        suivantActif = analyseFinie;
        libelleSuivant = analyseFinie ? "Voir la proposition" : "Analyse en cours…";
        break;
      case "carte": {
        etape = ETAPE_DE_CARTE[vue.carte];
        message = vue.carte === "profil" ? `Le profil de ${persona.nom}, tel qu'il l'a validé.` : sortie.messages[vue.carte];
        const cartes: Record<Carte, React.ReactNode> = {
          profil: <CarteProfil profil={sortie.profil} titre={`Profil de ${persona.nom}`} notes={persona.choix} />,
          repartition: <CarteRepartition sortie={sortie} ptf={ptf} choisir={setPtfId} />,
          risque: <CarteRisque sortie={sortie} ptf={ptf} choisir={setPtfId} />,
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
        carte = <ToutVoir sortie={sortie} ptf={ptf} ouvrir={(c) => aller({ type: "carte", carte: c, depuisTout: true })} />;
        libelleSuivant = "Autre profil";
        break;
    }
  }

  const resultat = vue.type === "carte" || vue.type === "tout";

  return (
    <FournisseurChiffres valeur={ctx}>
      <main className="appel">
        <BarreEtapes active={etape} />
        <Assistant message={reponse ?? message} sousTitre={reponse ? undefined : sousTitre} />
        <div className="appel__carte" key={vue.type === "carte" ? vue.carte : vue.type}>
          {carte}
        </div>
        <footer className="saisie">
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
            {libelleSuivant ? (
              <button type="button" className="bouton bouton--principal" onClick={suivant} disabled={!suivantActif}>
                {libelleSuivant}
              </button>
            ) : null}
          </div>
        </footer>
        {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
      </main>
    </FournisseurChiffres>
  );
}
