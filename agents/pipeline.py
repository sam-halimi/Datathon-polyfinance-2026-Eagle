"""Pipeline AlphaForge : profil validé + demande -> portefeuilles simulés vérifiés et expliqués.

    accueil (profil) -> orchestrateur -> spécialistes -> constructeur -> gouvernance -> explication
                                                          ^______ rejet, 2 essais au plus ___|

Le déroulé est fixe, écrit ici en Python : le pipeline ne se modifie pas tout seul. Les agents
(Strands sur Bedrock, `agents.modele.creer_agent`) interprètent, choisissent et expliquent ; les
chiffres viennent tous de `tools/` par le registre (`agents/registre.py`). La gouvernance est
déterministe (`agents/gouvernance.py`).

Usage : python -m agents.pipeline robert        (écrit agents/sorties/robert.json)
        python -m agents.pipeline amira mateo robert
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agents import consignes, gouvernance
from agents.modele import creer_agent
from agents.outils_agents import fiche_actif, outils_marche, rattrapage, stats_et_parts, table_univers
from agents.profil import Profil, contraintes
from agents.registre import REPERE, Registre, identifiant
from agents.schemas import Analyse, Cadrage, Explication, Propositions
from tools.donnees import univers

RACINE = Path(__file__).resolve().parent.parent
SORTIES = Path(__file__).resolve().parent / "sorties"
ESSAIS_MAX = 2
VERSION_FORMAT = "1.0"
MOTS_INTERDITS = re.compile(r"\bconseil|\bconseill|\brecommand", re.IGNORECASE)


class Journal:
    """Étapes visibles du pipeline : qui a fait quoi, avec quels outils, en combien de temps."""

    def __init__(self, bavard: bool = True) -> None:
        self.etapes: list[dict[str, Any]] = []
        self.bavard = bavard

    def ajouter(self, agent: str, fait: str, debut: float, outils: list[str] | None = None, **autres) -> None:
        e = {"agent": agent, "fait": fait, "outils": sorted(set(outils or [])),
             "duree_s": round(time.time() - debut, 1), **autres}
        self.etapes.append(e)
        if self.bavard:
            print(f"  [{e['duree_s']:>5} s] {agent} : {fait}", file=sys.stderr)


# ---------- contrôle des textes d'agents ----------

def _noms_permis() -> list[str]:
    t = univers()
    return list(t["name"]) + list(t.index)


CONSTANTES_DE_FORMULE = re.compile(r"\(\s*1\s*[-−+]|[-−+]\s*1\s*\)|√\s?(?:252|365)|[×x*]\s?(?:252|365)")


def problemes_texte(reg: Registre, texte: str, formule: bool = False) -> list[str]:
    """Problèmes d'un texte d'agent. `formule` : ligne de calcul, où les constantes d'une formule
    d'outil (1 de « 1 − perte », 252 ou 365 jours) sont permises."""
    if formule:
        texte = CONSTANTES_DE_FORMULE.sub(" ", texte)
    p = reg.verifier_texte(texte, _noms_permis())
    if MOTS_INTERDITS.search(texte):
        p.append("vocabulaire interdit (conseil, recommander)")
    return p


def _problemes_explication(reg: Registre, e: Explication) -> list[tuple[str, list[str]]]:
    return [(chemin, p) for chemin, t in _textes_explication(e)
            if (p := problemes_texte(reg, t, formule=chemin.startswith("niveau3")))]


def _textes_explication(e: Explication) -> list[tuple[str, str]]:
    """(chemin, texte) de tous les champs à contrôler. La formule est exemptée (constantes permises)."""
    t = [("sujet", e.sujet), ("niveau1", e.niveau1), ("reponse_a_la_demande", e.reponse_a_la_demande)]
    t += [(f"niveau2[{i}]", x) for i, x in enumerate(e.niveau2)]
    t += [(f"niveau3.lignes[{i}]", x) for i, x in enumerate(e.niveau3.lignes)]
    t += [(f"portefeuilles[{i}]", x) for i, x in enumerate(e.portefeuilles)]
    for bloc in ("faits", "hypotheses", "limites"):
        t += [(f"limites.{bloc}[{i}]", x) for i, x in enumerate(getattr(e.limites, bloc))]
    t += [(f"messages.{k}", v) for k, v in e.messages.model_dump().items()]
    return t


def _appeler(agent: Any, prompt: str, modele: type) -> Any:
    resultat = agent(prompt, structured_output_model=modele)
    sortie = getattr(resultat, "structured_output", None)
    if sortie is None:
        raise RuntimeError(f"{agent.name} n'a pas rendu de sortie structurée {modele.__name__}.")
    return sortie


def _outils_utilises(agent: Any) -> list[str]:
    noms = []
    for m in getattr(agent, "messages", []):
        for bloc in m.get("content", []):
            if isinstance(bloc, dict) and "toolUse" in bloc:
                noms.append(bloc["toolUse"]["name"])
    return noms


# ---------- étapes ----------

def _nombre_dans(texte: str, fraction: float) -> bool:
    """Le pourcentage figure-t-il dans le texte de l'utilisateur ? (40 % <- 0.40)"""
    cible = fraction * 100
    for n in re.findall(r"\d+(?:[.,]\d+)?", texte):
        if abs(float(n.replace(",", ".")) - cible) < 1e-6:
            return True
    return False


def orchestrer(profil: Profil, demande: str, reg: Registre, journal: Journal) -> Cadrage:
    t0 = time.time()
    agent = creer_agent("orchestrateur", consignes.ORCHESTRATEUR)
    c = contraintes(profil)
    prompt = (f"Profil validé :\n{profil.model_dump_json(indent=1)}\n\nLimites du profil (hypothèses de conception) :\n"
              f"{json.dumps(c['limites'], ensure_ascii=False)}\n\nDemande de l'utilisateur :\n« {demande} »\n\n"
              f"Univers (symbole | nom | classe | devise | secteur) :\n{table_univers()}")
    cadrage: Cadrage = _appeler(agent, prompt, Cadrage)

    # Contrôles : symboles de la table sourcée, pourcentages vraiment écrits par l'utilisateur.
    table = univers()
    ecartes = []
    gardees = []
    for p in cadrage.positions_demandees:
        p.symbole = p.symbole.strip().upper()
        if p.symbole not in table.index:
            ecartes.append(p.symbole)
            continue
        if p.poids_demande is not None and not _nombre_dans(demande, p.poids_demande):
            p.poids_demande = None
        gardees.append(p)
    cadrage.positions_demandees = gardees
    if cadrage.poids_total_demande is not None and not _nombre_dans(demande, cadrage.poids_total_demande):
        cadrage.poids_total_demande = None
    if cadrage.theme:
        cadrage.theme.symboles = [s.upper() for s in cadrage.theme.symboles
                                  if s.upper() in table.index and table.at[s.upper(), "asset_class"] in ("equity", "etf_equity")]
        if not profil.centres_interet or not cadrage.theme.symboles:
            cadrage.theme = None
    for p in cadrage.positions_demandees:
        if p.poids_demande is not None:
            reg.entree(identifiant("demande", p.symbole), p.poids_demande, f"Part demandée pour {p.symbole}",
                       "demande de l'utilisateur", "pourcent", "fraction du capital", par="orchestrateur")
    if cadrage.poids_total_demande is not None:
        reg.entree("demande_total", cadrage.poids_total_demande, "Part du capital demandée au total",
                   "demande de l'utilisateur", "pourcent", "fraction du capital", par="orchestrateur")
    fait = f"Demande lue : {cadrage.demande_resumee}"
    if ecartes:
        fait += f" Symboles hors de la table sourcée ignorés : {', '.join(ecartes)}."
    journal.ajouter("Orchestrateur", fait, t0)
    return cadrage


def _filtrer_analyse(a: Analyse, reg: Registre, journal_notes: list[str], nom: str) -> Analyse:
    table = univers()
    gardes = []
    for c in a.constats:
        p = problemes_texte(reg, c.texte)
        if p:
            journal_notes.append(f"{nom} : constat écarté ({'; '.join(p)}) : « {c.texte[:80]} »")
        else:
            gardes.append(c)
    a.constats = gardes
    a.candidats = [c for c in a.candidats if c.symbole.upper() in table.index and not problemes_texte(reg, c.raison)]
    a.a_ecarter = [c for c in a.a_ecarter if c.symbole.upper() in table.index]
    return a


def specialiste_marche(profil: Profil, cadrage: Cadrage, reg: Registre, fiches: dict, journal: Journal,
                       notes: list[str]) -> Analyse:
    t0 = time.time()
    agent = creer_agent("marché et risque", consignes.MARCHE, outils_marche(reg))
    ids_fiches = [i for f in fiches.values() for i in f.values()]
    limites = [i for i in reg.chiffres if i.startswith(("limite_", "demande_", "profil_"))]
    prompt = (f"Profil : tolérance {profil.tolerance_risque}, horizon {profil.horizon_annees} an(s), "
              f"objectif {profil.objectif}, exclusions {profil.exclusions or 'aucune'}.\n"
              f"Demande : {cadrage.demande_resumee}\nPositions demandées : "
              f"{[p.symbole for p in cadrage.positions_demandees] or 'aucune'} ; classes : {cadrage.classes_demandees or 'aucune'}\n"
              f"Thème : {cadrage.theme.model_dump() if cadrage.theme else 'aucun'}\n"
              f"Consigne de l'orchestrateur : {cadrage.consigne_marche}\n\n"
              f"Limites et demande au registre :\n{reg.catalogue(limites)}\n\n"
              f"Fiches de risque au registre :\n{reg.catalogue(ids_fiches)}")
    analyse = _filtrer_analyse(_appeler(agent, prompt, Analyse), reg, notes, "marché et risque")
    outils = _outils_utilises(agent)
    journal.ajouter("Marché et risque", f"{len(analyse.constats)} constats, {len(analyse.candidats)} candidats, "
                    f"{len(analyse.a_ecarter)} actifs écartés.", t0, ["volatilite", "pire_baisse"] + outils)
    return analyse


def _resume_analyses(analyses: dict[str, Analyse]) -> str:
    morceaux = []
    for nom, a in analyses.items():
        morceaux.append(f"## {nom}\nConstats :\n" + "\n".join(f"- {c.texte}" for c in a.constats))
        if a.candidats:
            morceaux.append("Candidats :\n" + "\n".join(f"- {c.symbole} ({c.role}) : {c.raison}" for c in a.candidats))
        if a.a_ecarter:
            morceaux.append("À écarter :\n" + "\n".join(f"- {c.symbole} : {c.raison}" for c in a.a_ecarter))
        if a.information_manquante:
            morceaux.append("Information manquante :\n" + "\n".join(f"- {x}" for x in a.information_manquante))
    return "\n".join(morceaux)


def _lignes_propres(brut) -> list[dict[str, Any]]:
    fusion: dict[str, dict[str, Any]] = {}
    for l in brut.lignes:
        s = l.symbole.strip().upper()
        if s in fusion:
            fusion[s]["poids"] += float(l.poids)
        else:
            fusion[s] = {"symbole": s, "poids": float(l.poids), "role": l.role, "raison": l.raison}
    return [l for l in fusion.values() if l["poids"] > 0]


def construire_et_verifier(profil: Profil, cadrage: Cadrage, analyses: dict[str, Analyse], reg: Registre,
                           fiches: dict, journal: Journal) -> list[dict[str, Any]]:
    """Constructeur puis gouvernance ; un portefeuille rejeté retourne au constructeur (2 essais au plus)."""
    agent = creer_agent("constructeur", consignes.CONSTRUCTEUR)
    limites = [i for i in reg.chiffres if i.startswith(("limite_", "profil_"))]
    prompt = (f"Profil validé :\n{profil.model_dump_json(indent=1)}\n\n"
              f"Limites à respecter :\n{reg.catalogue(limites)}\nExclusions : {profil.exclusions or 'aucune'}\n\n"
              f"Demande : {cadrage.demande_resumee}\nTension relevée : {cadrage.tension}\n"
              f"Thème : {cadrage.theme.model_dump() if cadrage.theme else 'aucun'}\n\n"
              f"Analyses des spécialistes :\n{_resume_analyses(analyses)}\n\n"
              f"Univers (symbole | nom | classe | devise | secteur) :\n{table_univers()}\n\n"
              "Propose deux ou trois portefeuilles simulés.")
    portefeuilles: list[dict[str, Any]] = []
    a_refaire: list[int] = []
    for essai in range(1, ESSAIS_MAX + 1):
        t0 = time.time()
        if essai == 1:
            props: Propositions = _appeler(agent, prompt, Propositions)
            for i, brut in enumerate(props.portefeuilles):
                portefeuilles.append({"id": "ABC"[i], "nom": brut.nom, "idee": brut.idee, "lignes": _lignes_propres(brut),
                                      "essais": []})
            cibles = list(range(len(portefeuilles)))
        else:
            retour = "\n\n".join(
                f"Portefeuille « {portefeuilles[i]['nom']} » rejeté. Lignes : "
                + ", ".join(f"{l['symbole']} {l['poids']:.2f}" for l in portefeuilles[i]["lignes"])
                + f" (somme {sum(l['poids'] for l in portefeuilles[i]['lignes']):.2f}).\n" + "\n".join(
                    f"- {c['titre']} : {c['detail']}" for c in portefeuilles[i]["essais"][-1]["controles"] if c["bloquant"])
                for i in a_refaire)
            props = _appeler(agent, f"La gouvernance a rejeté ces portefeuilles. Corrige-les, mêmes noms, "
                                    f"et rends uniquement les portefeuilles corrigés.\n\n{retour}", Propositions)
            par_nom = {p.nom.strip().lower(): p for p in props.portefeuilles}
            for k, i in enumerate(a_refaire):
                brut = par_nom.get(portefeuilles[i]["nom"].strip().lower()) or (
                    props.portefeuilles[k] if k < len(props.portefeuilles) else None)
                if brut is not None:
                    portefeuilles[i]["lignes"] = _lignes_propres(brut)
                    portefeuilles[i]["idee"] = brut.idee
            cibles = a_refaire
        a_refaire = []
        for i in cibles:
            p = portefeuilles[i]
            v = gouvernance.verifier(p["lignes"], profil, cadrage, reg, fiches)
            p["essais"].append({"essai": essai, "accepte": v["valeur"],
                                "controles": gouvernance.pour_interface(v["controles"], reg, f"{p['id']}{essai}"),
                                "lignes": [dict(l) for l in p["lignes"]]})
            if not v["valeur"]:
                a_refaire.append(i)
        rejets = {portefeuilles[i]["nom"]: [c["id"] for c in portefeuilles[i]["essais"][-1]["controles"] if c["bloquant"]]
                  for i in a_refaire}
        journal.ajouter("Constructeur", f"Essai {essai} : {len(cibles)} portefeuille(s) simulé(s) proposé(s).", t0)
        journal.ajouter("Gouvernance", (f"Essai {essai} : {len(cibles) - len(a_refaire)} accepté(s), "
                                        f"{len(a_refaire)} rejeté(s)" + (f" {rejets}" if rejets else "") + "."),
                        time.time(), ["verifier_contraintes", "stats_portefeuille"])
        if not a_refaire:
            break
    for p in portefeuilles:
        p["accepte"] = p["essais"][-1]["accepte"]
    return portefeuilles


def expliquer(profil: Profil, demande: str, cadrage: Cadrage, analyses: dict[str, Analyse],
              retenus: list[dict[str, Any]], controle_demande: dict[str, Any], reg: Registre,
              journal: Journal, notes: list[str]) -> Explication:
    t0 = time.time()
    agent = creer_agent("explication", consignes.EXPLICATION)
    niveau = contraintes(profil)["niveau_explication_par_defaut"]
    blocs = []
    pertinents: set[str] = {i for i in reg.chiffres if i.startswith(("limite_", "demande_", "rattrapage_", "profil_"))}
    for f in cadrage.positions_demandees:
        pertinents |= {identifiant("volatilite", f.symbole), identifiant("pire_baisse", f.symbole)}
    for p in retenus:
        ids = p["chiffres"]
        pertinents |= {ids["volatilite"], ids["pire_baisse"], ids["effet_diversification"], *ids["parts_du_risque"].values()}
        lignes = []
        for l in p["lignes"]:
            fl = p["fiches"][l["symbole"]]
            pertinents |= set(fl.values())
            pertinents.add(ids["poids"][l["symbole"]])
            lignes.append(f"- {l['symbole']} ({l['role']}) : poids {{{ids['poids'][l['symbole']]}}} ; "
                          f"part du risque {{{ids['parts_du_risque'][l['symbole']]}}} ; volatilité {{{fl['volatilite']}}} ; "
                          f"pire baisse {{{fl['pire_baisse']}}} ; raison : {l['raison']}")
        alertes = [f"- {c['titre']} : {c['detail']}" for c in p["controles"] if c["statut"] != "ok"]
        blocs.append(f"Portefeuille {p['id']} « {p['nom']} » : {p['idee']}\nVolatilité {{{ids['volatilite']}}}, "
                     f"pire baisse {{{ids['pire_baisse']}}}, diversification {{{ids['effet_diversification']}}}.\n"
                     + "\n".join(lignes) + ("\nContrôles à signaler :\n" + "\n".join(alertes) if alertes else ""))
    for a in analyses.values():
        for c in a.constats:
            pertinents |= set(REPERE.findall(c.texte))
    pertinents &= set(reg.chiffres)
    formules = sorted({c["formule"] for i, c in reg.chiffres.items() if i in pertinents and c["formule"] != "valeur donnée, pas calculée"})
    devise_ptf = "en CAD (prix en USD convertis avec fx_usdcad_daily.csv)" if profil.devise == "CAD" else "en devise de cotation"
    prompt = (f"Profil : {profil.model_dump_json()}\nNiveau d'explication ouvert par défaut : {niveau} "
              f"(connaissance « {profil.connaissance} »).\n\nDemande de l'utilisateur : « {demande} »\n"
              f"Tension relevée par l'orchestrateur : {cadrage.tension}\n"
              f"Contrôle de la gouvernance sur la demande : {controle_demande['detail']}\n\n"
              f"Portefeuilles simulés retenus (les poids sont des décisions du constructeur, pas des mesures) :\n"
              + "\n\n".join(blocs) + f"\n\nConstats des spécialistes :\n{_resume_analyses(analyses)}\n\n"
              f"Méthode : volatilité, pire baisse et parts du risque des portefeuilles calculées {devise_ptf}, sur les "
              "jours communs, poids constants ; fiches par actif en devise de cotation.\n\n"
              f"Formules des outils :\n" + "\n".join(f"- {f}" for f in formules) + "\n\n"
              f"Chiffres du registre que tu peux citer (repère = valeur : description) :\n{reg.catalogue(sorted(pertinents))}")
    e: Explication = _appeler(agent, prompt, Explication)
    problemes = _problemes_explication(reg, e)
    if problemes:
        liste = "\n".join(f"- {c} : {'; '.join(p)}" for c, p in problemes)
        e = _appeler(agent, f"Ces champs sont refusés par le contrôle des chiffres :\n{liste}\n"
                            "Réécris toute l'explication : chaque chiffre doit être un repère {identifiant} "
                            "de la liste fournie, aucun chiffre écrit en dur.", Explication)
        problemes = _problemes_explication(reg, e)
    e = _nettoyer_explication(e, reg, notes, problemes)
    journal.ajouter("Explication", f"Trois niveaux écrits, niveau {niveau} ouvert par défaut.", t0,
                    retries=1 if problemes else 0)
    return e


def _nettoyer_explication(e: Explication, reg: Registre, notes: list[str], problemes) -> Explication:
    """Dernier filet : un texte encore refusé après le second essai est retiré, et c'est dit."""
    if not problemes:
        return e
    refus = "Texte retiré : il contenait un chiffre sans référence."
    for chemin, p in problemes:
        notes.append(f"explication : {chemin} retiré ({'; '.join(p)})")
    ok = lambda t: not problemes_texte(reg, t)  # noqa: E731
    e.niveau2 = [t for t in e.niveau2 if ok(t)]
    e.niveau3.lignes = [t for t in e.niveau3.lignes if not problemes_texte(reg, t, formule=True)]
    e.portefeuilles = [t if ok(t) else refus for t in e.portefeuilles]
    for bloc in ("faits", "hypotheses", "limites"):
        setattr(e.limites, bloc, [t for t in getattr(e.limites, bloc) if ok(t)])
    for champ in ("sujet", "niveau1", "reponse_a_la_demande"):
        if not ok(getattr(e, champ)):
            setattr(e, champ, refus)
    for k, v in e.messages.model_dump().items():
        if not ok(v):
            setattr(e.messages, k, "Voici la carte.")
    e.limites.limites.append("Une partie de l'explication a été retirée par le contrôle des chiffres.")
    return e


# ---------- assemblage ----------

def lancer(profil: Profil, demande: str, persona: str | None = None, bavard: bool = True,
           specialistes: list[str] | None = None) -> dict[str, Any]:
    """Exécute le pipeline et renvoie la sortie au format de docs/sortie-pipeline.md."""
    debut = time.time()
    reg, journal, notes = Registre(), Journal(bavard), []
    specialistes = specialistes or ["marche"]
    ids_limites = gouvernance.inscrire_limites(reg, profil)

    cadrage = orchestrer(profil, demande, reg, journal)

    # Fiches de risque de tout l'univers : calcul déterministe, même registre.
    fiches = {s: fiche_actif(reg, s) for s in univers().index}
    for p in cadrage.positions_demandees:
        rattrapage(reg, p.symbole)

    analyses: dict[str, Analyse] = {}
    if "marche" in specialistes:
        analyses["Marché et risque"] = specialiste_marche(profil, cadrage, reg, fiches, journal, notes)
    for nom, fonction in SPECIALISTES_SUPPLEMENTAIRES.items():
        if nom in specialistes:
            libelle, analyse = fonction(profil, cadrage, reg, fiches, journal, notes)
            analyses[libelle] = analyse

    portefeuilles = construire_et_verifier(profil, cadrage, analyses, reg, fiches, journal)
    devise = "CAD" if profil.devise == "CAD" else "cotation"
    for p in portefeuilles:
        p["controles"] = p["essais"][-1]["controles"]
        p["fiches"] = {l["symbole"]: fiches[l["symbole"]] for l in p["lignes"] if l["symbole"] in fiches}
        if p["accepte"]:
            p["chiffres"] = stats_et_parts(reg, p["id"].lower(), {l["symbole"]: l["poids"] for l in p["lignes"]}, devise)
            p["chiffres"]["poids"] = {
                l["symbole"]: reg.entree(identifiant("poids", p["id"], l["symbole"]), l["poids"],
                                         f"Part de {l['symbole']} dans le portefeuille {p['id']}",
                                         "décision du constructeur, vérifiée par la gouvernance", "pourcent",
                                         "fraction du capital", par="constructeur")
                for l in p["lignes"]}
    retenus = [p for p in portefeuilles if p["accepte"]]
    controle_demande = next(c for c in (retenus or portefeuilles)[0]["controles"] if c["id"] == "demande_hors_profil")

    explication = expliquer(profil, demande, cadrage, analyses, retenus, controle_demande, reg, journal, notes) \
        if retenus else None
    return assembler(profil, demande, persona, cadrage, analyses, portefeuilles, explication, reg, journal,
                     notes, ids_limites, time.time() - debut)


SPECIALISTES_SUPPLEMENTAIRES: dict[str, Callable[..., tuple[str, Analyse]]] = {}


def assembler(profil, demande, persona, cadrage, analyses, portefeuilles, explication, reg, journal, notes,
              ids_limites, duree) -> dict[str, Any]:
    table = univers()
    sortie_ptf = []
    for p in portefeuilles:
        q = {"id": p["id"], "nom": p["nom"], "idee": p["idee"], "statut": "accepte" if p["accepte"] else "rejete",
             "lignes": [{"symbole": l["symbole"], "nom": table.at[l["symbole"], "name"] if l["symbole"] in table.index else l["symbole"],
                         "classe": table.at[l["symbole"], "asset_class"] if l["symbole"] in table.index else "inconnue",
                         "role": l["role"], "raison": l["raison"], "poids": l["poids"]} for l in p["lignes"]],
             "gouvernance": {"essai": len(p["essais"]), "essais_max": ESSAIS_MAX,
                             "statut": "accepte" if p["accepte"] else "rejete", "controles": p["controles"],
                             "historique": [{"essai": e["essai"], "accepte": e["accepte"],
                                             "rejets": [c["id"] for c in e["controles"] if c["bloquant"]],
                                             "lignes": e["lignes"]} for e in p["essais"]]}}
        if p["accepte"]:
            ids = p["chiffres"]
            q.update({"volatilite": ids["volatilite"], "pire_baisse": ids["pire_baisse"],
                      "effet_diversification": ids["effet_diversification"],
                      "parts_du_risque": ids["parts_du_risque"],
                      "poids": ids["poids"],
                      "pires_baisses": {s: f["pire_baisse"] for s, f in p["fiches"].items()},
                      "volatilites": {s: f["volatilite"] for s, f in p["fiches"].items()}})
        sortie_ptf.append(q)

    retenus = [q for q in sortie_ptf if q["statut"] == "accepte"]
    sortie: dict[str, Any] = {
        "format": VERSION_FORMAT,
        "exemple": False,
        "persona": persona,
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duree_s": round(duree, 1),
        "profil": profil.model_dump(),
        "demande": {"texte": demande, "resume": cadrage.demande_resumee, "tension": cadrage.tension,
                    "positions": [p.model_dump() for p in cadrage.positions_demandees],
                    "classes": cadrage.classes_demandees,
                    "theme": cadrage.theme.model_dump() if cadrage.theme else None},
        "contraintes": {**contraintes(profil), "chiffres": ids_limites},
        "etapes": journal.etapes,
        "analyses": {nom: a.model_dump() for nom, a in analyses.items()},
        "portefeuilles": sortie_ptf,
        "portefeuille_principal": retenus[0]["id"] if retenus else None,
        "statut": "accepte" if retenus else "aucun_portefeuille_accepte",
        "explication": None, "limites": None, "messages": None,
        "notes_de_controle": notes,
        "appels": reg.appels,
    }
    if explication is not None:
        e = explication
        sortie["explication"] = {
            "niveau_par_defaut": contraintes(profil)["niveau_explication_par_defaut"], "sujet": e.sujet,
            "niveau1": e.niveau1, "niveau2": e.niveau2, "niveau3": e.niveau3.model_dump(),
            "reponse_a_la_demande": e.reponse_a_la_demande,
            "par_portefeuille": dict(zip([q["id"] for q in retenus], e.portefeuilles)),
        }
        sortie["limites"] = e.limites.model_dump()
        sortie["messages"] = e.messages.model_dump()
    # Chiffres : ceux que la sortie cite ou référence, rien de plus.
    texte = json.dumps({k: v for k, v in sortie.items() if k != "appels"}, ensure_ascii=False)
    utilises = set(REPERE.findall(texte)) | set(re.findall(r'"([a-z0-9_]+)"', texte))
    sortie["chiffres"] = {k: v for k, v in reg.chiffres.items() if k in utilises}
    return sortie


def charger_scenario(nom: str) -> tuple[Profil, str]:
    s = json.loads((RACINE / "tests" / "scenarios" / f"{nom}.json").read_text(encoding="utf-8"))
    return Profil(**s["profil"]), s["demande"]


def resume(sortie: dict[str, Any]) -> str:
    lignes = [f"Persona {sortie['persona']} : {sortie['statut']} en {sortie['duree_s']} s, "
              f"{len(sortie['appels'])} appels d'outils, {len(sortie['chiffres'])} chiffres cités."]
    ch = sortie["chiffres"]

    def v(i):
        from agents.registre import afficher
        return afficher(ch[i]["valeur"], ch[i]["format"]) if i in ch else "?"
    for p in sortie["portefeuilles"]:
        lignes.append(f"  {p['id']} « {p['nom']} » : {p['statut']} (essai {p['gouvernance']['essai']})"
                      + (f", volatilité {v(p['volatilite'])}, pire baisse {v(p['pire_baisse'])}" if p["statut"] == "accepte" else ""))
        lignes.append("     " + ", ".join(f"{l['symbole']} {l['poids'] * 100:.0f} %" for l in p["lignes"]))
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("personas", nargs="+", help="amira, mateo, robert")
    ap.add_argument("--specialistes", default="marche", help="liste séparée par des virgules : marche,macro,esg")
    args = ap.parse_args(argv)
    SORTIES.mkdir(exist_ok=True)
    for nom in args.personas:
        profil, demande = charger_scenario(nom)
        print(f"== {nom} : « {demande} »", file=sys.stderr)
        sortie = lancer(profil, demande, persona=nom, specialistes=args.specialistes.split(","))
        chemin = SORTIES / f"{nom}.json"
        chemin.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(resume(sortie))
        print(f"  -> {chemin.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
