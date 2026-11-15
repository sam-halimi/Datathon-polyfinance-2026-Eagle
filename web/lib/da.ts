import fs from "node:fs";
import path from "node:path";

// Fichiers de la direction artistique, déposés dans web/public/da/ par l'équipe DA.
// Lu au moment du rendu serveur (et donc du build) : un fichier ajouté est pris en
// compte au prochain build. Aucun fichier : l'interface garde ses valeurs par défaut.

export type DirectionArtistique = { tokens: boolean; avatar: string | null; logo: string | null };

function trouver(noms: string[]): string | null {
  for (const n of noms) {
    if (fs.existsSync(path.join(process.cwd(), "public", "da", n))) return `/da/${n}`;
  }
  return null;
}

export function lireDa(): DirectionArtistique {
  return {
    tokens: trouver(["tokens.css"]) !== null,
    avatar: trouver(["avatar.svg", "avatar.png", "avatar.webp"]),
    logo: trouver(["logo.svg", "logo.png"]),
  };
}
