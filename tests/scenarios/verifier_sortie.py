"""Applique les contrôles d'un scénario (tests/scenarios/*.json) à une sortie du pipeline.

Usage : python -m tests.scenarios.verifier_sortie robert   (lit agents/sorties/robert.json)

Chaque `attendu` du scénario devient un verdict (id, réussi, détail). Les types de contrôle sont
décrits dans tests/scenarios/LISEZMOI.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from agents.profil import Profil, contraintes
from agents.registre import REPERE

DOSSIER = Path(__file__).parent
RACINE = DOSSIER.parent.parent
SORTIES = RACINE / "agents" / "sorties"
STATUTS = {"signale": "à signaler", "conforme": "conforme", "non conforme": "non conforme",
           "information manquante": "information manquante"}
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")
MOTS_ESG = re.compile(r"esg|controvers|fossile|vert\b|responsable|durab", re.IGNORECASE)


def retenus(sortie: dict) -> list[dict]:
    return [p for p in sortie["portefeuilles"] if p["statut"] == "accepte"]


def textes_affiches(sortie: dict) -> list[str]:
    """Tout ce que l'utilisateur peut lire : explication, limites, messages, analyses, contrôles, portefeuilles."""
    t: list[str] = []
    e = sortie.get("explication") or {}
    t += [e.get("sujet", ""), e.get("niveau1", ""), e.get("reponse_a_la_demande", "")]
    t += e.get("niveau2", []) + (e.get("niveau3") or {}).get("lignes", [])
    t += list((e.get("par_portefeuille") or {}).values())
    for v in (sortie.get("limites") or {}).values():
        t += v
    t += list((sortie.get("messages") or {}).values())
    for a in (sortie.get("analyses") or {}).values():
        t += [c["texte"] for c in a["constats"]] + [c["raison"] for c in a.get("a_ecarter", [])]
        t += a.get("information_manquante", [])
    for p in sortie["portefeuilles"]:
        t += [p["nom"], p["idee"]] + [l["raison"] for l in p["lignes"]]
        t += [c["detail"] for c in p["gouvernance"]["controles"]]
    return [x for x in t if x]


def chiffres_cites(sortie: dict) -> set[str]:
    """Repères cités dans un texte, ou affichés par une carte (portefeuilles, contrôles)."""
    ids = {m for t in textes_affiches(sortie) for m in REPERE.findall(t)}
    for p in retenus(sortie):
        ids |= {p["volatilite"], p["pire_baisse"]} | set(p["parts_du_risque"].values())
        ids |= set(p["pires_baisses"].values()) | set(p.get("volatilites", {}).values())
        for c in p["gouvernance"]["controles"]:
            ids |= set(c.get("chiffres", []))
    return ids & set(sortie["chiffres"])


def _poids_groupe(p: dict, c: dict) -> float:
    if "symboles" in c:
        return sum(l["poids"] for l in p["lignes"] if l["symbole"] in c["symboles"])
    if "classe" in c:
        return sum(l["poids"] for l in p["lignes"] if l["classe"] == c["classe"])
    if "role" in c:
        return sum(l["poids"] for l in p["lignes"] if l["role"] == c["role"])
    raise ValueError(f"groupe inconnu : {c}")


def _limite(valeur: Any, limites: dict) -> float:
    return float(limites[valeur]) if isinstance(valeur, str) else float(valeur)


def _parametres_egaux(attendu: dict, obtenu: dict, sortie: dict) -> bool:
    for k, v in attendu.items():
        if k == "poids" and v == "portefeuille retenu":
            poids = [{l["symbole"]: l["poids"] for l in p["lignes"]} for p in retenus(sortie)]
            if obtenu.get("poids") not in poids:
                return False
        elif k == "perte" and isinstance(v, str) and v.startswith("pire_baisse("):
            symbole = v[len("pire_baisse("):-1]
            pb = [c["valeur"] for c in sortie["chiffres"].values()
                  if c["outil"] == "pire_baisse" and c["parametres"].get("symbole") == symbole]
            if not pb or abs(abs(pb[0]) - float(obtenu.get("perte", -1))) > 1e-9:
                return False
        elif k == "symboles":
            if sorted(obtenu.get("symboles", [])) != sorted(v):
                return False
        elif obtenu.get(k) != v:
            return False
    return True


def verifier(scenario: dict, sortie: dict) -> list[tuple[str, bool, str]]:
    limites = contraintes(Profil(**scenario["profil"]))["limites"]
    ptfs = retenus(sortie)
    textes = textes_affiches(sortie)
    cites = chiffres_cites(sortie)
    verdicts = []
    for a in scenario["attendus"]:
        c = a["controle"]
        t = c["type"]
        ok, detail = False, ""
        if not ptfs and t not in ("texte_absent",):
            verdicts.append((a["id"], False, "aucun portefeuille simulé accepté"))
            continue
        if t == "plafond_poids":
            m = _limite(c["max"], limites)
            mesures = {p["id"]: _poids_groupe(p, c) for p in ptfs}
            ok = all(v <= m + 1e-9 for v in mesures.values())
            detail = f"poids {mesures}, plafond {m}"
        elif t == "diversification":
            mn, mx = _limite(c["min_lignes"], limites), _limite(c["max_part_risquee"], limites)
            mesures = {p["id"]: (len(p["lignes"]), round(sum(l["poids"] for l in p["lignes"]
                                                             if l["classe"] in CLASSES_RISQUEES), 4)) for p in ptfs}
            ok = all(n >= mn and r <= mx + 1e-9 for n, r in mesures.values())
            detail = f"(lignes, part risquée) {mesures}, minimum {mn}, plafond {mx}"
        elif t == "presence_min":
            groupes = c["dans_au_moins_un_portefeuille"]
            avec = [p["id"] for p in ptfs if all(_poids_groupe(p, g) > 0 for g in groupes)]
            ok, detail = bool(avec), f"portefeuilles qui contiennent {groupes} : {avec}"
        elif t == "controle_gouvernance":
            statut = STATUTS.get(c["statut"], c["statut"])
            trouves = [k for p in ptfs for k in p["gouvernance"]["controles"] if k["id"] == c["nom"]]
            ok = len(trouves) == len(ptfs) and all(
                k["statut_outil"] == statut and all(s in k["detail"] for s in c.get("symboles", [])) for k in trouves)
            detail = "; ".join(f"{k['statut_outil']} : {k['detail']}" for k in trouves[:1]) or "contrôle absent"
        elif t == "chiffres_cites":
            manques = []
            for appel in c["appels"]:
                bons = [i for i, ch in sortie["chiffres"].items() if ch["outil"] == appel["outil"]
                        and _parametres_egaux(appel["parametres"], ch["parametres"], sortie) and i in cites]
                if "valeur_attendue" in appel:
                    bons = [i for i in bons if abs(sortie["chiffres"][i]["valeur"] - appel["valeur_attendue"])
                            <= appel["tolerance"]]
                if not bons:
                    manques.append(f"{appel['outil']} {appel['parametres']}")
                else:
                    detail += f"{appel['outil']} -> {{{bons[0]}}} = {sortie['chiffres'][bons[0]]['valeur']:.4f} ; "
            ok = not manques
            detail = detail if ok else "non cités : " + ", ".join(manques)
        elif t == "chiffre_cite_si_retenu":
            manques, vus = [], []
            for p in ptfs:
                for l in p["lignes"]:
                    if l["classe"] != c["classe"]:
                        continue
                    vus.append(l["symbole"])
                    if not any(ch["outil"] == c["outil"] and ch["parametres"].get("symbole") == l["symbole"]
                               and i in cites for i, ch in sortie["chiffres"].items()):
                        manques.append(f"{p['id']}:{l['symbole']}")
            ok = not manques
            detail = f"lignes {c['classe']} : {sorted(set(vus)) or 'aucune'}" + (f", non cités {manques}" if manques else "")
        elif t == "texte_absent":
            bas = " ".join(textes).lower()
            trouves = [m for m in c["motifs"] if m.lower() in bas]
            ok, detail = not trouves, f"motifs trouvés : {trouves}" if trouves else "aucun motif interdit"
        elif t == "texte_present":
            zone = [x for v in (sortie.get(c["zone"]) or {}).values() for x in v] if c.get("zone") == "limites" else textes
            manques = [m for m in c["motifs"] if not any(m.lower() in x.lower() for x in zone)]
            ok, detail = not manques, f"motifs absents : {manques}" if manques else f"présents dans « {c.get('zone', 'tout')} »"
        elif t == "niveau_explication_par_defaut":
            n = (sortie.get("explication") or {}).get("niveau_par_defaut")
            ok, detail = n == c["niveau"], f"niveau {n}"
        elif t == "exclu_ou_signale":
            gardes = [(p["id"], l["symbole"]) for p in ptfs for l in p["lignes"]
                      if l["classe"] == "equity" and _secteur(l["symbole"]) == c["secteur"]]
            non_signales = [g for g in gardes if not any(g[1] in x and Path(c["source"]).name in x for x in textes)]
            ok = not non_signales
            detail = f"titres {c['secteur']} gardés : {gardes or 'aucun'}"
        elif t == "esg_source_ou_inconnu":
            fautifs = [x for x in textes for s in c["symboles"]
                       if s in x and MOTS_ESG.search(x)
                       and not re.search(r"https?://|esg_actions|information manquante", x, re.IGNORECASE)]
            ok = not fautifs
            detail = "jugements ESG sourcés ou « information manquante »" if ok else f"sans source : {fautifs[:2]}"
        elif t == "transparence_fnb":
            gardes = sorted({l["symbole"] for p in ptfs for l in p["lignes"] if l["symbole"] in c["symboles"]})
            sans = [f for f in gardes if not any(f in x and re.search(r"composition|contient|détient|fnb_composition", x,
                                                                       re.IGNORECASE) for x in textes)]
            ok = not sans
            detail = f"FNB larges retenus : {gardes or 'aucun'}" + (f", sans transparence : {sans}" if sans else "")
        else:
            detail = f"type inconnu {t}"
        verdicts.append((a["id"], ok, detail))
    return verdicts


def _secteur(symbole: str) -> str:
    import csv
    with open(RACINE / "data" / "assets_universe.csv", encoding="utf-8") as f:
        return {l["ticker"]: l["sector"] for l in csv.DictReader(f)}.get(symbole, "")


def main(argv: list[str]) -> int:
    echec = 0
    for nom in argv or ["amira", "mateo", "robert"]:
        chemin = SORTIES / f"{nom}.json"
        if not chemin.exists():
            print(f"== {nom} : pas de sortie ({chemin.relative_to(RACINE)}), lancer python -m agents.pipeline {nom}")
            echec += 1
            continue
        scenario = json.loads((DOSSIER / f"{nom}.json").read_text(encoding="utf-8"))
        sortie = json.loads(chemin.read_text(encoding="utf-8"))
        print(f"== {nom}")
        for ident, ok, detail in verifier(scenario, sortie):
            echec += not ok
            print(f"  {'OK   ' if ok else 'ÉCHEC'} {ident} {detail}")
    return 1 if echec else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
