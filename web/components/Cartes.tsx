"use client";

import { useState } from "react";
import { Chiffre, Texte, typo, useChiffres } from "./Chiffres";
import { Camembert, PALETTE } from "./Graphiques";
import { Pages, type Element } from "./Pages";
import { formaterDate, formaterHorizon, formaterMontant, formaterPoids, majuscule } from "@/lib/format";
import type { Controle, Portefeuille, Profil, Regroupement, SortiePipeline } from "@/lib/types";

// Les six cartes. Leur contenu vient de la sortie du pipeline
// (agents/sorties/<persona>.json), jamais de la voix. Une liste trop longue
// pour l'écran est coupée en pages : rien ne défile.

export const COULEURS = PALETTE;

function Entete({ titre, children }: { titre: string; children?: React.ReactNode }) {
  return (
    <header className="carte__entete">
      <h2 className="carte__titre">{titre}</h2>
      {children}
    </header>
  );
}

const RISQUE: Record<string, string> = { faible: "Faible", modéré: "Modéré", élevé: "Élevé" };
const CONNAISSANCE: Record<string, string> = { débutant: "Débutant", intermédiaire: "Intermédiaire", avancé: "Avancé" };

function liste(v: string[], vide: string) {
  return v.length ? v.join(", ") : vide;
}

// ---------- Profil ----------

export function CarteProfil({ profil, titre, notes = [] }: { profil: Profil; titre: string; notes?: string[] }) {
  const lignes: [string, string][] = [
    ["Horizon", formaterHorizon(profil.horizon_annees)],
    ["But", majuscule(profil.objectif) || "—"],
    ["Risque", RISQUE[profil.tolerance_risque] ?? "—"],
    ["Connaissance", CONNAISSANCE[profil.connaissance] ?? "—"],
    ["Important", liste(profil.preferences, "Rien de particulier")],
    ["À écarter", liste(profil.exclusions, "Rien")],
    ["Intérêts", liste(profil.centres_interet, "Aucun")],
    ["Capital fictif", formaterMontant(profil.capital_fictif, profil.devise)],
  ];
  if (profil.demande) lignes.push(["Sa demande", `« ${profil.demande} »`]);
  const elements: Element[] = [
    ...lignes.map(([k, v]) => ({
      cle: k,
      contenu: <div className="profil__ligne"><span className="profil__cle">{k}</span><span className="profil__valeur">{typo(v)}</span></div>,
    })),
    ...notes.map((n, i) => ({ cle: `note${i}`, contenu: <p className="profil__note">{typo(n)}</p> })),
  ];
  return (
    <article className="carte">
      <Entete titre={titre} />
      <Pages elements={elements} classe="profil" />
    </article>
  );
}

// ---------- Choix du portefeuille (répartition et risque) ----------

export function ChoixPortefeuille({ sortie, ptf, choisir }: { sortie: SortiePipeline; ptf: Portefeuille; choisir: (id: string) => void }) {
  const retenu = sortie.gouvernance.portefeuille_retenu;
  return (
    <div className="segment" role="tablist" aria-label="Portefeuilles simulés">
      {sortie.portefeuilles.map((p) => (
        <button key={p.id} type="button" role="tab" aria-selected={p.id === ptf.id}
          className={p.id === ptf.id ? "segment__bouton segment__bouton--actif" : "segment__bouton"} onClick={() => choisir(p.id)}>
          {p.id}{p.id === retenu ? <span className="segment__retenu"> · retenu</span> : null}
        </button>
      ))}
    </div>
  );
}

// ---------- Répartition ----------

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

const REGROUPEMENTS: [Regroupement, string][] = [["actif", "Par actif"], ["secteur", "Par secteur"], ["zone", "Par zone"]];

export function CarteRepartition({ sortie, ptf, choisir }: { sortie: SortiePipeline; ptf: Portefeuille; choisir: (id: string) => void }) {
  const [vue, setVue] = useState<Regroupement>("actif");
  const reps = sortie.graphiques.repartitions[ptf.id];
  const parts = reps[vue];
  const intention: Element = { cle: "intention", contenu: <p className="carte__chapeau">{typo(ptf.intention)}</p> };
  const elements: Element[] =
    vue === "actif"
      ? [intention, ...parts.map((p, i) => {
        const l = ptf.lignes.find((x) => x.symbole === p.symboles[0]);
        return {
          cle: p.id,
          contenu: (
            <div className="ligne">
              <span className="ligne__pastille" style={{ background: PALETTE[i % PALETTE.length] }} aria-hidden="true" />
              <span className="ligne__texte">
                <span className="ligne__nom">{l ? typo(l.role) : p.libelle}</span>
                <span className="ligne__detail">{l ? `${l.nom} · ${l.symbole}` : p.libelle}</span>
              </span>
              <span className="ligne__poids"><Chiffre id={p.id} /></span>
            </div>
          ),
        };
      })]
      : parts.map((p, i) => ({
        cle: p.id,
        contenu: (
          <div className="ligne">
            <span className="ligne__pastille" style={{ background: PALETTE[i % PALETTE.length] }} aria-hidden="true" />
            <span className="ligne__texte">
              <span className="ligne__nom">{p.libelle}</span>
              <span className="ligne__detail">{p.symboles.join(", ")}</span>
            </span>
            <span className="ligne__poids"><Chiffre id={p.id} /></span>
          </div>
        ),
      }));
  return (
    <article className="carte">
      <Entete titre="Répartition"><ChoixPortefeuille sortie={sortie} ptf={ptf} choisir={choisir} /></Entete>
      <div className="repartition__haut">
        <Camembert parts={parts} libelle={`Répartition ${REGROUPEMENTS.find(([k]) => k === vue)?.[1].toLowerCase()} du portefeuille ${ptf.id}`} />
        <div className="repartition__texte">
          <p className="carte__nom">{typo(ptf.nom)}</p>
          <p className="repartition__sous-titre">Portefeuille simulé {ptf.id}, {REGROUPEMENTS.find(([k]) => k === vue)?.[1].toLowerCase()}</p>
        </div>
      </div>
      <div className="niveaux" role="tablist" aria-label="Regroupement">
        {REGROUPEMENTS.map(([cle, nom]) => (
          <button key={cle} type="button" role="tab" aria-selected={vue === cle}
            className={vue === cle ? "niveau niveau--actif" : "niveau"} onClick={() => setVue(cle)}>{nom}</button>
        ))}
      </div>
      <Pages elements={elements} classe="lignes" />
    </article>
  );
}

// ---------- Risque ----------

export function CarteRisque({ sortie, ptf, choisir }: { sortie: SortiePipeline; ptf: Portefeuille; choisir: (id: string) => void }) {
  const { chiffres } = useChiffres();
  const elements: Element[] = ptf.lignes.map((l, i) => {
    const idPart = ptf.parts_du_risque[l.symbole];
    const part = Math.max(0, Math.min(1, chiffres[idPart]?.valeur ?? 0));
    return {
      cle: l.symbole,
      contenu: (
        <div className="part">
          <p className="part__nom">
            <span className="ligne__pastille" style={{ background: COULEURS[i % COULEURS.length] }} aria-hidden="true" />
            {l.symbole}
            <span className="part__mesures">
              vol. <Chiffre id={ptf.volatilites[l.symbole]} /> · pire baisse <Chiffre id={ptf.pires_baisses[l.symbole]} />
            </span>
          </p>
          <div className="part__barres">
            <div className="part__piste"><span className="part__capital" style={{ width: `${l.poids * 100}%` }} /></div>
            <span className="part__valeur">{formaterPoids(l.poids)}</span>
            <div className="part__piste"><span className="part__risque" style={{ width: `${part * 100}%` }} /></div>
            <span className="part__valeur part__valeur--risque"><Chiffre id={idPart} /></span>
          </div>
        </div>
      ),
    };
  });
  return (
    <article className="carte">
      <Entete titre="Risque"><ChoixPortefeuille sortie={sortie} ptf={ptf} choisir={choisir} /></Entete>
      <div className="risque__totaux">
        <p className="risque__total">
          <span className="risque__total-libelle">Variation typique par an</span>
          <span className="risque__total-valeur"><Chiffre id={ptf.volatilite} /></span>
        </p>
        <p className="risque__total">
          <span className="risque__total-libelle">Pire baisse sur la fenêtre</span>
          <span className="risque__total-valeur"><Chiffre id={ptf.pire_baisse} /></span>
        </p>
      </div>
      <div className="legende" aria-hidden="true">
        <span><i className="legende__capital" /> Part de l&apos;argent</span>
        <span><i className="legende__risque" /> Part du risque</span>
      </div>
      <Pages elements={elements} classe="parts" />
    </article>
  );
}

// ---------- Vérifications ----------

const ICONE: Record<Controle["statut"] | "retour" | "ecarte", string> = { ok: "✓", alerte: "!", echec: "✕", retour: "↺", ecarte: "–" };
const LIBELLE: Record<Controle["statut"], string> = { ok: "Réussi", alerte: "À signaler", echec: "Échec" };

function Ligne({ statut, titre, children }: { statut: keyof typeof ICONE; titre: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className={`controle controle--${statut}`}>
      <span className="controle__icone" aria-label={statut in LIBELLE ? LIBELLE[statut as Controle["statut"]] : undefined}>
        {ICONE[statut]}
      </span>
      <span>
        <span className="controle__titre">{titre}</span>
        {children ? <span className="controle__detail">{children}</span> : null}
      </span>
    </div>
  );
}

/** Candidats écartés avant construction, regroupés par raison. Une raison
 *  sourcée a la forme « controverse documentée selon data/x.csv (source : URL, AAAA-MM-JJ) » :
 *  chaque symbole renvoie alors à sa source. */
type Ecart = { symbole: string; url?: string; date?: string };

function regrouperExclus(exclus: Record<string, string>): { raison: string; fichier?: string; ecarts: Ecart[] }[] {
  const groupes = new Map<string, { raison: string; fichier?: string; ecarts: Ecart[] }>();
  for (const [symbole, texte] of Object.entries(exclus)) {
    const r = /^(.*?)(?: selon (\S+))?\s*\(source : (\S+), (\d{4}-\d{2}-\d{2})\)$/.exec(texte);
    const raison = r ? r[1] : texte;
    const g = groupes.get(raison) ?? { raison, fichier: r?.[2], ecarts: [] };
    g.ecarts.push(r ? { symbole, url: r[3], date: r[4] } : { symbole });
    groupes.set(raison, g);
  }
  return [...groupes.values()];
}

export function CarteVerifications({ sortie }: { sortie: SortiePipeline }) {
  const g = sortie.gouvernance;
  const rejets = g.historique.filter((h) => !h.accepte);
  const exclus = regrouperExclus(sortie.exclus ?? {});
  const elements: Element[] = [
    ...rejets.map((h) => ({
      cle: `rejet-${h.essai}-${h.portefeuille}`,
      contenu: (
        <Ligne statut="retour" titre={`Essai ${h.essai} : ${h.portefeuille} rejeté, renvoyé au constructeur`}>
          Contrôle{h.rejets.length > 1 ? "s" : ""} non conforme{h.rejets.length > 1 ? "s" : ""} : {h.rejets.join(", ")}.
          {g.historique.some((k) => k.essai > h.essai && k.portefeuille === h.portefeuille && k.accepte)
            ? ` Corrigé à l'essai ${h.essai + 1}.` : ""}
        </Ligne>
      ),
    })),
    ...g.controles.map((c, i) => ({
      cle: `c${i}`,
      contenu: <Ligne statut={c.statut} titre={c.titre}><Texte>{c.detail}</Texte></Ligne>,
    })),
    ...(exclus.length
      ? [{ cle: "exclus", contenu: <h3 className="controles__intertitre">Écartés avant la construction</h3> }]
      : []),
    ...exclus.map((g) => ({
      cle: `x-${g.raison}`,
      contenu: (
        <Ligne statut="ecarte" titre={<>{typo(majuscule(g.raison))}{g.fichier ? <span className="controle__fichier"> · {g.fichier}</span> : null}</>}>
          {g.ecarts.map((e, i) => (
            <span key={e.symbole}>
              {i ? " · " : ""}
              {e.url ? (
                <a className="lien" href={e.url} target="_blank" rel="noreferrer"
                  aria-label={`${e.symbole} : source du ${formaterDate(e.date ?? null)}`}>{e.symbole}</a>
              ) : e.symbole}
            </span>
          ))}
          {g.ecarts.some((e) => e.url) ? <span className="controle__aide">Touchez un symbole pour sa source.</span> : null}
        </Ligne>
      ),
    })),
  ];
  return (
    <article className="carte">
      <Entete titre="Vérifications" />
      <p className="carte__chapeau">
        Portefeuille {g.portefeuille_retenu} accepté par la gouvernance · essai {g.essai} sur {g.essais_max}
      </p>
      <Pages elements={elements} classe="controles" />
    </article>
  );
}

// ---------- Pourquoi ----------

const NIVEAUX = ["En bref", "Les chiffres", "Le calcul"] as const;

export function CartePourquoi({ sortie }: { sortie: SortiePipeline }) {
  const e = sortie.explication;
  const [niveau, setNiveau] = useState<number>(e.niveau_par_defaut);
  const sujet: Element = { cle: "sujet", contenu: <p className="explication__sujet"><Texte>{e.sujet}</Texte></p> };
  const elements: Element[] =
    niveau === 1
      ? [sujet, { cle: "n1", contenu: <p className="explication__phrase"><Texte>{e.niveau1}</Texte></p> }]
      : niveau === 2
        ? [sujet, ...e.niveau2.map((t, i) => ({ cle: `n2-${i}`, contenu: <p className="puce"><Texte>{t}</Texte></p> }))]
        : [
          { cle: "formule", contenu: <p className="formule">{e.niveau3.formule}</p> },
          ...e.niveau3.lignes.map((t, i) => ({ cle: `n3-${i}`, contenu: <p className="puce puce--serree"><Texte>{t}</Texte></p> })),
        ];
  return (
    <article className="carte">
      <Entete titre="Pourquoi" />
      <div className="niveaux" role="tablist" aria-label="Niveau de détail">
        {NIVEAUX.map((nom, i) => (
          <button key={nom} type="button" role="tab" aria-selected={niveau === i + 1}
            className={niveau === i + 1 ? "niveau niveau--actif" : "niveau"} onClick={() => setNiveau(i + 1)}>
            {nom}
          </button>
        ))}
      </div>
      <div className="explication" role="tabpanel">
        <Pages elements={elements.map((x) => ({ ...x, cle: `${niveau}-${x.cle}` }))} classe="explication__liste" />
      </div>
      <p className="carte__pied">Touchez un chiffre souligné pour voir son calcul.</p>
    </article>
  );
}

// ---------- Limites ----------

const BLOCS = [
  ["faits", "Faits"],
  ["hypotheses", "Hypothèses"],
  ["limites", "Limites"],
] as const;

export function CarteLimites({ sortie }: { sortie: SortiePipeline }) {
  const [bloc, setBloc] = useState<(typeof BLOCS)[number][0]>("faits");
  const items = sortie.limites[bloc];
  return (
    <article className="carte">
      <Entete titre="Limites" />
      <div className="niveaux" role="tablist" aria-label="Faits, hypothèses et limites">
        {BLOCS.map(([cle, nom]) => (
          <button key={cle} type="button" role="tab" aria-selected={bloc === cle}
            className={`niveau niveau--${cle}${bloc === cle ? " niveau--actif" : ""}`} onClick={() => setBloc(cle)}>
            {nom} <span className="niveau__nombre">{sortie.limites[cle].length}</span>
          </button>
        ))}
      </div>
      <div className={`bloc bloc--${bloc}`} role="tabpanel">
        <Pages elements={items.map((t, i) => ({ cle: `${bloc}-${i}`, contenu: <p className="puce puce--bloc"><Texte>{t}</Texte></p> }))}
          classe="bloc__liste" />
      </div>
    </article>
  );
}
