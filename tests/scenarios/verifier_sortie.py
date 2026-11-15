"""Applique les contrôles d'un scénario à une sortie du pipeline (docs/sortie-pipeline.md).

    python -m tests.scenarios.verifier_sortie robert            # lit agents/sorties/robert.json
    python -m tests.scenarios.verifier_sortie robert autre.json

Chaque contrôle donne ok ou échec, avec la raison. Utilisé par test_scenarios.py.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parents[2]
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")
MOTIF_REPERE = re.compile(r"\{([a-z0-9_]+)\}")


def _textes(objet: Any) -> list[str]:
    if isinstance(objet, str):
        return [objet]
    if isinstance(objet, dict):
        return [t for v in objet.values() for t in _textes(v)]
    if isinstance(objet, (list, tuple)):
        return [t for v in objet for t in _textes(v)]
    return []


def textes_affiches(sortie: dict[str, Any]) -> list[str]:
    """Ce que l'utilisateur lit : explication, limites, messages, vérifications, étapes, raisons."""
    return _textes([sortie.get("explication"), sortie.get("limites"), sortie.get("messages"),
                    [(c.get("titre"), c.get("detail")) for c in sortie["gouvernance"]["controles"]],
                    sortie.get("etapes"), sortie.get("specialistes"),
                    [(p.get("nom"), p.get("intention"), [l.get("raison") for l in p["lignes"]])
                     for p in sortie["portefeuilles"]]])


def reperes_cites(sortie: dict[str, Any]) -> set[str]:
    """Repères écrits dans les textes, plus ceux des cartes (volatilité, parts du risque, pires baisses)."""
    cites = {r for t in textes_affiches(sortie) for r in MOTIF_REPERE.findall(t)}
    for p in sortie["portefeuilles"]:
        for cle in ("volatilite", "pire_baisse"):
            if isinstance(p.get(cle), str):
                cites.add(p[cle])
        for cle in ("parts_du_risque", "pires_baisses", "volatilites"):
            cites.update((p.get(cle) or {}).values())
    return cites


def _poids(p: dict[str, Any]) -> dict[str, float]:
    return {l["symbole"]: l["poids"] for l in p["lignes"]}


def _part(p: dict[str, Any], c: dict[str, Any]) -> float:
    total = 0.0
    for l in p["lignes"]:
        if (l["symbole"] in c.get("symboles", []) or l.get("classe_code") == c.get("classe")
                or l.get("role_code") == c.get("role")):
            total += l["poids"]
    return total


def _correspond(chiffre: dict[str, Any], appel: dict[str, Any], sortie: dict[str, Any]) -> bool:
    if chiffre["outil"] != appel["outil"]:
        return False
    p, attendu = chiffre["parametres"], appel["parametres"]
    for cle, v in attendu.items():
        if cle == "perte" and isinstance(v, str) and v.startswith("pire_baisse("):
            origine = chiffre["details"].get("origine", {}).get("parametres", {})
            if origine.get("symbole") != v[len("pire_baisse("):-1]:
                return False
        elif cle == "poids" and v == "portefeuille retenu":
            if p.get("poids") not in [_poids(x) for x in sortie["portefeuilles"]]:
                return False
        elif cle == "symboles":
            if sorted(chiffre["details"].get("cle") or []) != sorted(v):
                return False
        elif p.get(cle) != v:
            return False
    return True


def appliquer(scenario: dict[str, Any], sortie: dict[str, Any]) -> list[dict[str, Any]]:
    limites = sortie["contraintes"]["limites"]
    ptfs = sortie["portefeuilles"]
    chiffres = sortie["chiffres"]
    cites = reperes_cites(sortie)
    texte = " ".join(textes_affiches(sortie)).lower()
    resultats = []

    def noter(attendu: dict[str, Any], ok: bool, raison: str) -> None:
        resultats.append({"id": attendu["id"], "ok": bool(ok), "raison": raison,
                          "description": attendu["description"]})

    if not ptfs:
        return [{"id": "portefeuilles", "ok": False, "raison": "aucun portefeuille simulé retenu", "description": ""}]
    for a in scenario["attendus"]:
        c = a["controle"]
        t = c["type"]
        if t == "plafond_poids":
            plafond = limites[c["max"]]
            parts = {p["id"]: _part(p, c) for p in ptfs}
            noter(a, all(v <= plafond + 1e-9 for v in parts.values()), f"parts {parts}, plafond {plafond}")
        elif t == "diversification":
            mini, maxi = limites[c["min_lignes"]], limites[c["max_part_risquee"]]
            etat = {p["id"]: (len(p["lignes"]), sum(l["poids"] for l in p["lignes"]
                                                    if l.get("classe_code") in CLASSES_RISQUEES)) for p in ptfs}
            noter(a, all(n >= mini and r <= maxi + 1e-9 for n, r in etat.values()),
                  f"(lignes, part risquée) {etat}, minimum {mini} lignes, part risquée max {maxi}")
        elif t == "presence_min":
            manquants = [g for g in c["dans_au_moins_un_portefeuille"] if not any(_part(p, g) > 0 for p in ptfs)]
            noter(a, not manquants, f"groupes absents de tous les portefeuilles : {manquants}")
        elif t == "controle_gouvernance":
            trouves = [x for x in sortie["gouvernance"]["controles"] if x.get("controle") == c["nom"]]
            ok = any(x.get("statut_detaille") == c["statut"]
                     and set(c.get("symboles", [])) <= set(x.get("symboles", [])) for x in trouves)
            noter(a, ok, f"contrôles {c['nom']} affichés : {[(x.get('statut_detaille'), x.get('symboles')) for x in trouves]}")
        elif t == "chiffres_cites":
            manques = []
            for appel in c["appels"]:
                bons = [r for r, ch in chiffres.items() if _correspond(ch, appel, sortie) and r in cites]
                if "valeur_attendue" in appel:
                    bons = [r for r in bons if abs(chiffres[r]["valeur"] - appel["valeur_attendue"]) <= appel["tolerance"]]
                if not bons:
                    manques.append(appel["outil"])
            noter(a, not manques, f"appels sans chiffre cité : {manques}")
        elif t == "chiffre_cite_si_retenu":
            retenus = {l["symbole"] for p in ptfs for l in p["lignes"] if l.get("classe_code") == c["classe"]}
            manques = [s for s in retenus if not any(
                ch["outil"] == c["outil"] and ch["parametres"].get("symbole") == s and r in cites
                for r, ch in chiffres.items())]
            noter(a, not manques, f"{c['classe']} retenus {sorted(retenus)}, sans {c['outil']} cité : {manques}")
        elif t == "texte_absent":
            trouves = [m for m in c["motifs"] if m.lower() in texte]
            noter(a, not trouves, f"motifs trouvés : {trouves}")
        elif t == "texte_present":
            zone = " ".join(_textes(sortie.get(c.get("zone"), sortie))).lower()
            absents = [m for m in c["motifs"] if m.lower() not in zone]
            noter(a, not absents, f"motifs absents de {c.get('zone')} : {absents}")
        elif t == "niveau_explication_par_defaut":
            n = sortie["explication"]["niveau_par_defaut"]
            noter(a, n == c["niveau"], f"niveau ouvert {n}")
        elif t == "exclu_ou_signale":
            gardes = {l["symbole"] for p in ptfs for l in p["lignes"]
                      if l.get("secteur") == c["secteur"] and l.get("classe_code") == "equity" and l["poids"] > 0}
            non_signales = [s for s in gardes if not (s.lower() in texte and Path(c["source"]).name in texte)]
            noter(a, not non_signales, f"titres {c['secteur']} gardés : {sorted(gardes)}, non signalés : {non_signales}")
        elif t == "esg_source_ou_inconnu":
            fiches = (sortie.get("esg") or {}).get("fiches", {})
            fautes = []
            for s in c["symboles"]:
                f = fiches.get(s)
                if f is None:
                    if s.lower() in texte and any(m in texte for m in ("vert", "esg", "controverse")):
                        fautes.append(f"{s} : jugement possible sans fiche ESG")
                elif not (f.get("statut") == "information manquante"
                          or (f.get("source_url") and f.get("source_date"))):
                    fautes.append(f"{s} : fiche sans source datée ni « information manquante »")
            noter(a, not fautes, "; ".join(fautes) or "fiches ESG sourcées")
        elif t == "transparence_fnb":
            transparence = (sortie.get("esg") or {}).get("transparence", {})
            retenus = {l["symbole"] for p in ptfs for l in p["lignes"] if l["symbole"] in c["symboles"]}
            limites_txt = " ".join(_textes(sortie.get("limites"))).lower()
            manques = [s for s in retenus if s not in transparence
                       and not ("transparence" in limites_txt and s.lower() in limites_txt)]
            noter(a, not manques, f"FNB larges retenus {sorted(retenus)}, ni vérifiés ni signalés : {manques}")
        else:
            noter(a, False, f"type de contrôle inconnu : {t}")
    return resultats


def main(argv: list[str]) -> int:
    nom = argv[0]
    scenario = json.loads((RACINE / "tests/scenarios" / f"{nom}.json").read_text(encoding="utf-8"))
    chemin = Path(argv[1]) if len(argv) > 1 else RACINE / "agents/sorties" / f"{nom}.json"
    resultats = appliquer(scenario, json.loads(chemin.read_text(encoding="utf-8")))
    for r in resultats:
        print(f"{'OK    ' if r['ok'] else 'ÉCHEC '} {r['id']} : {r['raison']}")
    return 0 if all(r["ok"] for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
