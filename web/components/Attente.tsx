"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { typo } from "./Chiffres";
import { useLangue } from "./Langue";
import { lireProgression, type Progression } from "@/lib/api";

// Écran d'attente de l'analyse (une à trois minutes).
//
// Ce qu'il montre est réel : le service publie l'avancement du pipeline (agents/progression.py) et
// l'écran le relit toutes les deux secondes et demie. On voit donc quel agent travaille, lesquels ont
// fini et ce qu'ils ont constaté. Sans réponse du service de suivi, l'écran montre le déroulé prévu
// et le temps écoulé, sans prétendre savoir quelle étape est en cours.

const AGENTS = [
  ["Orchestrateur", "lit votre profil et votre demande, fixe les plafonds"],
  ["ESG et qualité", "écarte ou signale les titres selon vos critères, avec leurs sources"],
  ["Marché et risque", "mesure volatilité et pires baisses des actifs candidats"],
  ["Macro et taux", "mesure la sensibilité aux taux et la pente des courbes"],
  ["Constructeur", "propose deux ou trois portefeuilles simulés"],
  ["Gouvernance", "vérifie chaque proposition au regard de votre profil, deux essais au plus"],
  ["Explication", "rédige l'explication, chaque chiffre renvoyant à son calcul"],
] as const;
// En anglais, une étape de plus : la traduction des textes du résultat (agents/traduction.py).
const TRADUCTION = ["Traduction", "met les textes du résultat en anglais, sans toucher aux chiffres"] as const;
const INTERVALLE = 2500;

function duree(secondes: number): string {
  const m = Math.floor(secondes / 60), s = secondes % 60;
  return m ? `${m} min ${String(s).padStart(2, "0")} s` : `${s} s`;
}

export function EcranAttente({ debut, suivi }: { debut: number; suivi: string | null }) {
  const langue = useLangue();
  const [maintenant, setMaintenant] = useState(() => Date.now());
  const [p, setP] = useState<Progression | null>(null);
  useEffect(() => {
    const t = window.setInterval(() => setMaintenant(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    setP(null);
    if (!suivi) return;
    let actif = true;
    const lire = async () => {
      const r = await lireProgression(suivi);
      if (actif && r?.connu) setP(r);
    };
    void lire();
    const t = window.setInterval(lire, INTERVALLE);
    return () => { actif = false; window.clearInterval(t); };
  }, [suivi]);

  const etapes = langue === "en" ? [...AGENTS, TRADUCTION] : [...AGENTS];
  const ecoule = Math.max(0, Math.floor((maintenant - debut) / 1000));
  const connu = Boolean(p?.connu);
  // Rang de l'étape en cours : -1 avant le premier agent, le dernier rang pendant la traduction.
  const rang = !connu ? -1
    : p?.phase === "traduction" ? AGENTS.length
    : p?.phase === "terminee" ? etapes.length
    : AGENTS.findIndex(([nom]) => nom === p?.agent);
  const constats = new Map((p?.faits ?? []).map((f) => [f.agent, f.fait]));
  const part = !connu ? null : Math.min(1, Math.max(0.03, (Math.max(rang, 0) + (rang >= 0 && rang < etapes.length ? 0.5 : 0)) / etapes.length));
  const enCours = rang >= 0 && rang < etapes.length ? etapes[rang][0] : null;
  const essai = p?.essai ?? 1;

  return (
    <div className="chargement" role="status" aria-live="polite" aria-busy="true">
      <div className="chargement__tete">
        <div className={part === null ? "chargement__barre chargement__barre--libre" : "chargement__barre"}
          role="progressbar" aria-label="Avancement de l'analyse" aria-valuemin={0} aria-valuemax={etapes.length}
          aria-valuenow={part === null ? undefined : Math.max(rang, 0)}>
          <span className="chargement__avance" style={part === null ? undefined : { width: `${Math.round(part * 100)}%` }} />
        </div>
        <p className="chargement__repere">
          <span className="chargement__ou">
            {enCours ? <>{`Étape ${rang + 1} sur ${etapes.length}`} · <strong>{enCours}</strong></> : connu && rang < 0 ? "Démarrage de l'analyse" : "Analyse en cours"}
          </span>
          <span className="chargement__temps">{duree(ecoule)} · <span>Durée habituelle : 1 à 3 minutes</span></span>
        </p>
      </div>
      <ol className="chargement__liste">
        {etapes.map(([nom, prevu], i) => {
          const etat = !connu ? "neutre" : i < rang ? "fait" : i === rang ? "actif" : "avenir";
          // Étape finie : ce que l'agent a réellement constaté (en français ; en anglais, la description prévue).
          const constat = etat === "fait" && langue === "fr" ? constats.get(nom) : undefined;
          return (
            <li key={nom} className={`chargement__agent chargement__agent--${etat}`} aria-current={etat === "actif" ? "step" : undefined}>
              <span className="chargement__puce" aria-hidden="true">{etat === "fait" ? <Check size={14} strokeWidth={3} /> : etat === "actif" ? null : i + 1}</span>
              <span className="chargement__texte">
                <strong className="chargement__nom">{nom}</strong>
                <span className="chargement__fait" title={constat}>{constat ? typo(constat) : prevu}</span>
                {essai > 1 && nom === "Gouvernance" && connu
                  ? <span className="chargement__essai">{`Essai ${essai} : la gouvernance a renvoyé les propositions au constructeur.`}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="chargement__note">La présentation s&apos;affiche dès que l&apos;analyse est prête.</p>
    </div>
  );
}
