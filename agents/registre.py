"""Registre des chiffres : le mécanisme qui garantit « aucun chiffre ne sort d'un modèle ».

Chaque appel à une fonction de `tools/` passe par le registre. Le résultat (valeur brute et
référence d'appel : outil, paramètres, période, formule, sources) y reçoit un identifiant court,
par exemple `volatilite_tsla`. Les agents ne voient que des identifiants et des valeurs déjà
formatées ; dans leurs textes, ils citent un chiffre par son repère `{volatilite_tsla}`.

`verifier_texte` refuse tout texte d'agent qui contient un chiffre écrit en dur ou un repère
inconnu. L'interface remplace chaque repère par la valeur et ouvre sa référence au toucher.

Le registre garde aussi la trace ordonnée des appels (qui a appelé quoi), affichée dans la sortie.
"""

from __future__ import annotations

import re
from typing import Any

REPERE = re.compile(r"\{([a-z0-9_]+)\}")
FORMATS = ("pourcent", "decimal", "points", "entier", "montant")

# Nombres qui font partie d'un nom propre ou d'un nom de série, pas d'une mesure.
NOMS_AVEC_CHIFFRES = [
    r"S&P\s?500", r"Nasdaq[- ]?100", r"S&P/TSX\s?60", r"TSX\s?60", r"Russell\s?\d+",
    r"\b(?:taux|obligations?|rendement)\s+(?:à\s+)?(?:10|2)\s+ans\b", r"\b(?:10|2)\s+ans\s+(?:américain|canadien)s?\b",
    r"\b10-2\b", r"\bDGS\d+\b", r"\bBD\.CDN\.\d+YR[\w.]*", r"\bCO2\b", r"\bN-PORT\b",
]
_NOMS = re.compile("|".join(NOMS_AVEC_CHIFFRES), re.IGNORECASE)


def identifiant(*morceaux: str) -> str:
    """« volatilite », « XIU.TO » -> « volatilite_xiu_to »."""
    texte = "_".join(str(m) for m in morceaux if m not in (None, ""))
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", texte.lower())).strip("_")


def format_par_defaut(unite: str) -> str:
    u = unite.lower()
    if u.startswith("coefficient") or "r²" in u:
        return "decimal"
    if u.startswith("points"):
        return "points"
    if u.startswith("fraction"):
        return "pourcent"
    if u.startswith("jours") or u.startswith("nombre"):
        return "entier"
    if u.startswith("cad") or u.startswith("usd") or "montant" in u:
        return "montant"
    return "decimal"


def afficher(valeur: Any, fmt: str) -> str:
    """Valeur formatée à la française, pour que les agents écrivent des phrases justes."""
    if not isinstance(valeur, (int, float)):
        return str(valeur)
    if fmt == "pourcent":
        texte = f"{valeur * 100:.1f} %"
    elif fmt == "points":
        texte = f"{valeur:+.2f} point"
    elif fmt == "entier":
        texte = f"{valeur:,.0f}".replace(",", " ")
    elif fmt == "montant":
        texte = f"{valeur:,.0f} $".replace(",", " ")
    else:
        texte = f"{valeur:.2f}"
    return texte.replace(".", ",").replace("-", "−")


def _scalaires(d: dict[str, Any]) -> dict[str, Any]:
    """Détails gardés dans la sortie : les valeurs simples, pas les matrices."""
    return {k: v for k, v in (d or {}).items() if isinstance(v, (str, int, float, bool)) or v is None}


class Registre:
    def __init__(self) -> None:
        self.chiffres: dict[str, dict[str, Any]] = {}
        self.appels: list[dict[str, Any]] = []

    # ----- inscription -----
    def inscrire(self, res: dict[str, Any], ident: str, decrit: str, *, valeur: Any = None,
                 cle: str | None = None, fmt: str | None = None, par: str = "pipeline",
                 unite: str | None = None) -> str:
        """Inscrit un résultat de tools/ (ou une de ses composantes) sous `ident`.

        `valeur` remplace `res["valeur"]` quand on inscrit une composante (par exemple la part
        du risque d'un actif dans le résultat de `parts_du_risque`) ; `cle` dit laquelle.
        """
        v = res["valeur"] if valeur is None else valeur
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise TypeError(f"{ident} : seule une valeur numérique s'inscrit (reçu {type(v).__name__}).")
        u = unite or res["unite"]
        f = fmt or format_par_defaut(u)
        if f not in FORMATS:
            raise ValueError(f"format inconnu : {f}")
        details = _scalaires(res.get("details", {}))
        details["decrit"] = decrit
        if cle:
            details["cle"] = cle
        self.chiffres[ident] = {
            "outil": res["outil"], "parametres": res["parametres"], "periode": res.get("periode") or {},
            "valeur": float(v), "unite": u, "format": f, "formule": res["formule"],
            "sources": list(res.get("sources", [])), "details": details,
        }
        self.appels.append({"ordre": len(self.appels) + 1, "par": par, "outil": res["outil"],
                            "parametres": res["parametres"], "chiffre": ident})
        return ident

    def entree(self, ident: str, valeur: float, decrit: str, origine: str, fmt: str,
               unite: str, par: str = "accueil") -> str:
        """Chiffre qui ne vient pas d'un calcul : donné par l'utilisateur (profil, demande)
        ou fixé par l'équipe (limites de `contraintes`). Sa nature est écrite dans la référence."""
        res = {"outil": origine, "parametres": {}, "periode": {}, "valeur": valeur, "unite": unite,
               "formule": "valeur donnée, pas calculée", "sources": [origine], "details": {}}
        return self.inscrire(res, ident, decrit, fmt=fmt, par=par)

    # ----- lecture -----
    def affiche(self, ident: str) -> str:
        c = self.chiffres[ident]
        return afficher(c["valeur"], c["format"])

    def ligne(self, ident: str) -> str:
        """« {volatilite_tsla} = 59,6 % : Volatilité de TSLA » : ce que voient les agents."""
        return f"{{{ident}}} = {self.affiche(ident)} : {self.chiffres[ident]['details']['decrit']}"

    def catalogue(self, idents: list[str] | None = None) -> str:
        return "\n".join(self.ligne(i) for i in (idents if idents is not None else self.chiffres))

    def valeur(self, ident: str) -> float:
        return self.chiffres[ident]["valeur"]

    # ----- contrôle des textes -----
    def verifier_texte(self, texte: str, noms_permis: list[str] | None = None) -> list[str]:
        """Problèmes d'un texte d'agent : repère inconnu, ou chiffre écrit en dur."""
        problemes = [f"repère inconnu {{{m}}}" for m in REPERE.findall(texte) if m not in self.chiffres]
        reste = REPERE.sub(" ", texte)
        reste = _NOMS.sub(" ", reste)
        for nom in noms_permis or []:
            reste = reste.replace(nom, " ")
        en_dur = re.findall(r"\d[\d\s,.]*\s?%?", reste)
        if en_dur:
            problemes.append("chiffre écrit en dur : " + ", ".join(sorted({e.strip() for e in en_dur})))
        return problemes

    def cites(self, textes: list[str]) -> set[str]:
        return {m for t in textes for m in REPERE.findall(t)}
