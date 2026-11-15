"""Applique les contrôles d'un scénario (tests/scenarios/*.json) à une sortie du pipeline.

    python -m agents.acceptation tests/scenarios/robert.json agents/sorties/robert.json

Chaque attendu donne ok (True), échec (False) ou non évalué (None, contrôle pas encore branché).
Le vocabulaire des contrôles est décrit dans tests/scenarios/LISEZMOI.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agents.journal import MOTIF_CLE, Journal
from tools.donnees import univers

TOLERANCE = 1e-6
STATUTS_SCENARIO = {"signale": "alerte", "conforme": "ok", "echec": "echec"}
CLASSES_RISQUEES = ("equity", "etf_equity", "crypto")


def textes_affiches(sortie: dict[str, Any], zone: str | None = None) -> list[str]:
    """Tous les textes que l'utilisateur peut lire (avec leurs clés), ou ceux d'une carte."""
    if zone == "limites":
        return [t for v in sortie["limites"].values() for t in v]
    e = sortie["explication"]
    textes = [e["sujet"], e["niveau1"], *e["niveau2"], *e["niveau3"]["lignes"]]
    textes += [t for v in sortie["limites"].values() for t in v]
    textes += list(sortie["messages"].values())
    cartes = sortie["gouvernance"]["controles"] + [k for p in sortie["portefeuilles"] for k in p["controles"]]
    textes += [f"{k['titre']} {k['detail']}" for k in cartes]
    textes += [f"{p['nom']} {p['intention']} " + " ".join(l["role"] for l in p["lignes"]) for p in sortie["portefeuilles"]]
    return textes


def _cles_citees(sortie: dict[str, Any]) -> set[str]:
    cles = {c for t in textes_affiches(sortie) for c in MOTIF_CLE.findall(t)}
    for p in sortie["portefeuilles"]:  # chiffres affichés par les cartes répartition et risque
        cles |= {p["volatilite"], p["pire_baisse"], *p["parts_du_risque"].values(), *p["pires_baisses"].values()}
    return cles


def _poids_groupe(p: dict[str, Any], c: dict[str, Any], table) -> float:
    total = 0.0
    for l in p["lignes"]:
        s = l["symbole"]
        if "symboles" in c and s in c["symboles"]:
            total += l["poids"]
        elif "classe" in c and s in table.index and table.at[s, "asset_class"] == c["classe"]:
            total += l["poids"]
        elif c.get("role") == "theme" and l.get("theme"):
            total += l["poids"]
    return total


def _limite(sortie: dict[str, Any], valeur: Any) -> float:
    return float(sortie["contraintes"]["limites"][valeur]) if isinstance(valeur, str) else float(valeur)


def _appel_correspond(ref: dict[str, Any], appel: dict[str, Any]) -> bool:
    if ref["outil"] != appel["outil"]:
        return False
    attendus = appel.get("parametres", {})
    params = ref.get("parametres", {})
    if "symbole" in attendus and params.get("symbole") != attendus["symbole"]:
        return False
    if "symboles" in attendus and not set(attendus["symboles"]) <= set(params.get("symboles", [])):
        return False
    perte = attendus.get("perte")
    if isinstance(perte, str) and perte.startswith("pire_baisse("):
        origine = ref["details"].get("origine") or {}
        if origine.get("parametres", {}).get("symbole") != perte[len("pire_baisse("):-1]:
            return False
    if "symboles" in attendus and ref["details"].get("chemin", [])[1:] not in (attendus["symboles"], attendus["symboles"][::-1]):
        return False
    return True


def evaluer(attendu: dict[str, Any], sortie: dict[str, Any]) -> tuple[bool | None, str]:
    c = attendu["controle"]
    t = c["type"]
    table = univers()
    portefeuilles = sortie["portefeuilles"]
    if not portefeuilles and t not in ("controle_gouvernance", "texte_absent", "texte_present",
                                        "niveau_explication_par_defaut"):
        return False, "aucun portefeuille simulé retenu"

    if t == "plafond_poids":
        plafond = _limite(sortie, c["max"])
        trop = {p["id"]: _poids_groupe(p, c, table) for p in portefeuilles}
        fautifs = {k: v for k, v in trop.items() if v > plafond + TOLERANCE}
        return not fautifs, f"poids par portefeuille {trop}, plafond {plafond}"

    if t == "diversification":
        n_min, plafond = int(_limite(sortie, c["min_lignes"])), _limite(sortie, c["max_part_risquee"])
        etat = {p["id"]: (len(p["lignes"]), sum(l["poids"] for l in p["lignes"]
                                                if table.at[l["symbole"], "asset_class"] in CLASSES_RISQUEES))
                for p in portefeuilles}
        ok = all(n >= n_min and r <= plafond + TOLERANCE for n, r in etat.values())
        return ok, f"(lignes, part risquée) {etat} ; minimum {n_min} lignes, part risquée au plus {plafond}"

    if t == "presence_min":
        groupes = c["dans_au_moins_un_portefeuille"]
        porteurs = [p["id"] for p in portefeuilles if all(_poids_groupe(p, g, table) > 0 for g in groupes)]
        return bool(porteurs), f"portefeuilles qui contiennent {groupes} : {porteurs}"

    if t == "controle_gouvernance":
        statut = STATUTS_SCENARIO.get(c["statut"], c["statut"])
        cartes = sortie["gouvernance"]["controles"] + [k for p in portefeuilles for k in p["controles"]]
        trouves = [k for k in cartes if k["controle"] == c["nom"] and k["statut"] == statut
                   and all(s in f"{k['titre']} {k['detail']}" for s in c.get("symboles", []))]
        return bool(trouves), f"{len(trouves)} contrôle(s) « {c['nom']} » au statut {statut}"

    if t == "chiffres_cites":
        citees = _cles_citees(sortie)
        manque, details = [], []
        for appel in c["appels"]:
            cles = [k for k, ref in sortie["chiffres"].items() if _appel_correspond(ref, appel) and k in citees]
            if not cles:
                manque.append(appel["outil"])
                continue
            ref = sortie["chiffres"][cles[0]]
            details.append(f"{appel['outil']} -> {{{cles[0]}}} = {ref['valeur']:.4f}")
            devise = ref["parametres"].get("devise") or (ref["details"].get("origine") or {}).get("parametres", {}).get("devise")
            if "valeur_attendue" in appel and devise in (None, "cotation"):
                if abs(ref["valeur"] - appel["valeur_attendue"]) > appel["tolerance"]:
                    manque.append(f"{appel['outil']} (valeur {ref['valeur']:.4f} au lieu de {appel['valeur_attendue']})")
        return not manque, "; ".join(details) + (f" ; manquants : {manque}" if manque else "")

    if t == "chiffre_cite_si_retenu":
        manque = [(p["id"], l["symbole"]) for p in portefeuilles for l in p["lignes"]
                  if table.at[l["symbole"], "asset_class"] == c["classe"]
                  and sortie["chiffres"].get(p["pires_baisses"].get(l["symbole"], ""), {}).get("outil") != c["outil"]]
        return not manque, f"lignes sans {c['outil']} cité : {manque}" if manque else f"chaque ligne {c['classe']} a son {c['outil']}"

    if t in ("texte_absent", "texte_present"):
        journal = Journal()
        journal.chiffres = sortie["chiffres"]
        texte = " ".join(journal.rendre(x) for x in textes_affiches(sortie, c.get("zone"))).lower()
        trouves = [m for m in c["motifs"] if m.lower() in texte]
        if t == "texte_absent":
            return not trouves, f"motifs trouvés : {trouves}" if trouves else "aucun motif interdit"
        return len(trouves) == len(c["motifs"]), f"motifs trouvés : {trouves}"

    if t == "niveau_explication_par_defaut":
        n = sortie["explication"]["niveau_par_defaut"]
        return n == c["niveau"], f"niveau par défaut {n}"

    return None, f"contrôle « {t} » pas encore branché"


def evaluer_scenario(scenario: dict[str, Any], sortie: dict[str, Any]) -> list[dict[str, Any]]:
    resultats = []
    for a in scenario["attendus"]:
        ok, detail = evaluer(a, sortie)
        resultats.append({"id": a["id"], "ok": ok, "description": a["description"], "detail": detail})
    return resultats


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    scenario = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    sortie = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    resultats = evaluer_scenario(scenario, sortie)
    for r in resultats:
        etat = {True: "OK", False: "ÉCHEC", None: "NON ÉVALUÉ"}[r["ok"]]
        print(f"[{etat}] {r['id']} {r['description']}\n         {r['detail']}")
    return 0 if all(r["ok"] is not False for r in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
