"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Chiffre } from "./Chiffres";
import type { DirectionArtistique, EtatAvatar } from "@/lib/da";
import type { Part } from "@/lib/types";

// Éléments de la direction artistique (docs/da-eagle.md) : avatar à états, illustrations
// par secteur et thème, carte du monde. Les fichiers sont dans web/public/da/.

const VIDE: DirectionArtistique = {
  avatar: { ecoute: null, parle: null, reflechit: null }, badge: null, logoHorizontal: null, illustrations: {}, carte: null,
};
const DaCtx = createContext<DirectionArtistique>(VIDE);

export function FournisseurDa({ da, children }: { da: DirectionArtistique | null; children: ReactNode }) {
  return <DaCtx.Provider value={da ?? VIDE}>{children}</DaCtx.Provider>;
}

export function useDa() {
  return useContext(DaCtx);
}

// ---------- Avatar ----------

const ETATS: Record<EtatAvatar, string> = { ecoute: "écoute", parle: "parle", reflechit: "réfléchit" };

/** Avatar d'Eagle selon l'état de la conversation : « écoute » (en attente d'une réponse),
 *  « parle » (la voix émet), « réfléchit » (calcul du portefeuille). */
export function Avatar({ etat, taille = 150, repli }: { etat: EtatAvatar; taille?: number; repli: ReactNode }) {
  const { avatar } = useDa();
  const src = avatar[etat];
  return (
    <div className="avatar" data-state={etat} role="img" aria-label={`Eagle, ${ETATS[etat]}`}>
      {src ? (
        // Les trois SVG sont animés (SMIL) : on les garde montés et on ne montre que l'état courant.
        (Object.keys(avatar) as EtatAvatar[]).map((e) => avatar[e] ? (
          <img key={e} src={avatar[e]!} alt="" width={taille} height={taille} className={e === etat ? "avatar__image avatar__image--actif" : "avatar__image"} />
        ) : null)
      ) : repli}
      <div className="eg-voice" data-active={etat === "parle"} aria-hidden="true"><span /><span /><span /><span /></div>
    </div>
  );
}

// ---------- Illustrations par secteur et thème ----------

const MOTS: [RegExp, string][] = [
  [/jeu.?vid|gaming/i, "jeu-video"],
  [/crypto|bitcoin|ether/i, "crypto"],
  [/oblig|bond/i, "obligations"],
  [/^or\b|gold|or,/i, "or"],
  [/immobil|real estate/i, "immobilier"],
  [/sant|health/i, "sante"],
  [/[ée]nergie|energy/i, "energie"],
  [/financ|banque|assur/i, "finance"],
  [/technolog|information technology|^techno/i, "technologie"],
];

/** Clé d'illustration pour un secteur, un thème ou une classe d'actif ; null si la DA n'en a pas. */
export function cleIllustration(...textes: (string | undefined | null)[]): string | null {
  for (const t of textes) {
    if (!t) continue;
    for (const [re, cle] of MOTS) if (re.test(t)) return cle;
  }
  return null;
}

export function Illustration({ cle, taille = 64, titre }: { cle: string | null; taille?: number; titre?: string }) {
  const { illustrations } = useDa();
  const src = cle ? illustrations[cle] : undefined;
  if (!src) return null;
  return <img className="illustration" src={src} width={taille} height={taille} alt={titre ?? ""} aria-hidden={titre ? undefined : true} />;
}

// ---------- Carte du monde ----------

/** Carte en hexagones chargée en ligne pour colorer chaque région exposée (docs/da-eagle.md).
 *  Les régions sans exposition gardent la couleur neutre du fichier. */
export function CarteMonde({ parts, titre }: { parts: Part[]; titre: string }) {
  const { carte } = useDa();
  const [svg, setSvg] = useState<string | null>(null);
  const [actif, setActif] = useState<string | null>(null);
  useEffect(() => {
    if (!carte) return;
    let vivant = true;
    fetch(carte).then((r) => r.text()).then((t) => { if (vivant) setSvg(t); }, () => {});
    return () => { vivant = false; };
  }, [carte]);
  const regions = parts.filter((p) => p.region);
  const hors = parts.filter((p) => !p.region);
  const style = regions.map((p) => `.carte-monde #${p.region}{fill:${p.couleur};opacity:${actif && actif !== p.id ? 0.35 : 1}}`).join("");
  return (
    <figure className="anneau carte-monde" onMouseLeave={() => setActif(null)}>
      <figcaption>{titre}</figcaption>
      <div className="carte-monde__dessin">
        {svg ? (
          <>
            <style>{style}</style>
            {/* Fichier de la charte, servi par ce site (web/public/da/illustrations/). */}
            <div className="carte-monde__svg" dangerouslySetInnerHTML={{ __html: svg }} />
          </>
        ) : <p className="manque">{carte ? "Chargement de la carte…" : "Information manquante : carte du monde absente de web/public/da/."}</p>}
      </div>
      <ul className="anneau__legende">
        {regions.map((p) => (
          <li key={p.id} className={actif === p.id ? "anneau__entree anneau__entree--actif" : actif ? "anneau__entree anneau__entree--terne" : "anneau__entree"}
            onMouseEnter={() => setActif(p.id)} title={p.symboles.join(", ")}>
            <span className="anneau__pastille" style={{ background: p.couleur }} aria-hidden="true" />
            <span className="anneau__nom">{p.libelle}</span>
            <Chiffre id={p.id} />
          </li>
        ))}
        {hors.map((p) => (
          <li key={p.id} className="anneau__entree anneau__entree--hors" title={p.symboles.join(", ")}>
            <span className="anneau__pastille anneau__pastille--hors" aria-hidden="true" />
            <span className="anneau__nom">{p.libelle} (hors carte)</span>
            <Chiffre id={p.id} />
          </li>
        ))}
      </ul>
    </figure>
  );
}
