"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { Chiffre, Texte, typo } from "./Chiffres";
import { cleIllustration, Illustration } from "./Da";
import { rapproche, useFocus } from "./Focus";
import { Pages, type Element } from "./Pages";
import { formaterDate, formaterPoids, secteurEnFrancais } from "@/lib/format";
import type { Adequation, Ligne, Portefeuille, SortiePipeline } from "@/lib/types";

// Format v2 de la sortie (docs/sortie-pipeline.md, branche agents-eagle) :
// adéquation au profil, fiche de chaque ligne, limites propres au portefeuille.
// Un champ absent de la réponse s'affiche « information manquante » : rien n'est
// recalculé ni deviné ici.

export const MANQUE = "Information manquante";

export function Manque({ quoi }: { quoi?: string }) {
  return <span className="manque">{MANQUE}{quoi ? ` : ${quoi}` : ""}</span>;
}

const CRITERES: Record<string, string> = {
  horizon: "Horizon", objectif: "Objectif", tolerance: "Tolérance au risque", preferences: "Préférence",
  exclusions: "Exclusion", centres_interet: "Centre d'intérêt", capital: "Capital", demande: "Demande",
};

export function retenu(s: SortiePipeline): Portefeuille {
  return s.portefeuilles.find((p) => p.id === s.gouvernance.portefeuille_retenu) ?? s.portefeuilles[0];
}

// ---------- Pourquoi ce portefeuille vous correspond ----------

export function TableauAdequation({ s }: { s: SortiePipeline }) {
  const lignes: Adequation[] | undefined = retenu(s).adequation ?? s.adequation;
  if (!lignes) return <p className="diapo__manque"><Manque quoi="la réponse du pipeline ne contient pas de champ « adequation »." /></p>;
  const entete: Element = {
    cle: "entete",
    contenu: (
      <div className="adequation__ligne adequation__ligne--entete" aria-hidden="true">
        <span>Critère du profil</span><span>Ce que fait le portefeuille</span><span>Preuve chiffrée</span>
      </div>
    ),
  };
  return (
    <Pages classe="adequation" elements={[entete, ...lignes.map((a, i) => ({
      cle: `${a.critere}-${a.element ?? i}`,
      contenu: (
        <div className={`adequation__ligne adequation__ligne--${a.statut.replace(" ", "-")}`} style={{ "--rang": i } as CSSProperties}>
          <span className="adequation__critere">
            <strong>{CRITERES[a.critere] ?? a.critere}{a.element ? ` : ${a.element}` : ""}</strong>
            <span className="adequation__attente">{typo(a.attente)}</span>
          </span>
          <span className="adequation__reponse">
            <span className={`statut statut--${a.statut.replace(" ", "-")}`}>{a.statut}</span>
            <span className="adequation__texte"><Texte>{a.reponse}</Texte></span>
            {a.statut === "non couvert" ? <span className="adequation__raison">{a.raison ? typo(a.raison) : <Manque quoi="raison non fournie" />}</span> : null}
            {a.regle ? <span className="adequation__regle">Règle : {typo(a.regle)}</span> : null}
          </span>
          <span className="adequation__preuves">
            {a.chiffres?.length ? a.chiffres.map((id) => <Chiffre key={id} id={id} />) : <span className="adequation__aucune">—</span>}
          </span>
        </div>
      ),
    }))]} />
  );
}

// ---------- Une fiche par ligne ----------

function Champ({ nom, children }: { nom: string; children: ReactNode }) {
  return <div className="fiche-ligne__champ"><dt>{nom}</dt><dd>{children}</dd></div>;
}

function Sources({ sources }: { sources?: Ligne["sources"] }) {
  if (!sources?.length) return <Manque quoi="aucune source dans la réponse" />;
  return (
    <ul className="fiche-ligne__sources">
      {sources.map((src, i) => (
        <li key={i}>
          {src.url ? (
            <a className="lien lien--source" href={src.url} target="_blank" rel="noreferrer">
              {src.fichier} <ExternalLink aria-hidden="true" size={13} />
            </a>
          ) : <code>{src.fichier}</code>}
          <span className="fiche-ligne__objet"> · {typo(src.objet)}{src.date ? ` · ${formaterDate(src.date)}` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

/** Couleurs de la charte pour les lignes d'un portefeuille (chart-1 à 8, puis on recommence). */
const COULEURS_LIGNES = Array.from({ length: 8 }, (_, i) => `var(--chart-${i + 1})`);

export function FichesLignes({ s }: { s: SortiePipeline }) {
  const ptf = retenu(s);
  const [choix, setChoix] = useState(ptf.lignes[0]?.symbole);
  // La présentation vocale ouvre la fiche de la ligne dont elle parle.
  const focus = useFocus();
  useEffect(() => {
    const vise = focus ? ptf.lignes.find((x) => rapproche(x.symbole, focus.element) || rapproche(x.nom, focus.element)) : null;
    if (vise) setChoix(vise.symbole);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.n]);
  const l = ptf.lignes.find((x) => x.symbole === choix) ?? ptf.lignes[0];
  if (!l) return <p className="diapo__manque"><Manque quoi="le portefeuille retenu n'a pas de lignes." /></p>;
  const ch = l.chiffres ?? {};
  const vol = ch.volatilite ?? ptf.volatilites?.[l.symbole];
  const pb = ch.pire_baisse ?? ptf.pires_baisses?.[l.symbole];
  const part = ch.part_du_risque ?? ptf.parts_du_risque?.[l.symbole];
  return (
    <div className="fiches-lignes">
      {/* Le capital en une barre : une couleur par ligne, la même que sur son onglet. Toucher un segment ouvre la fiche. */}
      <div className="lignes-barre" role="img" aria-label={`Répartition du capital : ${ptf.lignes.map((x) => `${x.symbole} ${formaterPoids(x.poids)}`).join(", ")}`}>
        {ptf.lignes.map((x, i) => (
          <button key={x.symbole} type="button" tabIndex={-1} title={`${x.nom} : ${formaterPoids(x.poids)}`}
            className={x.symbole === l.symbole ? "lignes-barre__part lignes-barre__part--actif" : "lignes-barre__part"}
            style={{ flexGrow: x.poids, background: COULEURS_LIGNES[i % COULEURS_LIGNES.length] }} onClick={() => setChoix(x.symbole)}>
            {x.poids >= 0.09 ? <span>{x.symbole}</span> : null}
          </button>
        ))}
      </div>
      <div className="fiches-lignes__onglets" role="tablist" aria-label="Lignes du portefeuille">
        {ptf.lignes.map((x, i) => (
          <button key={x.symbole} type="button" role="tab" aria-selected={x.symbole === l.symbole}
            className={x.symbole === l.symbole ? "onglet onglet--actif" : "onglet"} onClick={() => setChoix(x.symbole)}>
            <span className="onglet__pastille" style={{ background: COULEURS_LIGNES[i % COULEURS_LIGNES.length] }} aria-hidden="true" />
            <span className="onglet__symbole">{x.symbole}</span><span className="onglet__poids">{formaterPoids(x.poids)}</span>
          </button>
        ))}
      </div>
      <article className="fiche-ligne" key={l.symbole} role="tabpanel">
        <header className="fiche-ligne__entete">
          <Illustration taille={72} cle={cleIllustration(
            { etf_bond: "obligations", etf_commodity: "or", crypto: "crypto" }[l.classe_code], l.secteur, l.nom)} />
          <div className="fiche-ligne__titre">
            <h3 className="fiche-ligne__nom">{l.nom}</h3>
            <p className="fiche-ligne__symbole">{l.symbole} · {typo(l.role)}</p>
          </div>
          <p className="fiche-ligne__poids">{l.poids_id ? <Chiffre id={l.poids_id} /> : formaterPoids(l.poids)}<span>du capital</span></p>
        </header>
        <div className="fiche-ligne__corps">
          <dl className="fiche-ligne__identite">
            <Champ nom="Classe">{l.classe || <Manque />}</Champ>
            <Champ nom="Secteur">{l.secteur ? secteurEnFrancais(l.secteur) : <Manque />}</Champ>
            <Champ nom="Pays">{l.pays ?? <Manque />}</Champ>
            <Champ nom="Devise">{l.devise ?? <Manque />}</Champ>
            <Champ nom="Volatilité">{vol ? <Chiffre id={vol} /> : <Manque />}</Champ>
            <Champ nom="Pire baisse">{pb ? <Chiffre id={pb} /> : <Manque />}</Champ>
            <Champ nom="Part du risque">{part ? <Chiffre id={part} /> : <Manque />}</Champ>
          </dl>
          {/* Justification, alternative écartée et sources : paginées si elles dépassent, rien ne défile. */}
          <div className="fiche-ligne__raisons">
            <Pages classe="fiche-ligne__raisons-liste" elements={[
              { cle: "t-pourquoi", contenu: <h4>Pourquoi cette ligne, pour votre profil</h4> },
              {
                cle: "pourquoi",
                contenu: (
                  <p>{l.pourquoi ? <Texte>{l.pourquoi}</Texte> : <Manque quoi="justification absente de la réponse" />}
                    {l.critere_profil ? <span className="fiche-ligne__critere"> Critère servi : {CRITERES[l.critere_profil] ?? l.critere_profil}.</span> : null}</p>
                ),
              },
              ...(l.plutot_que ? [{
                cle: "plutot",
                contenu: <p className="fiche-ligne__plutot">Plutôt que <strong>{l.plutot_que.symbole}</strong> : <Texte>{l.plutot_que.raison}</Texte></p>,
              }] : []),
              { cle: "t-sources", contenu: <h4>Sources</h4> },
              { cle: "sources", contenu: <Sources sources={l.sources} /> },
            ].map((e) => ({ ...e, cle: `${l.symbole}-${e.cle}` }))} />
          </div>
        </div>
      </article>
    </div>
  );
}

// ---------- Limites et hypothèses ----------

export function LimitesPortefeuille({ s }: { s: SortiePipeline }) {
  const L = s.limites;
  const [voirMethode, setVoirMethode] = useState(false);
  const specifiques = L.limites_specifiques ? [...L.limites_specifiques].sort((a, b) => a.importance - b.importance) : undefined;
  const hypotheses = L.hypotheses_specifiques;
  const elements: Element[] = [
    { cle: "t-lim", contenu: <h3 className="limites__intertitre">Limites propres à ce portefeuille</h3> },
    ...(specifiques
      ? specifiques.map((x, i) => ({
        cle: `l${i}`,
        contenu: (
          <div className="limite" style={{ "--rang": i } as CSSProperties}>
            <span className="limite__rang" aria-label={`Importance ${x.importance}`}>{x.importance}</span>
            <p><Texte>{x.texte}</Texte></p>
          </div>
        ),
      }))
      : [{ cle: "l-manque", contenu: <p className="diapo__manque"><Manque quoi="la réponse ne contient pas de limites propres au portefeuille (limites_specifiques)." /></p> }]),
    { cle: "t-hyp", contenu: <h3 className="limites__intertitre">Hypothèses dont il dépend</h3> },
    ...(hypotheses
      ? hypotheses.map((h, i) => ({
        cle: `h${i}`,
        contenu: (
          <div className="hypothese" style={{ "--rang": i } as CSSProperties}>
            <p><Texte>{h.texte}</Texte></p>
            <p className="hypothese__tombe"><strong>Si elle ne tient pas :</strong> <Texte>{h.si_elle_tombe}</Texte></p>
          </div>
        ),
      }))
      : [{ cle: "h-manque", contenu: <p className="diapo__manque"><Manque quoi="la réponse ne contient pas d'hypothèses propres au portefeuille (hypotheses_specifiques)." /></p> }]),
  ];
  const methode = L.methode ?? [...L.faits, ...L.hypotheses, ...L.limites];
  return (
    <div className="limites-ptf">
      {voirMethode ? (
        <Pages classe="limites__liste" elements={[
          { cle: "t-meth", contenu: <h3 className="limites__intertitre">Méthode générale</h3> },
          ...methode.map((t, i) => ({ cle: `m${i}`, contenu: <p className="puce"><Texte>{t}</Texte></p> })),
        ]} />
      ) : <Pages classe="limites__liste" elements={elements} />}
      <button type="button" className="bouton-texte" aria-expanded={voirMethode} onClick={() => setVoirMethode(!voirMethode)}>
        {voirMethode ? "Revenir aux limites de ce portefeuille" : `Méthode générale (${methode.length})`}
      </button>
    </div>
  );
}
