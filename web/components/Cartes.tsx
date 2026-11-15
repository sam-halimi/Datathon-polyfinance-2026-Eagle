"use client";

import { useState } from "react";
import { Chiffre, Texte, typo, useChiffres } from "./Chiffres";
import { formaterMontant, formaterPoids } from "@/lib/format";
import type { Controle, Portefeuille, Profil, SortiePipeline } from "@/lib/types";

// Les six cartes. Leur contenu vient de la sortie du pipeline
// (aujourd'hui web/data/exemple.json), jamais de la voix.

export const COULEURS = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)", "var(--serie-4)", "var(--serie-5)"];

function Entete({ titre, exemple }: { titre: string; exemple?: boolean }) {
  return (
    <header className="carte__entete">
      <h2 className="carte__titre">{titre}</h2>
      {exemple ? <span className="pastille">Exemple</span> : null}
    </header>
  );
}

const RISQUE: Record<string, string> = { faible: "Faible", modéré: "Modéré", élevé: "Élevé" };
const CONNAISSANCE: Record<string, string> = { débutant: "Débutant", intermédiaire: "Intermédiaire", avancé: "Avancé" };

function liste(v: string[], vide: string) {
  return v.length ? v.join(", ") : vide;
}

export function CarteProfil({ profil, titre = "Votre profil" }: { profil: Profil; titre?: string }) {
  const lignes: [string, string][] = [
    ["Horizon", profil.horizon_annees || "—"],
    ["But", profil.objectif || "—"],
    ["Risque", RISQUE[profil.tolerance_risque] ?? "—"],
    ["Connaissance", CONNAISSANCE[profil.connaissance] ?? "—"],
    ["Important", liste(profil.preferences, "Rien de particulier")],
    ["À écarter", liste(profil.exclusions, "Rien")],
    ["Intérêts", liste(profil.centres_interet, "Aucun")],
    ["Capital fictif", formaterMontant(profil.capital_fictif, profil.devise)],
  ];
  if (profil.demande) lignes.push(["Votre idée", `« ${profil.demande} »`]);
  return (
    <article className="carte">
      <Entete titre={titre} />
      <dl className="profil">
        {lignes.map(([k, v]) => (
          <div key={k} className="profil__ligne">
            <dt>{k}</dt>
            <dd>{typo(v)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export function BarreRepartition({ ptf, mince }: { ptf: Portefeuille; mince?: boolean }) {
  return (
    <div className={mince ? "barre barre--mince" : "barre"} role="img"
      aria-label={ptf.lignes.map((l) => `${l.nom} ${formaterPoids(l.poids)}`).join(", ")}>
      {ptf.lignes.map((l, i) => (
        <span key={l.symbole} style={{ flexGrow: l.poids, background: COULEURS[i % COULEURS.length] }} />
      ))}
    </div>
  );
}

export function CarteRepartition({ sortie, ptf }: { sortie: SortiePipeline; ptf: Portefeuille }) {
  return (
    <article className="carte">
      <Entete titre="Répartition" exemple={sortie.exemple} />
      <p className="carte__chapeau">Portefeuille simulé « {ptf.nom} »</p>
      <BarreRepartition ptf={ptf} />
      <ul className="lignes">
        {ptf.lignes.map((l, i) => (
          <li key={l.symbole} className="ligne">
            <span className="ligne__pastille" style={{ background: COULEURS[i % COULEURS.length] }} aria-hidden="true" />
            <span className="ligne__texte">
              <span className="ligne__nom">{l.role}</span>
              <span className="ligne__detail">{l.nom} · {l.classe}</span>
            </span>
            <span className="ligne__poids">{formaterPoids(l.poids)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

export function CarteRisque({ sortie, ptf }: { sortie: SortiePipeline; ptf: Portefeuille }) {
  const { chiffres } = useChiffres();
  return (
    <article className="carte">
      <Entete titre="Risque" exemple={sortie.exemple} />
      <p className="risque__total">
        <span className="risque__total-libelle">Variation typique par an</span>
        <span className="risque__total-valeur"><Chiffre id={ptf.volatilite} /></span>
      </p>
      <div className="legende" aria-hidden="true">
        <span><i className="legende__capital" /> Part de l&apos;argent</span>
        <span><i className="legende__risque" /> Part du risque</span>
      </div>
      <ul className="parts">
        {ptf.lignes.map((l, i) => {
          const idPart = ptf.parts_du_risque[l.symbole];
          const part = chiffres[idPart]?.valeur ?? 0;
          return (
            <li key={l.symbole} className="part">
              <p className="part__nom">
                <span className="ligne__pastille" style={{ background: COULEURS[i % COULEURS.length] }} aria-hidden="true" />
                {l.nom}
              </p>
              <div className="part__barres">
                <div className="part__piste"><span className="part__capital" style={{ width: `${l.poids * 100}%` }} /></div>
                <span className="part__valeur">{formaterPoids(l.poids)}</span>
                <div className="part__piste"><span className="part__risque" style={{ width: `${part * 100}%` }} /></div>
                <span className="part__valeur part__valeur--risque"><Chiffre id={idPart} /></span>
              </div>
              <p className="part__baisse">Pire baisse en 5 ans : <Chiffre id={ptf.pires_baisses[l.symbole]} /></p>
            </li>
          );
        })}
      </ul>
    </article>
  );
}

const ICONE: Record<Controle["statut"], string> = { ok: "✓", alerte: "!", echec: "✕" };

export function CarteVerifications({ sortie }: { sortie: SortiePipeline }) {
  const g = sortie.gouvernance;
  return (
    <article className="carte">
      <Entete titre="Vérifications" exemple={sortie.exemple} />
      <p className="carte__chapeau">
        {g.statut === "accepte" ? "Accepté" : "Rejeté"} par la gouvernance · essai {g.essai} sur {g.essais_max}
      </p>
      <ul className="controles">
        {g.controles.map((c) => (
          <li key={c.titre} className={`controle controle--${c.statut}`}>
            <span className="controle__icone" aria-label={c.statut === "ok" ? "Réussi" : c.statut === "alerte" ? "Alerte" : "Échec"}>
              {ICONE[c.statut]}
            </span>
            <span>
              <span className="controle__titre">{c.titre}</span>
              <span className="controle__detail"><Texte>{c.detail}</Texte></span>
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}

const NIVEAUX = ["En bref", "Les chiffres", "Le calcul"] as const;

export function CartePourquoi({ sortie }: { sortie: SortiePipeline }) {
  const e = sortie.explication;
  const [niveau, setNiveau] = useState<number>(e.niveau_par_defaut);
  return (
    <article className="carte">
      <Entete titre="Pourquoi" exemple={sortie.exemple} />
      <p className="carte__chapeau">{e.sujet}</p>
      <div className="niveaux" role="tablist" aria-label="Niveau de détail">
        {NIVEAUX.map((nom, i) => (
          <button key={nom} type="button" role="tab" aria-selected={niveau === i + 1}
            className={niveau === i + 1 ? "niveau niveau--actif" : "niveau"} onClick={() => setNiveau(i + 1)}>
            {nom}
          </button>
        ))}
      </div>
      <div className="explication" role="tabpanel">
        {niveau === 1 ? <p className="explication__phrase"><Texte>{e.niveau1}</Texte></p> : null}
        {niveau === 2 ? (
          <ul className="explication__liste">
            {e.niveau2.map((t) => <li key={t}><Texte>{t}</Texte></li>)}
          </ul>
        ) : null}
        {niveau === 3 ? (
          <>
            <p className="formule">{e.niveau3.formule}</p>
            <ul className="explication__liste explication__liste--serree">
              {e.niveau3.lignes.map((t) => <li key={t}><Texte>{t}</Texte></li>)}
            </ul>
          </>
        ) : null}
      </div>
      <p className="carte__pied">Touchez un chiffre souligné pour voir son calcul.</p>
    </article>
  );
}

export function CarteLimites({ sortie }: { sortie: SortiePipeline }) {
  const l = sortie.limites;
  const blocs: [string, string, string[]][] = [
    ["faits", "Faits", l.faits],
    ["hypotheses", "Hypothèses", l.hypotheses],
    ["limites", "Limites", l.limites],
  ];
  return (
    <article className="carte">
      <Entete titre="Limites" exemple={sortie.exemple} />
      {blocs.map(([cle, titre, items]) => (
        <section key={cle} className={`bloc bloc--${cle}`}>
          <h3 className="bloc__titre">{titre}</h3>
          <ul>
            {items.map((t) => <li key={t}><Texte>{t}</Texte></li>)}
          </ul>
        </section>
      ))}
    </article>
  );
}
