"""Pipeline AlphaForge AI : profil validé + demande -> un JSON unique (docs/sortie-pipeline.md).

    python -m agents.pipeline tests/scenarios/robert.json -o agents/sorties/robert.json

Ordre : orchestrateur -> spécialiste marché et risque -> constructeur -> gouvernance (rejet = retour
au constructeur, deux retours au plus) -> explication. Le pipeline ne se modifie pas tout seul.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agents import etapes
from agents.gouvernance import (_carte, controle_demande, enregistrer_limites, enregistrer_poids,
                                verifier_portefeuille)
from agents.journal import Journal
from agents.outils_agents import devise_calcul, mesurer, outils_constructeur, outils_marche
from agents.profil import Profil, contraintes
from tools.bedrock import modele_bedrock
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE
from tools.portefeuille import parts_du_risque, stats_portefeuille

RETOURS_MAX = 2  # « Rejet = retour au constructeur, 2 essais au plus »
ESSAIS_MAX = 1 + RETOURS_MAX
CLASSES_THEME = ("equity", "etf_equity")
MOTS_INTERDITS = ("conseil", "recommand", "réglementaire")
LIBELLES_CLASSE = {"equity": "Action", "etf_equity": "FNB d'actions", "etf_bond": "FNB d'obligations",
                   "etf_commodity": "FNB d'or", "crypto": "Cryptoactif"}

HYPOTHESES_FIXES = [
    "Calculs dans la devise du profil : un actif coté en USD est converti avec le taux de la Banque du Canada "
    "(fx_usdcad_daily.csv), dernier taux reporté les jours fériés.",
    "Poids constants : un portefeuille simulé est supposé rééquilibré chaque jour, sans frais ni impôt.",
    "Les limites du profil et les seuils de risque sont des hypothèses de conception de l'équipe, pas une norme.",
    "Les poids sont la décision du constructeur ; la gouvernance les vérifie par le code.",
]
LIMITES_FIXES = [
    "Le passé décrit le risque observé sur la fenêtre. Il ne promet rien pour l'avenir.",
    "Univers de départ choisi en 2026 : les actifs qui ont disparu entre-temps n'y sont pas (biais du survivant).",
    "La gouvernance ne voit pas encore à travers les FNB : un titre ou un secteur détenu par SPY, QQQ, XIU.TO "
    "ou ESGV n'est pas compté dans les plafonds.",
]


def _trace(message: str) -> None:
    print(f"[pipeline] {message}", file=sys.stderr, flush=True)


def _problemes(journal: Journal, texte: str) -> list[str]:
    problemes = journal.problemes_texte(texte)
    problemes += [f"mot interdit « {m} »" for m in MOTS_INTERDITS if m in texte.lower()]
    return problemes


def _valider_orchestration(orch: etapes.Orchestration, profil: Profil, demande: str) -> tuple[list[dict], dict | None, list[str]]:
    """Symboles dans l'univers, thème sur actions et FNB, part demandée lisible dans la demande."""
    table = univers()
    notes = []
    cibles = []
    for cible in orch.cibles:
        symboles = [s for s in cible.symboles if s in table.index]
        if len(symboles) < len(cible.symboles):
            notes.append(f"Symboles hors univers ignorés : {sorted(set(cible.symboles) - set(symboles))}.")
        poids = cible.poids_demande
        if poids is not None:
            texte = demande.lower().replace(" ", "")
            lisible = f"{round(poids * 100)}%" in texte or (abs(poids - 1) < 1e-9 and "tout" in demande.lower())
            if not (0 < poids <= 1) or not lisible:
                notes.append("Part demandée écartée : elle ne se lit pas dans la demande.")
                poids = None
        cibles.append({"symboles": symboles, "poids_demande": poids, "extrait": cible.extrait})
    theme = None
    if orch.theme and profil.centres_interet:
        symboles = [s for s in orch.theme.symboles if s in table.index and table.at[s, "asset_class"] in CLASSES_THEME]
        if symboles:
            theme = {"nom": orch.theme.nom, "symboles": symboles, "justification": orch.theme.justification,
                     "source": "data/assets_universe.csv"}
    return cibles, theme, notes


def _lignes_valides(journal: Journal, p: etapes.PortefeuillePropose, table) -> dict[str, Any]:
    """Libellés sans chiffre (sinon libellé par défaut), poids agrégés par symbole."""
    poids: dict[str, float] = {}
    lignes = []
    for ligne in p.lignes:
        s = ligne.symbole.strip()
        poids[s] = poids.get(s, 0.0) + float(ligne.poids)
        classe = table.at[s, "asset_class"] if s in table.index else "inconnue"
        role = ligne.role if not _problemes(journal, ligne.role) else LIBELLES_CLASSE.get(classe, "Ligne")
        lignes.append({"symbole": s, "role": role, "theme": ligne.au_titre_du_theme})
    nom = p.nom if not _problemes(journal, p.nom) else f"Portefeuille {p.id}"
    intention = p.intention if not _problemes(journal, p.intention) else ""
    return {"id": p.id, "nom": nom, "intention": intention, "lignes": lignes, "poids": poids}


def _texte_explication(e: etapes.Explication) -> list[tuple[str, str]]:
    champs = [("sujet", e.sujet), ("niveau1", e.niveau1)]
    champs += [(f"niveau2[{i}]", t) for i, t in enumerate(e.niveau2)]
    champs += [(f"niveau3.lignes[{i}]", t) for i, t in enumerate(e.niveau3.lignes)]
    for nom in ("faits", "hypotheses", "limites"):
        champs += [(f"{nom}[{i}]", t) for i, t in enumerate(getattr(e, nom))]
    champs += [(f"messages.{k}", v) for k, v in e.messages.model_dump().items()]
    return champs


def lancer(profil_brut: dict[str, Any], demande: str, prenom: str | None = None,
           trace: Callable[[str], None] = _trace) -> dict[str, Any]:
    profil = Profil(**profil_brut)
    c = contraintes(profil)
    p = profil.model_dump()
    journal = Journal()
    table = univers()
    devise = devise_calcul(p)
    cles_limites = enregistrer_limites(journal, profil, c)
    seuils_risque = {k: SEUILS_PAR_TOLERANCE[profil.tolerance_risque][k] for k in ("volatilite", "pire_baisse")}
    suivi: list[dict[str, str]] = []

    # 1. Orchestrateur
    trace("orchestrateur")
    orch = etapes.orchestrer(p, c, demande, outils_marche(journal, p, "Orchestrateur")[:1])
    cibles, theme, notes_orch = _valider_orchestration(orch, profil, demande)
    suivi.append({"agent": "Orchestrateur", "fait": (
        f"Lit le profil et fixe les limites ({len(c['limites'])} limites). "
        + (f"Thème « {theme['nom']} » plafonné, {len(theme['symboles'])} actifs de la table sourcée. " if theme
           else "Pas de thème. ")
        + f"{sum(1 for x in cibles if x['poids_demande'] is not None)} demande(s) chiffrée(s) relevée(s).")})
    cartes_demande = controle_demande(journal, profil, c, cibles, cles_limites)

    # 2. Spécialiste marché et risque
    trace("spécialiste marché et risque")
    avant = len(journal.chiffres)
    notes = etapes.analyser_marche(p, c, orch, outils_marche(journal, p))
    constats = [k.model_dump() for k in notes.constats if not _problemes(journal, k.texte)]
    ecartes = len(notes.constats) - len(constats)
    suivi.append({"agent": "Marché et risque", "fait": (
        f"Mesure volatilité, pire baisse et corrélations : {len(journal.chiffres) - avant} chiffres calculés par tools/."
        + (f" {ecartes} constat(s) écarté(s) : chiffre écrit sans référence." if ecartes else ""))})

    # 3. Constructeur et 4. gouvernance, deux retours au plus
    symboles_theme_autorises = set(theme["symboles"]) if theme else set()
    historique = []
    propositions, rejets, verifies = None, None, {}
    for essai in range(1, ESSAIS_MAX + 1):
        trace(f"constructeur, essai {essai}")
        propositions = etapes.construire(p, c, seuils_risque, orch, notes, outils_constructeur(journal, p),
                                         rejets=rejets, precedentes=propositions)
        verifies = {}
        for prop in propositions.portefeuilles[:3]:
            v = _lignes_valides(journal, prop, table)
            symboles_theme = [l["symbole"] for l in v["lignes"] if l["theme"]]
            controle = verifier_portefeuille(journal, profil, c, v["poids"], symboles_theme,
                                             theme["nom"] if theme else None)
            hors_theme = [s for s in symboles_theme if s not in symboles_theme_autorises]
            if hors_theme:
                controle["controles"].append(_carte(
                    "theme_source", "non conforme",
                    f"Lignes marquées « thème » hors du thème de l'orchestrateur : {hors_theme}.",
                    source="agents/pipeline.py"))
                controle["accepte"] = False
                controle["rejets"].append(controle["controles"][-1])
            verifies[v["id"]] = {**v, **controle}
        rejets = {i: [f"{k['titre']} : {k['detail']}" for k in v["rejets"]] for i, v in verifies.items() if not v["accepte"]}
        historique.append({"essai": essai, "rejets": rejets})
        trace(f"gouvernance : {len(verifies) - len(rejets)} accepté(s), {len(rejets)} rejeté(s)")
        if not rejets:
            break
    retenus = [v for v in verifies.values() if v["accepte"]]
    suivi.append({"agent": "Constructeur", "fait": (
        f"Propose {len(verifies)} portefeuilles simulés en {len(historique)} essai(s).")})
    suivi.append({"agent": "Gouvernance", "fait": (
        f"Vérifie chaque portefeuille contre le profil : {len(retenus)} accepté(s)"
        + (f", {len(verifies) - len(retenus)} écarté(s) après {RETOURS_MAX} retours." if len(retenus) < len(verifies)
           else ".") + (f" Rejets en cours de route : {sum(len(h['rejets']) for h in historique)}."
                        if len(historique) > 1 else ""))})

    # Chiffres des portefeuilles retenus, recalculés par tools/
    portefeuilles = []
    for v in retenus:
        ident, poids = v["id"], {s: w for s, w in v["poids"].items() if w > 0}
        stats = journal.appeler(stats_portefeuille, "Gouvernance", poids=poids, devise=devise)
        parts = journal.appeler(parts_du_risque, "Gouvernance", poids=poids, devise=devise)
        cles_poids = enregistrer_poids(journal, ident, poids)
        lignes = []
        for l in v["lignes"]:
            s = l["symbole"]
            if poids.get(s, 0) <= 0 or any(x["symbole"] == s for x in lignes):
                continue
            lignes.append({"symbole": s, "nom": table.at[s, "name"],
                           "classe": LIBELLES_CLASSE.get(table.at[s, "asset_class"], table.at[s, "asset_class"]),
                           "secteur": table.at[s, "sector"], "role": l["role"], "theme": l["theme"],
                           "poids": poids[s], "poids_cle": cles_poids[s]})
        portefeuilles.append({
            "id": ident, "nom": v["nom"], "intention": v["intention"], "lignes": lignes,
            "volatilite": journal.enregistrer(f"vol_ptf_{ident}", stats, f"Volatilité du portefeuille simulé {ident}",
                                              chemin=("valeur", "volatilite"), unite="fraction annualisée"),
            "pire_baisse": journal.enregistrer(f"baisse_ptf_{ident}", stats, f"Pire baisse du portefeuille simulé {ident}",
                                               chemin=("valeur", "pire_baisse"), unite="fraction"),
            "parts_du_risque": {s: journal.enregistrer(f"part_{s}_{ident}", parts,
                                                       f"Part de {s} dans le risque du portefeuille {ident}",
                                                       chemin=("valeur", s)) for s in poids},
            "pires_baisses": {s: mesurer(journal, "Marché et risque", s, devise)["pire_baisse"] for s in poids},
            "controles": v["controles"],
        })

    # 5. Explication, avec contrôle des chiffres (deux reprises au plus)
    trace("explication")
    contexte = {
        "profil": {**p, "prenom": prenom}, "demande": demande, "limites_du_profil": cles_limites,
        "orchestration": {"cibles": cibles, "theme": theme},
        "controles_de_la_demande": cartes_demande, "constats_marche": constats,
        "portefeuilles": [{k: x[k] for k in ("id", "nom", "intention", "lignes", "volatilite", "pire_baisse",
                                             "parts_du_risque", "pires_baisses")}
                          | {"controles_non_ok": [k for k in x["controles"] if k["statut"] != "ok"]}
                          for x in portefeuilles],
        "gouvernance": {"essais": len(historique), "rejets_en_cours_de_route": historique},
        "niveau_par_defaut": c["niveau_explication_par_defaut"],
        "hypotheses_deja_affichees": HYPOTHESES_FIXES, "limites_deja_affichees": LIMITES_FIXES,
        "formules": {r["outil"]: r["formule"] for r in journal.chiffres.values() if r["formule"]},
        "chiffres_disponibles": journal.apercu(),
    }
    retour, explication, reprises = None, None, 0
    for reprises in range(3):
        explication = etapes.expliquer(contexte, retour)
        retour = [f"{champ} : {pb}" for champ, texte in _texte_explication(explication) for pb in _problemes(journal, texte)]
        if not retour:
            break
        trace(f"explication refusée : {len(retour)} problème(s)")
    retires = []
    if retour:  # dernier recours : on retire ce qui reste fautif, et on le dit
        e = explication.model_dump()
        for nom in ("niveau2", "faits", "hypotheses", "limites"):
            garde = [t for t in e[nom] if not _problemes(journal, t)]
            retires += [t for t in e[nom] if t not in garde]
            e[nom] = garde
        e["niveau3"]["lignes"] = [t for t in e["niveau3"]["lignes"] if not _problemes(journal, t)]
        explication = etapes.Explication(**e)
    suivi.append({"agent": "Explication", "fait": (
        "Explique à trois niveaux ; chaque chiffre cité renvoie à son calcul."
        + (f" Réécrite {reprises} fois pour retirer des chiffres sans référence." if reprises else ""))})

    accepte = bool(retenus)
    controles_globaux = cartes_demande + [
        _carte(f"portefeuille_{x['id']}", "conforme" if all(k["statut"] == "ok" for k in x["controles"]) else "à signaler",
               f"{sum(k['statut'] == 'ok' for k in x['controles'])} contrôles conformes, "
               f"{sum(k['statut'] == 'alerte' for k in x['controles'])} à signaler.",
               source="agents/gouvernance.py", titre=f"Portefeuille simulé {x['id']} : {x['nom']}")
        for x in portefeuilles] + [
        _carte("simulation", "conforme", "Aucune transaction réelle.", source="agents/pipeline.py",
               titre="Simulation seulement"),
        _carte("sources", "conforme", "Touchez un chiffre pour voir son calcul, sa période et sa source.",
               source="agents/journal.py", titre="Chaque chiffre a sa source"),
    ]
    periode = next((r["periode"] for r in journal.chiffres.values() if r["periode"].get("debut")), {})
    return {
        "version": 1,
        "exemple": False,
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modele": modele_bedrock() or "modèle par défaut de Strands sur Bedrock",
        "note": "Sortie du pipeline d'agents (agents/pipeline.py). Portefeuilles simulés, aucune transaction réelle.",
        "profil": {**p, "prenom": prenom, "demande": demande},
        "contraintes": c,
        "etapes": suivi,
        "orchestration": {"resume_demande": orch.resume_demande, "cibles": cibles, "theme": theme, "notes": notes_orch},
        "constats": constats,
        "portefeuilles": portefeuilles,
        "gouvernance": {
            "essai": len(historique), "essais_max": ESSAIS_MAX, "statut": "accepte" if accepte else "rejete",
            "controles": controles_globaux, "historique": historique,
        },
        "explication": {"niveau_par_defaut": c["niveau_explication_par_defaut"], "sujet": explication.sujet,
                        "niveau1": explication.niveau1, "niveau2": explication.niveau2,
                        "niveau3": explication.niveau3.model_dump()},
        "limites": {
            "faits": ([f"Données de prix du {periode.get('debut')} au {periode.get('fin')}."] if periode else [])
                     + explication.faits,
            "hypotheses": HYPOTHESES_FIXES + explication.hypotheses,
            "limites": LIMITES_FIXES + explication.limites
                       + (["Des phrases de l'explication ont été retirées : elles citaient un chiffre sans référence."]
                          if retires else []),
        },
        "messages": explication.messages.model_dump(),
        "chiffres": journal.chiffres,
        "appels": journal.appels,
    }


def rendre_texte(sortie: dict[str, Any]) -> str:
    """Lecture humaine d'une sortie : clés remplacées par leurs valeurs arrondies."""
    journal = Journal()
    journal.chiffres = sortie["chiffres"]
    r = journal.rendre
    lignes = [f"# {sortie['profil'].get('prenom') or 'Profil'} : {sortie['profil']['demande']}", ""]
    lignes += [f"- {e['agent']} : {e['fait']}" for e in sortie["etapes"]]
    for x in sortie["portefeuilles"]:
        lignes += ["", f"## Portefeuille simulé {x['id']} : {x['nom']}",
                   f"{x['intention']} Volatilité {r('{' + x['volatilite'] + '}')}, pire baisse {r('{' + x['pire_baisse'] + '}')}."]
        lignes += [f"- {l['symbole']} {l['poids'] * 100:.0f} % ({l['role']}) : part du risque "
                   f"{r('{' + x['parts_du_risque'][l['symbole']] + '}')}, pire baisse {r('{' + x['pires_baisses'][l['symbole']] + '}')}"
                   for l in x["lignes"]]
    g = sortie["gouvernance"]
    lignes += ["", f"## Gouvernance : {g['statut']} à l'essai {g['essai']} sur {g['essais_max']}"]
    lignes += [f"- [{k['statut']}] {k['titre']} : {r(k['detail'])}" for k in g["controles"]]
    e = sortie["explication"]
    lignes += ["", f"## Explication (niveau {e['niveau_par_defaut']} par défaut) : {r(e['sujet'])}",
               f"1. {r(e['niveau1'])}", "2. " + " ".join(r(t) for t in e["niveau2"]),
               f"3. {e['niveau3']['formule']}"] + [f"   {r(t)}" for t in e["niveau3"]["lignes"]]
    for nom in ("faits", "hypotheses", "limites"):
        lignes += ["", f"## {nom.capitalize()}"] + [f"- {r(t)}" for t in sortie["limites"][nom]]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", help="Fichier de tests/scenarios/ (profil, demande)")
    parser.add_argument("-o", "--sortie", help="Fichier JSON où écrire la sortie")
    args = parser.parse_args(argv)
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    sortie = lancer(scenario["profil"], scenario["demande"], prenom=scenario.get("persona", {}).get("nom"))
    if args.sortie:
        Path(args.sortie).parent.mkdir(parents=True, exist_ok=True)
        Path(args.sortie).write_text(json.dumps(sortie, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(rendre_texte(sortie))
    return 0 if sortie["gouvernance"]["statut"] == "accepte" else 1


if __name__ == "__main__":
    sys.exit(main())
