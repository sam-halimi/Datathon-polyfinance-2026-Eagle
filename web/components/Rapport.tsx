"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Chiffre, FicheReference, FournisseurChiffres, Texte, typo } from "./Chiffres";
import { useLangue } from "./Langue";
import { BarrePoids, CamembertPlein, COULEURS, CourbeCours, EventailFixe, Source, sourceCourte } from "./DossierGraphiques";
import { formaterDate, formaterHorizon, formaterMontant, formaterPoids, majuscule, secteurEnFrancais } from "@/lib/format";
import { chargerSortie, CLE_DOSSIER, estPersona, PERSONAS } from "@/lib/personas";
import { completerGraphiques } from "@/lib/repartition";
import { lireEventail } from "@/lib/scenarios";
import type { SortiePipeline } from "@/lib/types";

// Le dossier exporté : tout le résultat sur des pages A4 ou Lettre, à enregistrer en PDF par
// l'impression du navigateur. Il ne contient que des données du pipeline et des fichiers de data/.
// Les données clés portent leur provenance entre parenthèses ; la liste complète est à la fin.

export const MENTION = "Simulation, ne constitue pas un conseil en placement";

const ICONE = { ok: "✓", alerte: "!", echec: "✕" } as const;
const CRITERES: Record<string, string> = {
  horizon: "Horizon", objectif: "Objectif", tolerance: "Tolérance au risque", preferences: "Préférence",
  exclusions: "Exclusion", centres_interet: "Centre d'intérêt", capital: "Capital", demande: "Demande",
};

export function Rapport() {
  const params = useSearchParams();
  const id = params.get("persona");
  const imprimer = params.get("imprimer") !== "0";
  const [sortie, setSortie] = useState<SortiePipeline | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fiche, setFiche] = useState<string | null>(null);

  // /rapport?source=analyse : le dossier de l'analyse affichée, déposée par l'écran principal
  // dans le stockage local du navigateur (rien n'est envoyé ailleurs). Sinon, un persona.
  const enDirect = params.get("source") === "analyse";
  const langue = useLangue(); // installe aussi la traduction de l'interface sur cette page
  useEffect(() => {
    if (enDirect) {
      try {
        const brut = window.localStorage.getItem(CLE_DOSSIER);
        if (!brut) throw new Error("vide");
        void completerGraphiques(JSON.parse(brut) as SortiePipeline).then(setSortie);
      } catch {
        setErreur("Aucune analyse à exporter : relancez l'analyse dans l'écran principal, puis « Exporter le dossier ».");
      }
      return;
    }
    if (!estPersona(id)) {
      setErreur("Persona inconnu : choisissez robert, amira ou mateo.");
      return;
    }
    chargerSortie(id, langue).then(completerGraphiques).then(setSortie, () => setErreur(`Je n'arrive pas à lire agents/sorties/${id}.json.`));
  }, [id, enDirect, langue]);

  useEffect(() => {
    if (!sortie || !imprimer) return;
    const t = window.setTimeout(() => window.print(), 600);
    return () => window.clearTimeout(t);
  }, [sortie, imprimer]);

  const ev = useMemo(() => (sortie ? lireEventail(sortie) : null), [sortie]);
  const ctx = useMemo(() => ({ chiffres: { ...(sortie?.chiffres ?? {}), ...(ev?.chiffres ?? {}) }, ouvrir: setFiche }), [sortie, ev]);
  if (erreur) return <main className="dossier"><p>{erreur}</p></main>;
  if (!sortie) return <main className="dossier"><p>Préparation du dossier…</p></main>;

  const persona = enDirect ? undefined : PERSONAS.find((p) => p.id === sortie.scenario);
  const origine = enDirect ? "réponse de POST /analyse, profil saisi à l'écran" : `agents/sorties/${sortie.scenario}.json`;
  const profil = sortie.profil;
  const g = sortie.gouvernance;
  const ptf = sortie.portefeuilles.find((p) => p.id === g.portefeuille_retenu) ?? sortie.portefeuilles[0];
  const reps = sortie.graphiques.repartitions[ptf.id];
  const c = sortie.chiffres;
  const e = sortie.explication;
  const cours = sortie.graphiques.cours;
  const pb = cours ? c[cours.reference] : undefined;
  const retour = typeof pb?.details?.date_retour === "string" ? pb.details.date_retour : null;
  const adequation = ptf.adequation ?? sortie.adequation ?? [];
  const sources = Array.from(new Set(Object.values(sortie.chiffres).flatMap((r) => r.sources))).sort();
  const exclus = Object.entries(sortie.exclus ?? {});
  const plusLourde = [...ptf.lignes].sort((a, b) => b.poids - a.poids)[0];
  const idPoids = (symbole: string) => reps.actif.find((p) => p.symboles[0] === symbole && p.symboles.length === 1)?.id ?? "";
  const limites = sortie.limites;

  return (
    <FournisseurChiffres valeur={ctx}>
      <div className="dossier__ecran">
        <p className="dossier__mention">{MENTION}</p>
        <main className="dossier">
          <header className="dossier__tete">
            <div>
              <p className="dossier__surtitre">Eagle · dossier de portefeuille simulé</p>
              <h1>{profil.prenom || "Votre profil"}{persona ? `, ${persona.age} ans` : ""}</h1>
              <p className="dossier__chapeau">
                {typo(`Portefeuille simulé ${ptf.id} : « ${ptf.nom} ».`)}{" "}
                {sortie.vue ? `Autre proposition consultée ; la gouvernance a retenu la proposition ${sortie.vue.retenu}. ` : ""}
                Analyse du {formaterDate(sortie.meta?.date ?? null)}<Source>{origine}</Source>.
              </p>
            </div>
            <button type="button" className="bouton bouton--principal dossier__imprimer" onClick={() => window.print()}>Imprimer ou enregistrer en PDF</button>
          </header>

          <section className="dossier__cles" aria-label="Données clés">
            <div className="dossier__cle">
              <span>Variation annuelle (volatilité)</span>
              <strong><Chiffre id={ptf.volatilite} /></strong>
              <small><Source>{sourceCourte(c[ptf.volatilite]) ?? "information manquante"}</Source></small>
            </div>
            <div className="dossier__cle">
              <span>Pire baisse passée</span>
              <strong><Chiffre id={ptf.pire_baisse} /></strong>
              <small><Source>{sourceCourte(c[ptf.pire_baisse]) ?? "information manquante"}</Source></small>
            </div>
            <div className="dossier__cle">
              <span>Ligne la plus lourde</span>
              <strong>{plusLourde ? <>{plusLourde.symbole} · {idPoids(plusLourde.symbole) ? <Chiffre id={idPoids(plusLourde.symbole)} /> : formaterPoids(plusLourde.poids)}</> : "—"}</strong>
              <small><Source>poids du portefeuille simulé {ptf.id}</Source></small>
            </div>
            <div className="dossier__cle">
              <span>Capital fictif</span>
              <strong>{formaterMontant(profil.capital_fictif, profil.devise)}</strong>
              <small><Source>votre profil</Source></small>
            </div>
          </section>

          <section>
            <h2>Votre profil</h2>
            <dl className="dossier__profil">
              <div><dt>Horizon</dt><dd>{formaterHorizon(profil.horizon_annees)}</dd></div>
              <div><dt>Objectif</dt><dd>{majuscule(profil.objectif)}</dd></div>
              <div><dt>Tolérance au risque</dt><dd>{majuscule(profil.tolerance_risque)}</dd></div>
              <div><dt>Connaissance</dt><dd>{profil.connaissance_niveau ? `Niveau ${profil.connaissance_niveau} sur 5` : majuscule(profil.connaissance ?? "")}</dd></div>
              <div><dt>Préférences</dt><dd>{profil.preferences.join(", ") || "Rien de particulier"}</dd></div>
              <div><dt>Exclusions</dt><dd>{profil.exclusions.join(", ") || "Aucune"}</dd></div>
              <div><dt>Thèmes d&apos;intérêt</dt><dd>{profil.centres_interet.join(", ") || "Aucun"}</dd></div>
              <div><dt>Capital fictif</dt><dd>{formaterMontant(profil.capital_fictif, profil.devise)}</dd></div>
            </dl>
            {profil.demande ? <p className="dossier__demande">{typo(`Votre demande : « ${profil.demande} »`)}</p> : null}
            {persona?.choix.length ? <ul className="dossier__liste dossier__liste--discrete">{persona.choix.map((x) => <li key={x}>{typo(x)}</li>)}</ul> : null}
          </section>

          <section className="dossier__bloc">
            <h2>Répartition du portefeuille simulé {ptf.id}</h2>
            <p>{typo(ptf.intention)}</p>
            <div className="dossier__camemberts">
              <CamembertPlein titre="Par classe d'actif" parts={reps.classe ?? []} />
              <CamembertPlein titre="Par secteur" parts={reps.secteur ?? []} />
              <CamembertPlein titre="Par zone" parts={reps.zone ?? []} />
            </div>
            <p className="dossier__note">
              Parts du capital fictif, pas une mesure de marché<Source>poids du portefeuille simulé {ptf.id} ; classe, secteur et marché de chaque actif : data/assets_universe.csv et data/univers_etendu.csv</Source>.
            </p>
          </section>

          <section>
            <h2>Les lignes</h2>
            <table className="dossier__table">
              <thead><tr><th>Actif</th><th>Rôle</th><th className="dossier__num">Poids</th><th className="dossier__num">Volatilité</th><th className="dossier__num">Pire baisse</th><th className="dossier__num">Part du risque</th></tr></thead>
              <tbody>
                {ptf.lignes.map((l, i) => (
                  <tr key={l.symbole}>
                    <td>
                      <strong><span className="dossier__pastille" style={{ background: COULEURS[i % COULEURS.length] }} aria-hidden="true" /> {l.symbole}</strong>
                      <span className="dossier__petit">{l.nom} · {l.classe}{l.secteur ? ` · ${secteurEnFrancais(l.secteur)}` : ""}</span>
                    </td>
                    <td>{typo(l.role)}</td>
                    <td className="dossier__num">
                      {idPoids(l.symbole) ? <Chiffre id={idPoids(l.symbole)} /> : formaterPoids(l.poids)}
                      <BarrePoids poids={l.poids / (plusLourde?.poids || 1)} couleur={COULEURS[i % COULEURS.length]} />
                    </td>
                    <td className="dossier__num"><Chiffre id={ptf.volatilites[l.symbole]} /></td>
                    <td className="dossier__num"><Chiffre id={ptf.pires_baisses[l.symbole]} /></td>
                    <td className="dossier__num"><Chiffre id={ptf.parts_du_risque[l.symbole]} /></td>
                  </tr>
                ))}
                <tr className="dossier__total">
                  <td colSpan={3}>Portefeuille simulé {ptf.id}, en {profil.devise}</td>
                  <td className="dossier__num"><Chiffre id={ptf.volatilite} /></td>
                  <td className="dossier__num"><Chiffre id={ptf.pire_baisse} /></td>
                  <td />
                </tr>
              </tbody>
            </table>
            <p className="dossier__note">
              Mesures passées, sur la fenêtre de données<Source>{sourceCourte(c[ptf.volatilite]) ?? "outils de tools/"} ; part du risque : {sourceCourte(c[Object.values(ptf.parts_du_risque)[0]]) ?? "parts_du_risque"}</Source>. Elles décrivent, elles ne promettent rien.
            </p>
            <ul className="dossier__liste">
              {ptf.lignes.filter((l) => l.pourquoi).map((l) => <li key={l.symbole}><strong>{l.symbole}</strong> : <Texte>{l.pourquoi!}</Texte></li>)}
            </ul>
          </section>

          {cours ? (
            <section className="dossier__bloc">
              <h2>Cours de {cours.nom} ({cours.symbole})</h2>
              <CourbeCours points={cours.points} devise={cours.devise} pic={cours.date_pic} creux={cours.date_creux} retour={retour} nom={cours.nom} />
              <p>
                Sur la fenêtre, {cours.nom} a perdu <Chiffre id={cours.reference} /> entre son sommet du {formaterDate(cours.date_pic)} et son creux du {formaterDate(cours.date_creux)}
                {retour ? `, puis a retrouvé son sommet le ${formaterDate(retour)}` : " ; il n'avait pas retrouvé son sommet à la fin de la fenêtre"}
                <Source>{cours.sources.join(", ")} ; baisse calculée par {sourceCourte(pb) ?? "pire_baisse"}</Source>.
                {c[`rattrapage_${cours.id}`] ? <> Pour effacer cette baisse, il fallait un gain de <Chiffre id={`rattrapage_${cours.id}`} />.</> : null}
                {c[`vol_${cours.id}`] ? <> Variation typique par an : <Chiffre id={`vol_${cours.id}`} />.</> : null}
              </p>
              <p className="dossier__note">Zone ombrée : la pire baisse. Le passé ne promet rien.</p>
            </section>
          ) : null}

          <section className="dossier__bloc">
            <h2>Scénarios, pas une prévision</h2>
            {ev ? (
              <>
                <EventailFixe ev={ev} />
                <ul className="dossier__cles-graphique">
                  <li><i style={{ background: "var(--chart-2)" }} /> Médiane à l&apos;horizon : <Chiffre id="scen_p50_fin" /></li>
                  <li><i style={{ background: "var(--chart-3)", opacity: 0.6 }} /> Un scénario sur deux</li>
                  <li><i style={{ background: "var(--chart-1)", opacity: 0.45 }} /> Huit sur dix : de <Chiffre id="scen_p10_fin" /> à <Chiffre id="scen_p90_fin" /></li>
                </ul>
                <p>
                  <strong>{ev.avertissement ?? "Ce n'est pas une prévision."}</strong>
                  <Source>{sourceCourte(ev.chiffres.scen_p50_fin) ?? "eventail_scenarios"}, mois observés tirés au hasard</Source>
                </p>
                <ul className="dossier__liste dossier__liste--discrete">{ev.hypotheses.map((h) => <li key={h}>{typo(h)}</li>)}</ul>
              </>
            ) : <p className="manque">Information manquante : cette sortie ne contient pas d&apos;éventail de scénarios. Rien n&apos;est tracé à sa place.</p>}
          </section>

          {adequation.length ? (
            <section>
              <h2>Pourquoi ce portefeuille vous correspond</h2>
              <table className="dossier__table dossier__table--adequation">
                <thead><tr><th>Critère du profil</th><th>Statut</th><th>Ce que fait le portefeuille</th></tr></thead>
                <tbody>
                  {adequation.map((a, i) => (
                    <tr key={`${a.critere}-${a.element ?? i}`}>
                      <td><strong>{CRITERES[a.critere] ?? a.critere}{a.element ? ` : ${a.element}` : ""}</strong><span className="dossier__petit">{typo(a.attente)}</span></td>
                      <td><span className={`statut statut--${a.statut.replace(" ", "-")}`}>{a.statut}</span></td>
                      <td><Texte>{a.reponse}</Texte>{a.statut === "non couvert" && a.raison ? <span className="dossier__petit">{typo(a.raison)}</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          <section>
            <h2>Contrôles de gouvernance</h2>
            <p>Portefeuille {g.portefeuille_retenu} accepté · essai {g.essai} sur {g.essais_max}<Source>tools/gouvernance.py, verifier_contraintes</Source>.</p>
            <ul className="dossier__controles">
              {g.historique.filter((h) => !h.accepte).map((h) => (
                <li key={`${h.essai}${h.portefeuille}`}><span className="dossier__statut">↺</span><span>Essai {h.essai} : {h.portefeuille} rejeté ({h.rejets.join(", ")}), renvoyé au constructeur.</span></li>
              ))}
              {g.controles.map((k, i) => (
                <li key={i} className={`dossier__controle--${k.statut}`}>
                  <span className="dossier__statut">{ICONE[k.statut]}</span><span><strong>{k.titre}.</strong> <Texte>{k.detail}</Texte></span>
                </li>
              ))}
            </ul>
            {exclus.length ? (
              <>
                <h3>Écartés avant la construction</h3>
                <ul className="dossier__liste">{exclus.map(([s, r]) => <li key={s}><strong>{s}</strong> : <Texte>{r}</Texte></li>)}</ul>
              </>
            ) : null}
          </section>

          <section>
            <h2>Explication</h2>
            {sortie.vue ? <p className="dossier__note">L&apos;explication ci-dessous a été rédigée pour la proposition {sortie.vue.retenu}, retenue par la gouvernance.</p> : null}
            <p className="dossier__phrase"><Texte>{e.niveau1}</Texte></p>
            <ul className="dossier__liste">{e.niveau2.map((t) => <li key={t}><Texte>{t}</Texte></li>)}</ul>
          </section>

          <section>
            <h2>Limites et hypothèses</h2>
            {limites.limites_specifiques?.length ? (
              <>
                <h3>Propres à ce portefeuille</h3>
                <ul className="dossier__liste">{[...limites.limites_specifiques].sort((x, y) => x.importance - y.importance).map((x) => <li key={x.texte}><Texte>{x.texte}</Texte></li>)}</ul>
              </>
            ) : null}
            {([["Faits", limites.faits], ["Hypothèses", limites.hypotheses], ["Limites générales", limites.limites]] as const).map(([titre, items]) => (
              <div key={titre}>
                <h3>{titre}</h3>
                <ul className="dossier__liste">{items.map((t) => <li key={t}><Texte>{t}</Texte></li>)}</ul>
              </div>
            ))}
          </section>

          <section>
            <h2>Toutes les sources</h2>
            <ul className="dossier__liste dossier__liste--discrete">
              {sources.map((s) => <li key={s}>{s}</li>)}
              <li>{origine} : {sortie.note}</li>
            </ul>
            <p className="dossier__note">Chaque chiffre souligné renvoie à l&apos;appel d&apos;outil qui l&apos;a produit (outil, paramètres, période, formule) : touchez-le à l&apos;écran pour l&apos;ouvrir.</p>
          </section>
        </main>
        <p className="dossier__mention">{MENTION}</p>
      </div>
      {fiche ? <FicheReference id={fiche} fermer={() => setFiche(null)} /> : null}
    </FournisseurChiffres>
  );
}
