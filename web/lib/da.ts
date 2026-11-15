import fs from "node:fs";
import path from "node:path";

// Fichiers de la direction artistique (docs/da-eagle.md), copiés tels quels depuis le
// zip de la DA dans web/public/da/. Les noms sont ceux du zip ; le code s'y adapte.
// Lu au rendu serveur (donc au build) : un fichier absent laisse la valeur par défaut.

export type EtatAvatar = "ecoute" | "parle" | "reflechit";

export type DirectionArtistique = {
  /** Avatar animé par état de la conversation : avatar/eagle-avatar-<état>.svg */
  avatar: Record<EtatAvatar, string | null>;
  /** Emblème dans un disque : seule version permise sur fond clair. */
  badge: string | null;
  logoHorizontal: string | null;
  /** Illustrations par secteur et thème : clé = nom après « secteur- » (technologie, sante, energie…). */
  illustrations: Record<string, string>;
  /** Carte du monde à colorier par région (à charger en ligne, pas en <img>). */
  carte: string | null;
};

const DOSSIER = path.join(process.cwd(), "public", "da");

function existe(relatif: string): string | null {
  return fs.existsSync(path.join(DOSSIER, relatif)) ? `/da/${relatif}` : null;
}

export function lireDa(): DirectionArtistique {
  const illustrations: Record<string, string> = {};
  const dossier = path.join(DOSSIER, "illustrations");
  if (fs.existsSync(dossier)) {
    for (const f of fs.readdirSync(dossier)) {
      const m = /^secteur-(.+)\.svg$/.exec(f);
      if (m) illustrations[m[1]] = `/da/illustrations/${f}`;
    }
  }
  return {
    avatar: {
      ecoute: existe("avatar/eagle-avatar-ecoute.svg"),
      parle: existe("avatar/eagle-avatar-parle.svg"),
      reflechit: existe("avatar/eagle-avatar-reflechit.svg"),
    },
    badge: existe("logo/eagle-badge.svg"),
    logoHorizontal: existe("logo/eagle-logo-horizontal.svg"),
    illustrations,
    carte: existe("illustrations/carte-monde-neutre.svg"),
  };
}
