// Comptes d'Eagle (agents/comptes.py) : un identifiant et un mot de passe gardés par Amazon Cognito.
// Le site ne conserve que le jeton d'accès, dans le stockage local du navigateur, le temps de sa validité.
// Actifs seulement sur le site déployé (NEXT_PUBLIC_COMPTES=1, posé par deploiement/deployer.py) :
// en local, le serveur n'exige rien et aucun écran de connexion n'apparaît.

export const COMPTES_ACTIFS = process.env.NEXT_PUBLIC_COMPTES === "1";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CLE = "eagle:session";

export type Session = { identifiant: string; jeton: string; expire: number };

export const REGLE_IDENTIFIANT = "3 à 32 caractères : lettres sans accent, chiffres, point, tiret ou tiret bas.";
export const REGLE_MOT_DE_PASSE = "Au moins 8 caractères, dont une minuscule et un chiffre.";

/** Session en cours, ou null si personne n'est connecté ou si le jeton a expiré. */
export function lireSession(): Session | null {
  try {
    const s = JSON.parse(window.localStorage.getItem(CLE) ?? "null") as Session | null;
    if (!s?.jeton || !s.identifiant || s.expire <= Date.now()) return null;
    return s;
  } catch {
    return null;
  }
}

export function fermerSession(): void {
  try { window.localStorage.removeItem(CLE); } catch { /* stockage indisponible : rien à retirer */ }
}

/** En-tête à joindre aux appels protégés (analyse, scénarios, fiche d'actif). */
export function enteteCompte(): Record<string, string> {
  const s = COMPTES_ACTIFS && typeof window !== "undefined" ? lireSession() : null;
  return s ? { Authorization: `Bearer ${s.jeton}` } : {};
}

/** Crée un compte ou connecte : renvoie la session, ou lève une erreur dont le message se lit tel quel. */
export async function ouvrirSession(action: "creer" | "connexion", identifiant: string, motDePasse: string): Promise<Session> {
  let r: Response;
  try {
    r = await fetch(`${API}/compte/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifiant, mot_de_passe: motDePasse }),
    });
  } catch {
    throw new Error("Le service des comptes ne répond pas. Vérifiez votre connexion, puis réessayez.");
  }
  const corps = (await r.json().catch(() => ({}))) as { erreur?: string; jeton?: string; expire_dans?: number; identifiant?: string };
  if (!r.ok || !corps.jeton || !corps.identifiant) {
    throw new Error(corps.erreur ?? `Le service des comptes a répondu par une erreur ${r.status}.`);
  }
  // Une minute de marge : on redemande la connexion un peu avant l'expiration réelle du jeton.
  const session = { identifiant: corps.identifiant, jeton: corps.jeton, expire: Date.now() + ((corps.expire_dans ?? 3600) - 60) * 1000 };
  try { window.localStorage.setItem(CLE, JSON.stringify(session)); } catch { /* la session vaut pour cet onglet */ }
  return session;
}
