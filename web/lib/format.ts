import type { Reference } from "./types";

// L'interface n'invente aucun chiffre : elle arrondit pour l'affichage une
// valeur brute venue de tools/, rien de plus.

const pourcent = new Intl.NumberFormat("fr-CA", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const decimal = new Intl.NumberFormat("fr-CA", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const entier = new Intl.NumberFormat("fr-CA", { maximumFractionDigits: 0 });

function signe(texte: string): string {
  return texte.replace(/^-/, "−");
}

export function formaterChiffre(ref: Reference): string {
  if (ref.unite.startsWith("coefficient")) return signe(decimal.format(ref.valeur));
  if (ref.unite.startsWith("fraction")) return signe(pourcent.format(ref.valeur));
  return signe(decimal.format(ref.valeur));
}

export function formaterPoids(poids: number): string {
  return `${entier.format(poids * 100)} %`;
}

export function formaterMontant(montant: number, devise: string): string {
  return `${entier.format(montant)} $ ${devise}`;
}

export function formaterDate(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, j] = iso.split("-").map(Number);
  const mois = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
  ];
  return `${j} ${mois[m - 1]} ${a}`;
}
