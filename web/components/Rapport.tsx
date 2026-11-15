"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Chiffre, FicheReference, FournisseurChiffres, Texte, typo } from "./Chiffres";
import { Camembert, Cours, Legende, LegendeCours, PhraseCours, SourceCours } from "./Graphiques";
import { formaterDate, formaterHorizon, formaterMontant, majuscule } from "@/lib/format";
import { chargerSortie, estPersona, PERSONAS } from "@/lib/personas";
import type { SortiePipeline } from "@/lib/types";

// Le dossier imprimable : tout le contenu des cartes sur des pages A4/Lettre,
// à enregistrer en PDF par l'impression du navigateur. Comme les cartes, il ne
// contient que des données du pipeline et de web/scripts/graphiques.py.

export const MENTION = "Simulation, ne constitue pas un conseil en placement";

const ICONE = { ok: "✓", alerte: "!", echec: "✕" } as const;
const REGROUPEMENTS = [["actif", "Par actif"], ["secteur", "Par secteur"], ["zone", "Par zone géographique"]] as const;

export function Rapport() {
  const params = useSearchParams();
  const id = params.get("persona");
  const imprimer = params.get("imprimer") !== "0";
  const [sortie, setSortie] = useState<SortiePipeline | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fiche, setFiche] = useState<string | null>(null);

  useEffect(() => {
    if (!estPersona(id)) {
      setErreur("Persona inconnu : choisissez robert, amira ou mateo.");
      return;
    }
    chargerSortie(id).then(setSortie, () => setErreur(`Je n'arrive pas à lire agents/sorties/${id}.json.`));
  }, [id]);

  useEffect(() => {
    if (!sortie || !imprimer) return;
    const t = window.setTimeout(() => window.print(), 400);
    return () => window.clearTimeout(t);
  }, [sortie, imprimer]);

  const ctx = useMemo(() => ({ chiffres: sortie?.chiffres ?? {}, ouvrir: setFiche }), [sortie]);
  if (erreur) return <main className="rapport"><p>{erreur}</p></main>;
  if (!sortie) return <main className="rapport"><p>Préparation du dossier…</p></main>;

  const persona = PERSONAS.find((p) => p.id === sortie.scenario);
  const profil = sortie.profil;
  const g = sortie.gouvernance;
  const ptf = sortie.portefeuilles.find((p) => p.id === g.portefeuille_retenu) ?? sortie.portefeuilles[0];
  const reps = sortie.graphiques.repartitions[ptf.id];
  const e = sortie.explication;
  const sources = Array.from(new Set(Object.values(sortie.chiffres).flatMap((r) => r.sources))).sort();
  const exclus = Object.entries(sortie.exclus ?? {});

  return (
    <FournisseurChiffres valeur={ctx}>
      <div className="rapport__ecran">
        <p className="rapport__mention rapport__mention--haut">{MENTION}</p>
        <main className="rapport">
          <header className="rapport__titre">
            <p className="rapport__surtitre">AlphaForge · dossier de portefeuille simulé</p>
            <h1>{profil.prenom}{persona ? `, ${persona.age} ans` : ""}</h1>
            <p>Sortie du pipeline du {formaterDate(sortie.meta?.date ?? null)} (agents/sorties/{sortie.scenario}.json). Portefeuille simulé retenu : {ptf.id}, « {typo(ptf.nom)} ».</p>
            <button type="button" className="bouton bouton--principal rapport__imprimer" onClick={() => window.print()}>Imprimer ou enregistrer en PDF</button>
          </header>

          <section>
            <h2>Profil</h2>
            <table className="rapport__table rapport__table--profil"><tbody>
              <tr><th>Horizon</th><td>{formaterHorizon(profil.horizon_annees)}</td></tr>
              <tr><th>But</th><td>{majuscule(profil.objectif)}</td></tr>
              <tr><th>Tolérance au risque</th><td>{majuscule(profil.tolerance_risque)}</td></tr>
              <tr><th>Connaissance</th><td>{majuscule(profil.connaissance)}</td></tr>
              <tr><th>Préférences</th><td>{profil.preferences.join(", ") || "Rien de particulier"}</td></tr>
              <tr><th>Exclusions</th><td>{profil.exclusions.join(", ") || "Rien"}</td></tr>
              <tr><th>Centres d&apos;intérêt</th><td>{profil.centres_interet.join(", ") || "Aucun"}</td></tr>
              <tr><th>Capital fictif</th><td>{formaterMontant(profil.capital_fictif, profil.devise)}</td></tr>
              {profil.demande ? <tr><th>Demande</th><td>{typo(`« ${profil.demande} »`)}</td></tr> : null}
            </tbody></table>
            {persona?.choix.length ? <ul className="rapport__notes">{persona.choix.map((c) => <li key={c}>{typo(c)}</li>)}</ul> : null}
          </section>

          <section className="rapport__bloc">
            <h2>Répartition du portefeuille simulé {ptf.id}</h2>
            <p>{typo(ptf.intention)}</p>
            <div className="rapport__camemberts">
              {REGROUPEMENTS.map(([cle, nom]) => (
                <figure key={cle}>
                  <figcaption>{nom}</figcaption>
                  <Camembert parts={reps[cle]} taille={110} libelle={`Répartition ${nom.toLowerCase()}`} />
                  <Legende parts={reps[cle]} />
                </figure>
              ))}
            </div>
          </section>

          <section className="rapport__bloc">
            <h2>Cours de {sortie.graphiques.cours.nom} ({sortie.graphiques.cours.symbole})</h2>
            <Cours sortie={sortie} hauteur={130} />
            <LegendeCours sortie={sortie} />
            <PhraseCours sortie={sortie} />
            <SourceCours sortie={sortie} />
          </section>

          <section>
            <h2>Lignes du portefeuille simulé {ptf.id}</h2>
            <table className="rapport__table">
              <thead><tr><th>Actif</th><th>Rôle</th><th>Poids</th><th>Volatilité</th><th>Pire baisse</th><th>Part du risque</th></tr></thead>
              <tbody>
                {ptf.lignes.map((l) => (
                  <tr key={l.symbole}>
                    <td><strong>{l.symbole}</strong><br /><span className="rapport__petit">{l.nom} · {l.classe}</span></td>
                    <td>{typo(l.role)}</td>
                    <td><Chiffre id={reps.actif.find((p) => p.symboles[0] === l.symbole)?.id ?? ""} /></td>
                    <td><Chiffre id={ptf.volatilites[l.symbole]} /></td>
                    <td><Chiffre id={ptf.pires_baisses[l.symbole]} /></td>
                    <td><Chiffre id={ptf.parts_du_risque[l.symbole]} /></td>
                  </tr>
                ))}
                <tr className="rapport__total">
                  <td colSpan={3}>Portefeuille simulé {ptf.id}, en {profil.devise}</td>
                  <td><Chiffre id={ptf.volatilite} /></td>
                  <td><Chiffre id={ptf.pire_baisse} /></td>
                  <td />
                </tr>
              </tbody>
            </table>
          </section>

          <section>
            <h2>Contrôles de gouvernance</h2>
            <p>Portefeuille {g.portefeuille_retenu} accepté · essai {g.essai} sur {g.essais_max}.</p>
            <ul className="rapport__controles">
              {g.historique.filter((h) => !h.accepte).map((h) => (
                <li key={`${h.essai}${h.portefeuille}`}><span className="rapport__statut">↺</span> Essai {h.essai} : {h.portefeuille} rejeté ({h.rejets.join(", ")}), renvoyé au constructeur.</li>
              ))}
              {g.controles.map((c, i) => (
                <li key={i} className={`rapport__controle--${c.statut}`}>
                  <span className="rapport__statut">{ICONE[c.statut]}</span> <strong>{c.titre}.</strong> <Texte>{c.detail}</Texte>
                </li>
              ))}
            </ul>
            {exclus.length ? (
              <>
                <h3>Écartés avant la construction</h3>
                <ul className="rapport__liste">
                  {exclus.map(([s, r]) => <li key={s}><strong>{s}</strong> : <Texte>{r}</Texte></li>)}
                </ul>
              </>
            ) : null}
          </section>

          <section>
            <h2>Explication</h2>
            <p className="rapport__sujet"><Texte>{e.sujet}</Texte></p>
            <h3>En bref</h3>
            <p><Texte>{e.niveau1}</Texte></p>
            <h3>Les chiffres</h3>
            <ul className="rapport__liste">{e.niveau2.map((t) => <li key={t}><Texte>{t}</Texte></li>)}</ul>
          </section>

          <section>
            <h2>Limites</h2>
            {([["Faits", sortie.limites.faits], ["Hypothèses", sortie.limites.hypotheses], ["Limites", sortie.limites.limites]] as const).map(([titre, items]) => (
              <div key={titre}>
                <h3>{titre}</h3>
                <ul className="rapport__liste">{items.map((t) => <li key={t}><Texte>{t}</Texte></li>)}</ul>
              </div>
            ))}
          </section>

          <section>
            <h2>Sources</h2>
            <ul className="rapport__liste">
              {sources.map((s) => <li key={s}>{s}</li>)}
              <li>data/assets_universe.csv (secteur, marché), via web/scripts/graphiques.py</li>
              <li>agents/sorties/{sortie.scenario}.json : {sortie.note}</li>
            </ul>
            <p className="rapport__petit">Chaque chiffre souligné renvoie à l&apos;appel d&apos;outil qui l&apos;a produit (outil, paramètres, période, formule). Les données passées décrivent, elles ne promettent rien.</p>
          </section>
        </main>
        <p className="rapport__mention rapport__mention--bas">{MENTION}</p>
      </div>
      {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
    </FournisseurChiffres>
  );
}
