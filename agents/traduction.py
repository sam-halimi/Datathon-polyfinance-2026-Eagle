"""Traduction anglaise de ce que le pipeline renvoie (option « English » du site).

Le pipeline travaille et écrit en français. Quand le site demande l'anglais, ce module traduit
les textes de la sortie, et rien d'autre : codes, symboles, identifiants, dates et valeurs
restent tels quels.

Règle du projet : aucun chiffre ne sort d'un modèle. Elle tient ici par construction. Avant
l'appel, chaque nombre, chaque marqueur de chiffre (`{vol_tsla}`), chaque nom de fichier, adresse
ou identifiant est remplacé par un jeton (`⟦0⟧`, `⟦1⟧`…). Le modèle ne traduit que les mots autour.
Au retour, on vérifie que chaque jeton est présent exactement autant de fois qu'à l'aller, puis on
remet les valeurs d'origine. Une traduction qui perd, ajoute ou répète un jeton est refusée et le
texte reste en français : un trou se signale (`meta.traduction`), il ne se comble pas en silence.

Les traductions déjà faites sont gardées dans `agents/traductions/en.json`, sous leur forme à
jetons : « Les poids totalisent ⟦0⟧ % du capital fictif. » sert pour toutes les valeurs. Les
textes écrits par les outils (contrôles, limites, formules) n'appellent donc le modèle qu'une fois.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

MEMOIRE = Path(__file__).resolve().parent / "traductions" / "en.json"
LANGUES = ("fr", "en")

# Ce que le modèle ne voit pas : marqueurs et objets entre accolades, adresses, fichiers, dates,
# identifiants à tiret bas, symboles boursiers à suffixe (XIU.TO), nombres (avec ordinal éventuel).
_PROTEGE = re.compile(
    r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    r"|https?://[^\s)»]+"
    r"|[\w./-]+\.(?:csv|py|json|txt|md|ts|tsx)\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b[A-Za-z]+(?:_[A-Za-z0-9]+)+\b"
    r"|\b[A-Z]{1,5}\.(?:TO|V|NE)\b"
    r"|\d+(?:[   ]\d{3})*(?:[.,]\d+)?(?:er|re|e)?(?![\w])"
    r"|\d+(?:[.,]\d+)?"
)
_JETON = re.compile(r"⟦(\d+)⟧")
_ORDINAL = re.compile(r"^(\d+)(er|re|e)$")

# Champs traduits sur place. `*` : toute clé ; `[]` : chaque élément d'une liste.
CHEMINS = (
    "note",
    "demande_analysee.resume",
    "etapes[].fait",
    "portefeuilles[].nom", "portefeuilles[].intention",
    "portefeuilles[].lignes[].role", "portefeuilles[].lignes[].pourquoi",
    "portefeuilles[].lignes[].plutot_que.raison", "portefeuilles[].lignes[].sources[].objet",
    "portefeuilles[].controles[].titre", "portefeuilles[].controles[].detail",
    "portefeuilles[].controles[].reference.formule",
    "portefeuilles[].adequation[].attente", "portefeuilles[].adequation[].reponse",
    "portefeuilles[].adequation[].regle", "portefeuilles[].adequation[].raison",
    "adequation[].attente", "adequation[].reponse", "adequation[].regle", "adequation[].raison",
    "gouvernance.controles[].titre", "gouvernance.controles[].detail",
    "gouvernance.controles[].reference.formule", "gouvernance.historique[].nom",
    "explication.sujet", "explication.niveau1", "explication.niveau2[]",
    "explication.niveau3.formule", "explication.niveau3.lignes[]",
    "explication.registre.nom", "explication.registre.description",
    "explication.lexique[].terme", "explication.lexique[].definition",
    "limites.faits[]", "limites.hypotheses[]", "limites.limites[]", "limites.methode[]",
    "limites.limites_specifiques[].texte", "limites.hypotheses_specifiques[].texte",
    "limites.hypotheses_specifiques[].si_elle_tombe",
    "messages.*",
    "specialistes.*[]",
    "contraintes.origine.*", "contraintes.nature",
    "chiffres.*.details.avertissement", "chiffres.*.details.nature",
    "chiffres.*.details.hypothese", "chiffres.*.details.methode",
    "chiffres.*.details.serie_taux.libelle",
    "scenarios.details.avertissement", "scenarios.details.hypotheses[]",
    "scenarios_par_portefeuille.*.details.avertissement",
    "scenarios_par_portefeuille.*.details.hypotheses[]",
    # GET /actif (tools.scenarios.fiche_actif)
    "titre", "raisons[]", "notes[]",
)

# Champs que le site lit aussi comme des codes (format du nombre, choix de la formule) : le
# français reste en place, l'anglais va dans une clé voisine `<champ>_en`.
CHEMINS_A_COTE = (
    "chiffres.*.unite", "chiffres.*.formule",
    "scenarios.unite", "scenarios.formule",
    "scenarios_par_portefeuille.*.unite", "scenarios_par_portefeuille.*.formule",
)

CONSIGNE = (
    "You translate short French texts into clear Canadian English for Eagle, an assistant that builds "
    "SIMULATED investment portfolios and explains them. You receive a JSON array of strings and return "
    "ONLY a JSON array of the same length, in the same order, with each string translated.\n"
    "Rules:\n"
    "- Tokens such as ⟦0⟧ or ⟦12⟧ stand for numbers, dates, file names or identifiers. Copy every token "
    "exactly once, never change, drop, repeat or invent one, and never write a number yourself.\n"
    "- Translate faithfully: add nothing, remove nothing, do not soften or strengthen a statement.\n"
    "- Keep ticker symbols, company and fund names, and source names as they are.\n"
    "- Vocabulary: « portefeuille simulé » = simulated portfolio; « FNB » = ETF; « pire baisse » = worst "
    "drawdown; « volatilité » = volatility; « gain de rattrapage » = recovery gain; « part du risque » = "
    "share of risk; « gouvernance » = governance; « fenêtre » (of data) = window; « ligne » (of a "
    "portfolio) = holding; « plafond » = cap; « capital fictif » = notional capital; « titre » (a "
    "security) = security or stock.\n"
    "- Eagle is an assistant and the portfolio is a simulation: never write advice, advisor, adviser or "
    "recommend. Never turn a description of the past into a forecast.\n"
    "- « vous » is you. French quotation marks « … » become “…”. Keep the register of the source "
    "(plain words stay plain, professional terms stay professional).\n"
    "- A string made only of tokens or names is returned unchanged."
)

Modele = Callable[[list[str]], list[str]]

_verrou = threading.Lock()
_memoire: dict[str, str] | None = None


def memoire() -> dict[str, str]:
    """Traductions connues : forme à jetons en français -> forme à jetons en anglais."""
    global _memoire
    with _verrou:
        if _memoire is None:
            _memoire = json.loads(MEMOIRE.read_text(encoding="utf-8")) if MEMOIRE.exists() else {}
        return _memoire


def enregistrer_memoire() -> None:
    """Écrit la mémoire sur disque (poste de travail seulement : la Lambda est en lecture seule)."""
    MEMOIRE.parent.mkdir(parents=True, exist_ok=True)
    MEMOIRE.write_text(json.dumps(dict(sorted(memoire().items())), ensure_ascii=False, indent=0) + "\n",
                       encoding="utf-8")


def masquer(texte: str) -> tuple[str, list[str]]:
    """Remplace chaque valeur protégée par un jeton. Renvoie la forme à jetons et les valeurs."""
    valeurs: list[str] = []

    def jeton(m: re.Match[str]) -> str:
        valeurs.append(m.group(0))
        return f"⟦{len(valeurs) - 1}⟧"

    return _PROTEGE.sub(jeton, texte.replace("⟦", "[").replace("⟧", "]")), valeurs


def _ordinal_anglais(valeur: str) -> str:
    m = _ORDINAL.match(valeur)
    if not m:
        return valeur
    n = int(m.group(1))
    suffixe = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffixe}"


def jetons_respectes(source: str, cible: str) -> bool:
    """Chaque jeton de la source est dans la cible le même nombre de fois, et aucun autre."""
    return sorted(_JETON.findall(source)) == sorted(_JETON.findall(cible))


def demasquer(masque: str, valeurs: list[str]) -> str:
    """Remet les valeurs d'origine à la place des jetons (« 1er » devient « 1st », rien d'autre ne change)."""
    return _JETON.sub(lambda m: _ordinal_anglais(valeurs[int(m.group(1))]), masque)


def _a_traduire(texte: str) -> bool:
    """Un texte sans lettre hors des jetons (un nombre, un symbole seul) n'a rien à traduire."""
    return bool(re.search(r"[A-Za-zÀ-ÿ]{2}", _JETON.sub("", texte)))


def modele_bedrock(textes: list[str]) -> list[str]:
    """Un appel au modèle pour un lot de textes à jetons. Passe par agents.modele (reprises, secours)."""
    from agents.modele import creer_agent

    agent = creer_agent("Traduction", CONSIGNE)
    reponse = str(agent(json.dumps(textes, ensure_ascii=False)))
    debut, fin = reponse.find("["), reponse.rfind("]")
    if debut < 0 or fin < debut:
        raise ValueError("réponse du modèle sans tableau JSON")
    resultat = json.loads(reponse[debut:fin + 1])
    if not isinstance(resultat, list) or len(resultat) != len(textes) or not all(isinstance(x, str) for x in resultat):
        raise ValueError("réponse du modèle : tableau de la mauvaise longueur")
    return resultat


def _lots(textes: list[str], taille: int = 2600) -> list[list[str]]:
    lots: list[list[str]] = [[]]
    for t in textes:
        if lots[-1] and sum(len(x) for x in lots[-1]) + len(t) > taille:
            lots.append([])
        lots[-1].append(t)
    return [lot for lot in lots if lot]


def _traduire_lot(lot: list[str], modele: Modele) -> dict[str, str]:
    """Traduit un lot ; s'il échoue en bloc, le coupe en deux une fois. Ne garde que les traductions valides."""
    try:
        cibles = modele(lot)
    except Exception:  # noqa: BLE001 - une panne de traduction ne doit jamais faire échouer l'analyse
        if len(lot) == 1:
            return {}
        milieu = len(lot) // 2
        return {**_traduire_lot(lot[:milieu], modele), **_traduire_lot(lot[milieu:], modele)}
    return {s: c.strip() for s, c in zip(lot, cibles) if c.strip() and jetons_respectes(s, c)}


def traduire_textes(textes: Iterable[str], modele: Modele | None = None, fils: int = 8) -> dict[str, str]:
    """Français -> anglais pour chaque texte donné. Un texte non traduit est absent du résultat."""
    connu = memoire()
    formes: dict[str, tuple[str, list[str]]] = {}
    for t in dict.fromkeys(textes):
        if isinstance(t, str) and t.strip():
            formes[t] = masquer(t)
    manquants = list(dict.fromkeys(m for m, _ in formes.values() if m not in connu and _a_traduire(m)))
    if manquants:
        lots = _lots(manquants)
        with ThreadPoolExecutor(max_workers=min(fils, len(lots))) as bassin:
            for trouve in bassin.map(lambda lot: _traduire_lot(lot, modele or modele_bedrock), lots):
                with _verrou:
                    connu.update(trouve)
    resultat: dict[str, str] = {}
    for t, (masque, valeurs) in formes.items():
        if not _a_traduire(masque):
            resultat[t] = t
        elif masque in connu:
            resultat[t] = demasquer(connu[masque], valeurs)
    return resultat


def _visiter(noeud: Any, chemin: list[str], action: Callable[[Any, Any], None]) -> None:
    """Applique `action(conteneur, clé)` à chaque chaîne désignée par le chemin."""
    if not chemin:
        return
    tete, reste = chemin[0], chemin[1:]
    liste = tete.endswith("[]")
    cle = tete[:-2] if liste else tete
    if not isinstance(noeud, dict):
        return
    for k in (list(noeud) if cle == "*" else [cle] if cle in noeud else []):
        valeur = noeud[k]
        if liste:
            if not isinstance(valeur, list):
                continue
            for i, element in enumerate(valeur):
                if reste:
                    _visiter(element, reste, action)
                elif isinstance(element, str):
                    action(valeur, i)
        elif reste:
            _visiter(valeur, reste, action)
        elif isinstance(valeur, str):
            action(noeud, k)


def _formule(texte: str, table: dict[str, str]) -> str | None:
    """Une formule à plusieurs parties (« a ; b ; c ») est traduite partie par partie : le site en choisit une."""
    parties = texte.split(" ; ")
    return " ; ".join(table[p] for p in parties) if all(p in table for p in parties) else None


def traduire_sortie(sortie: dict[str, Any], langue: str = "en", modele: Modele | None = None) -> dict[str, Any]:
    """Copie de la sortie avec ses textes en anglais. `langue="fr"` : la sortie telle quelle.

    Ajoute `langue` et `meta.traduction` (nombre de textes, combien sont restés en français).
    Une panne du modèle laisse le français : l'analyse n'échoue jamais à cause de la traduction."""
    if langue != "en":
        return sortie
    copie = copy.deepcopy(sortie)
    places: list[tuple[Any, Any, str | None]] = []  # conteneur, clé, clé voisine éventuelle
    for chemin in CHEMINS:
        _visiter(copie, chemin.split("."), lambda c, k: places.append((c, k, None)))
    for chemin in CHEMINS_A_COTE:
        _visiter(copie, chemin.split("."), lambda c, k: places.append((c, k, f"{k}_en")))

    textes: list[str] = []
    for conteneur, cle, voisine in places:
        textes.extend(conteneur[cle].split(" ; ") if voisine and cle == "formule" else [conteneur[cle]])
    table = traduire_textes(textes, modele)

    total = restes = 0
    for conteneur, cle, voisine in places:
        source = conteneur[cle]
        if not source.strip():
            continue
        total += 1
        cible = _formule(source, table) if voisine and cle == "formule" else table.get(source)
        if cible is None:
            restes += 1
        elif voisine:
            conteneur[voisine] = cible
        else:
            conteneur[cle] = cible
    copie["langue"] = "en"
    if isinstance(copie.get("meta"), dict):
        copie["meta"]["traduction"] = {"langue": "en", "textes": total, "restes_en_francais": restes}
    return copie


def langue_demandee(valeur: Any) -> str:
    """« en » si l'anglais est demandé, « fr » dans tous les autres cas."""
    return "en" if str(valeur or "").strip().lower().startswith("en") else "fr"


def main() -> int:
    """`python -m agents.traduction` : versions anglaises des trois démonstrations et mémoire à jour.

    Lit agents/sorties/<persona>.json, écrit agents/sorties/en/<persona>.json. `--tout` traduit
    aussi les autres sorties enregistrées, sans les écrire : leurs textes rejoignent la mémoire."""
    import sys

    sorties = Path(__file__).resolve().parent / "sorties"
    (sorties / "en").mkdir(exist_ok=True)
    noms = sorted(f.stem for f in sorties.glob("*.json")) if "--tout" in sys.argv else ["amira", "mateo", "robert"]
    for nom in noms:
        source = json.loads((sorties / f"{nom}.json").read_text(encoding="utf-8"))
        traduite = traduire_sortie(source, "en")
        bilan = traduite["meta"]["traduction"]
        if nom in ("amira", "mateo", "robert"):
            (sorties / "en" / f"{nom}.json").write_text(
                json.dumps(traduite, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{nom} : {bilan['textes']} textes, {bilan['restes_en_francais']} resté(s) en français")
        enregistrer_memoire()
    print(f"mémoire : {len(memoire())} traductions ({MEMOIRE.relative_to(Path.cwd()) if MEMOIRE.is_relative_to(Path.cwd()) else MEMOIRE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
