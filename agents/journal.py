"""Journal des chiffres : chaque chiffre affiché garde la référence de l'appel qui l'a produit.

Le pipeline n'écrit jamais un chiffre en clair dans un texte de modèle. Il écrit une clé entre
accolades, `{baisse_tsla}`, et `chiffres["baisse_tsla"]` donne la valeur brute, l'outil, ses
paramètres, la période, la formule et les sources. L'interface (`web/lib/format.ts`) et
`rendre()` ci-dessous remplacent la clé par la valeur arrondie pour l'affichage.

`problemes_texte()` refuse un texte de modèle qui contient un chiffre hors d'une clé : c'est le
garde-fou de la règle « aucun chiffre ne sort d'un modèle ».
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

# Nature d'un chiffre, pour distinguer faits, hypothèses et décisions dans l'explication.
FAIT = "fait mesuré"
HYPOTHESE = "hypothèse de conception"
DECISION = "décision du constructeur"
DEMANDE = "demande de l'utilisateur"

MOTIF_CLE = re.compile(r"\{([a-z0-9_]+)\}")
MOTIF_CHIFFRE = re.compile(r"\d")
# Un rapport calculé par le modèle et écrit en lettres (« huit fois plus », « la moitié ») est un chiffre.
MOTIF_RAPPORT = re.compile(r"\b(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|quinze|vingt|trente|"
                           r"quarante|cinquante|cent|mille)\s+fois\b|\b(moitié|double|triple|quadruple|tiers|quart)\b",
                           re.IGNORECASE)


def cle_propre(*morceaux: Any) -> str:
    """« vol », « BTC-USD » -> « vol_btc_usd »."""
    texte = "_".join(str(m) for m in morceaux if m not in (None, ""))
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", texte).strip("_")


def _extraire(valeur: Any, chemin: tuple[str, ...]) -> Any:
    for morceau in chemin:
        valeur = valeur[morceau]
    return valeur


def formater(ref: dict[str, Any]) -> str:
    """Même arrondi que web/lib/format.ts : % à une décimale, coefficient à deux décimales."""
    v = float(ref["valeur"])
    if ref["unite"].startswith("fraction"):
        texte = f"{v * 100:.1f} %"
    else:
        texte = f"{v:.2f}"
    return texte.replace(".", ",").replace("-", "−")


class Journal:
    """Registre des appels à tools/ et des chiffres qu'ils ont produits."""

    def __init__(self) -> None:
        self.chiffres: dict[str, dict[str, Any]] = {}
        self.appels: list[dict[str, Any]] = []

    # --- appels -----------------------------------------------------------------------------
    def appeler(self, fonction: Callable[..., dict[str, Any]], agent: str, **parametres: Any) -> dict[str, Any]:
        """Lance une fonction de tools/ et garde la trace de l'appel."""
        resultat = fonction(**parametres)
        self.appels.append({"agent": agent, "outil": resultat.get("outil", fonction.__name__),
                            "parametres": resultat.get("parametres", parametres)})
        return resultat

    # --- chiffres ---------------------------------------------------------------------------
    def enregistrer(self, cle: str, res: dict[str, Any], decrit: str, chemin: tuple[str, ...] = ("valeur",),
                    nature: str = FAIT, unite: str | None = None) -> str:
        """Garde un chiffre scalaire tiré d'un résultat de tools/. Renvoie la clé (suffixée si elle
        est déjà prise par un autre calcul)."""
        valeur = _extraire(res, chemin)
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            raise TypeError(f"{cle} : {chemin} ne désigne pas un nombre")
        ref = {
            "outil": res["outil"],
            "parametres": res.get("parametres", {}),
            "periode": res.get("periode") or {"debut": None, "fin": None, "observations": None},
            "valeur": float(valeur),
            "unite": unite or res.get("unite", ""),
            "formule": res.get("formule", ""),
            "sources": list(res.get("sources", [])),
            "details": {"decrit": decrit, "nature": nature, "chemin": list(chemin)},
        }
        origine = (res.get("details") or {}).get("origine")
        if origine:  # chiffre calculé à partir d'un autre (gain de rattrapage d'une pire baisse)
            ref["details"]["origine"] = origine
        base, n = cle_propre(cle), 1
        cle = base
        while cle in self.chiffres:
            ancien = self.chiffres[cle]
            if (ancien["outil"], ancien["parametres"], ancien["details"]["chemin"]) == (
                    ref["outil"], ref["parametres"], ref["details"]["chemin"]):
                return cle
            n += 1
            cle = f"{base}_{n}"
        self.chiffres[cle] = ref
        return cle

    def valeur_hors_outil(self, cle: str, valeur: float, unite: str, decrit: str, nature: str,
                          origine: str, parametres: dict[str, Any] | None = None, sources: list[str] | None = None) -> str:
        """Chiffre qui ne vient pas d'un calcul sur les données : limite du profil, poids décidé,
        poids demandé. Sa nature et son origine sont affichées avec lui."""
        res = {"outil": origine, "parametres": parametres or {}, "valeur": valeur, "unite": unite,
               "formule": "", "sources": sources or [origine]}
        return self.enregistrer(cle, res, decrit, nature=nature)

    def apercu(self, cles: list[str] | None = None) -> list[dict[str, str]]:
        """Ce que voit un agent : la clé, ce qu'elle décrit et la valeur arrondie."""
        cles = list(self.chiffres) if cles is None else cles
        return [{"cle": c, "decrit": self.chiffres[c]["details"]["decrit"],
                 "valeur_affichee": formater(self.chiffres[c]),
                 "nature": self.chiffres[c]["details"]["nature"]} for c in cles]

    # --- textes -----------------------------------------------------------------------------
    def problemes_texte(self, texte: str) -> list[str]:
        """Chiffres écrits en clair et clés inconnues dans un texte de modèle."""
        problemes = [f"clé inconnue {{{c}}}" for c in MOTIF_CLE.findall(texte) if c not in self.chiffres]
        sans_cles = MOTIF_CLE.sub("", texte)
        nus = [c for c in self.chiffres if re.search(rf"(?<![\w{{]){re.escape(c)}(?![\w}}])", sans_cles)]
        if nus:
            problemes.append("nom de clé écrit hors accolades : " + ", ".join(nus[:5]))
        rapports = [m.group(0) for m in MOTIF_RAPPORT.finditer(sans_cles)]
        if rapports:
            problemes.append("rapport calculé écrit en lettres : " + ", ".join(rapports[:5]))
        if MOTIF_CHIFFRE.search(sans_cles):
            fragments = re.findall(r"[^\s]*\d[^\s]*", sans_cles)
            problemes.append("chiffre écrit en clair : " + ", ".join(fragments[:5]))
        return problemes

    def rendre(self, texte: str) -> str:
        """Remplace chaque clé par sa valeur arrondie (lecture humaine, tests)."""
        return MOTIF_CLE.sub(lambda m: formater(self.chiffres[m.group(1)]) if m.group(1) in self.chiffres
                             else m.group(0), texte)
