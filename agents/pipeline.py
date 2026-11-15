"""Pipeline d'AlphaForge AI : orchestrateur, spécialistes, constructeur, gouvernance, explication.

    python -m agents.pipeline robert            # scénario de tests/scenarios/, sortie dans agents/sorties/
    python -m agents.pipeline --profil p.json --demande "…" --sortie s.json

Les agents (Strands sur Bedrock) décident : quels actifs regarder, quels poids proposer, comment
expliquer. Le code calcule : tout chiffre vient de `tools/` par le registre, et la gouvernance
est déterministe. La sortie est un JSON unique décrit dans docs/sortie-pipeline.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from agents.consignes import CONSTRUCTEUR, EXPLICATION, MARCHE_RISQUE, ORCHESTRATEUR
from agents.gouvernance import ESSAIS_MAX, controle_demande, pour_interface, verifier_portefeuille
from agents.modele import creer_agent
from agents.outils import (devise_calcul, mesurer_actifs_brut, outils_constructeur, outils_mesure,
                           rattrapage_brut, table_univers)
from agents.profil import PLAFOND_THEME_DEFAUT, Profil, contraintes
from agents.registre import Registre
from agents.schemas import Explication, NoteSpecialiste, Orchestration, Proposition
from tools.bedrock import modele_bedrock
from tools.donnees import univers
from tools.gouvernance import SEUILS_PAR_TOLERANCE
from tools.mesures import pire_baisse, volatilite
from tools.portefeuille import correlations, parts_du_risque, stats_portefeuille

RACINE = Path(__file__).resolve().parent.parent
SORTIES = RACINE / "agents" / "sorties"
VERSION_FORMAT = "1.0"
MOTS_INTERDITS = ("conseil", "recommand", "bonne idée", "excellent choix", "bon choix", "allez-y")
LIBELLE_CLASSE = {"equity": "Action", "etf_equity": "Actions (FNB)", "etf_bond": "Obligations (FNB)",
                  "etf_commodity": "Or (FNB)", "crypto": "Cryptoactif"}
LIBELLE_ROLE = {"coeur": "Le cœur du portefeuille", "defensif": "L'amortisseur",
                "diversification": "La diversification", "theme": "L'inclinaison thématique, plafonnée",
                "crypto": "La part audacieuse, plafonnée"}
LIMITES_FIXES = [
    "Univers de 31 actifs choisi en 2026 : biais du survivant.",
    "Les mesures portent sur le 12 novembre 2021 au 12 novembre 2026 : elles décrivent le passé et ne prédisent rien.",
]


def _json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, indent=1)


class Journal:
    """Trace lisible de l'exécution, sur la sortie d'erreur."""

    def __init__(self, actif: bool = True) -> None:
        self.actif, self.debut = actif, time.time()

    def __call__(self, message: str) -> None:
        if self.actif:
            print(f"[{time.time() - self.debut:6.1f} s] {message}", file=sys.stderr, flush=True)


ESSAIS_RESEAU = 3


def _appeler(agent: Any, prompt: str, modele: type) -> Any:
    """Appel d'un agent avec sortie structurée. Une coupure réseau est retentée (3 fois au plus)."""
    for tentative in range(1, ESSAIS_RESEAU + 1):
        try:
            resultat = agent(prompt, structured_output_model=modele)
            break
        except Exception as e:  # coupure du flux Bedrock (connexion réinitialisée, délai dépassé)
            texte = f"{type(e).__name__} {e} {e.__cause__!r}"
            transitoire = any(m in texte for m in ("Connection", "ProtocolError", "Timeout", "timed out",
                                                    "ThrottlingException", "ServiceUnavailable"))
            if not transitoire or tentative == ESSAIS_RESEAU:
                raise
            print(f"  {agent.name} : coupure réseau ({type(e).__name__}), nouvel essai {tentative + 1}",
                  file=sys.stderr, flush=True)
            time.sleep(3 * tentative)
    sortie = resultat.structured_output
    if sortie is None:
        raise RuntimeError(f"{agent.name} n'a pas rendu de sortie structurée.")
    return sortie


def _textes(objet: Any) -> list[str]:
    """Toutes les chaînes d'une structure (pour vérifier repères et vocabulaire)."""
    if isinstance(objet, str):
        return [objet]
    if isinstance(objet, dict):
        return [t for v in objet.values() for t in _textes(v)]
    if isinstance(objet, (list, tuple)):
        return [t for v in objet for t in _textes(v)]
    return []


def verifier_textes(registre: Registre, textes: list[str]) -> dict[str, list[str]]:
    """Repères inconnus, nombres écrits en clair, mots interdits."""
    inconnus, en_clair, interdits = [], [], []
    for t in textes:
        inconnus += registre.reperes_inconnus(t)
        en_clair += registre.nombres_en_clair(t)
        interdits += [m for m in MOTS_INTERDITS if m in t.lower()]
    return {"reperes_inconnus": sorted(set(inconnus)), "nombres_en_clair": sorted(set(en_clair)),
            "mots_interdits": sorted(set(interdits))}


def _probleme(v: dict[str, list[str]]) -> bool:
    return any(v.values())


def _appeler_verifie(agent: Any, prompt: str, modele: type, registre: Registre, j: Journal,
                     champs_internes: tuple[str, ...] = ()) -> Any:
    """Appel structuré, puis une correction si un texte affiché contient un nombre en clair,
    un repère inconnu ou un mot interdit. `champs_internes` : champs non affichés, non vérifiés."""
    sortie = _appeler(agent, prompt, modele)
    affiche = lambda s: _textes(s.model_dump(exclude=set(champs_internes)))  # noqa: E731
    verif = verifier_textes(registre, affiche(sortie))
    if _probleme(verif):
        j(f"{agent.name} : correction demandée {verif}")
        sortie = _appeler(agent, "Ta réponse ne respecte pas les règles. Rends-la complète et corrigée, sans rien "
                          "changer d'autre : remplace chaque nombre écrit en clair par son repère (appelle un outil "
                          "s'il te manque), retire les repères inconnus et les mots interdits.\n" + _json(verif), modele)
    return sortie


# --- étapes ----------------------------------------------------------------------

def orchestrer(profil: Profil, c: dict[str, Any], demande: str, registre: Registre,
               j: Journal) -> tuple[Orchestration, list[str]]:
    agent = creer_agent("orchestrateur", ORCHESTRATEUR)
    prompt = _json({"profil": profil.model_dump(), "limites": c["limites"], "exclusions": c["exclusions"],
                    "demande_de_l_utilisateur": demande, "table_de_l_univers": table_univers()})
    orch: Orchestration = _appeler_verifie(agent, prompt, Orchestration, registre, j,
                                           ("positions_demandees", "theme", "candidats", "consigne_specialiste"))
    connus = set(univers().index)
    anomalies = []
    for p in orch.positions_demandees:
        if p.symbole and p.symbole not in connus:
            anomalies.append(f"Symbole demandé absent de la table : {p.symbole} (ignoré).")
            p.symbole = None
    orch.positions_demandees = [p for p in orch.positions_demandees if p.symbole or p.classe or p.role]
    table = univers()
    if orch.theme:
        if not profil.centres_interet:
            anomalies.append("Thème proposé sans centre d'intérêt déclaré : retiré.")
            orch.theme = None
        else:
            gardes = [s for s in orch.theme.symboles
                      if s in connus and table.at[s, "asset_class"] in ("equity", "etf_equity")]
            if len(gardes) < len(orch.theme.symboles):
                anomalies.append("Symboles du thème hors table ou hors actions et FNB : retirés.")
            orch.theme.symboles = gardes
            if not gardes:
                orch.theme = None
    demandes = [p.symbole for p in orch.positions_demandees if p.symbole]
    orch.candidats = list(dict.fromkeys([s for s in orch.candidats if s in connus] + demandes))
    j(f"orchestrateur : {len(orch.positions_demandees)} position(s) demandée(s), "
      f"thème {orch.theme.nom if orch.theme else 'aucun'}, {len(orch.candidats)} candidats")
    return orch, anomalies


def analyser_marche(profil: Profil, c: dict[str, Any], orch: Orchestration, demande: str,
                    tension: dict[str, Any] | None, registre: Registre, j: Journal) -> NoteSpecialiste:
    agent = creer_agent("marche_et_risque", MARCHE_RISQUE, outils_mesure(registre))
    prompt = _json({"profil": profil.model_dump(), "limites": c["limites"], "demande": demande,
                    "positions_demandees": [p.model_dump() for p in orch.positions_demandees],
                    "tension_avec_le_profil": tension and tension["message"],
                    "theme": orch.theme.model_dump() if orch.theme else None,
                    "candidats": orch.candidats, "consigne": orch.consigne_specialiste})
    note: NoteSpecialiste = _appeler_verifie(agent, prompt, NoteSpecialiste, registre, j)
    j(f"marché et risque : {len(note.constats)} constats, {len(registre.chiffres)} chiffres au registre")
    return note


def _proposition_en_poids(p) -> tuple[dict[str, float], dict[str, Any] | None]:
    poids: dict[str, float] = {}
    for l in p.lignes:
        poids[l.symbole] = poids.get(l.symbole, 0) + l.poids_pourcent / 100
    theme = [l.symbole for l in p.lignes if l.role == "theme"]
    return poids, ({"nom": "thème", "symboles": theme} if theme else None)


def construire_et_gouverner(profil: Profil, c: dict[str, Any], orch: Orchestration, note: NoteSpecialiste,
                            demande: str, tension: dict[str, Any] | None, registre: Registre,
                            j: Journal) -> tuple[Proposition, list[Any], dict[str, Any], list[dict[str, Any]]]:
    agent = creer_agent("constructeur", CONSTRUCTEUR, outils_constructeur(registre, profil, c))
    prompt = _json({"profil": profil.model_dump(), "limites": c["limites"], "origine_des_limites": c["origine"],
                    "exclusions": c["exclusions"], "demande": demande,
                    "tension_avec_le_profil": tension and tension["message"],
                    "theme": orch.theme.model_dump() if orch.theme else None,
                    "note_marche_et_risque": note.model_dump(),
                    "table_de_l_univers": table_univers()})
    historique: list[dict[str, Any]] = []
    prop: Proposition = _appeler_verifie(agent, prompt, Proposition, registre, j)
    for essai in range(1, ESSAIS_MAX + 1):
        verifs = {}
        for p in prop.portefeuilles:
            poids, theme = _proposition_en_poids(p)
            verifs[p.id] = verifier_portefeuille(poids, theme, profil, c)
            historique.append({"essai": essai, "portefeuille": p.id, "nom": p.nom,
                               "poids": poids, "accepte": verifs[p.id]["accepte"],
                               "rejets": verifs[p.id]["rejets"],
                               "messages": [x["message"] for x in verifs[p.id]["controles"]
                                            if x["statut"] == "non conforme"]})
        rejetes = [pid for pid, v in verifs.items() if not v["accepte"]]
        j(f"gouvernance, essai {essai} : {len(verifs) - len(rejetes)} accepté(s), rejetés : {rejetes or 'aucun'}")
        if not rejetes or essai == ESSAIS_MAX:
            break
        retour = {pid: [x["message"] for x in verifs[pid]["controles"] if x["statut"] == "non conforme"]
                  for pid in rejetes}
        prop = _appeler_verifie(agent, "La gouvernance a rejeté ces portefeuilles simulés. Corrige-les sans toucher "
                        "aux portefeuilles acceptés, et rends la proposition complète.\n" + _json(retour), Proposition, registre, j)
    retenus = [p for p in prop.portefeuilles if verifs[p.id]["accepte"]]
    return prop, retenus, verifs, historique


def renommer_portefeuille(p: Any, ancien: str, nouveau: str) -> None:
    """Le constructeur a cité les repères de ses essais (vol_p2…) : ils deviennent ceux du portefeuille retenu."""
    if ancien == nouveau:
        return
    motif = re.compile(r"\{((?:vol|rend|baisse)_|part_)" + re.escape(ancien) + r"(\}|_)")

    def remplacer(texte: str) -> str:
        return motif.sub(lambda m: "{" + m.group(1) + nouveau + m.group(2), texte)

    p.intention = remplacer(p.intention)
    for l in p.lignes:
        l.raison = remplacer(l.raison)


def chiffrer_retenus(retenus: list[Any], orch: Orchestration, profil: Profil, registre: Registre) -> tuple[list[dict], list[str]]:
    """Chiffres finaux de chaque portefeuille retenu, et repères à citer en priorité."""
    table, devise = univers(), devise_calcul(profil)
    a_citer: list[str] = []
    sortie = []
    for p in retenus:
        poids, _ = _proposition_en_poids(p)
        renommer_portefeuille(p, registre.nom_portefeuille(poids), p.id)
        stats = registre.enregistrer(stats_portefeuille(poids, devise=devise), p.id)
        parts = registre.enregistrer(parts_du_risque(poids, devise=devise), p.id)
        lignes, baisses, vols = [], {}, {}
        for l in p.lignes:
            registre.enregistrer_decision(
                f"poids_{p.id}_{l.symbole.lower().replace('-', '_').replace('.', '_')}", l.poids_pourcent / 100,
                "constructeur", {"portefeuille": p.id, "symbole": l.symbole},
                "poids choisi par l'agent constructeur, vérifié par la gouvernance", ["agents/pipeline.py"],
                f"Poids de {l.symbole} dans le portefeuille simulé {p.id}")
            baisses[l.symbole] = registre.enregistrer(pire_baisse(l.symbole))[0]
            vols[l.symbole] = registre.enregistrer(volatilite(l.symbole))[0]
            classe = table.at[l.symbole, "asset_class"]
            if classe == "etf_bond":
                a_citer.append(baisses[l.symbole])
            lignes.append({"symbole": l.symbole, "nom": table.at[l.symbole, "name"], "classe": LIBELLE_CLASSE[classe],
                           "classe_code": classe, "secteur": table.at[l.symbole, "sector"],
                           "role": LIBELLE_ROLE[l.role], "role_code": l.role, "poids": l.poids_pourcent / 100,
                           "raison": l.raison})
        part_de = {s: r for s, r in zip(poids, parts)}
        a_citer += [stats[0]] + parts
        sortie.append({"id": p.id, "nom": p.nom, "intention": p.intention, "lignes": lignes,
                       "volatilite": stats[0], "rendement_passe": stats[1], "pire_baisse": stats[2],
                       "parts_du_risque": part_de, "pires_baisses": baisses, "volatilites": vols})
        theme = [l.symbole for l in p.lignes if l.role == "theme"]
        if theme:
            # Point faible du thème : sa corrélation avec la techno déjà présente dans QQQ.
            symboles = list(dict.fromkeys(theme + ["QQQ"]))
            if len(symboles) > 1:
                a_citer += registre.enregistrer(correlations(symboles))
    return sortie, list(dict.fromkeys(a_citer))


def expliquer(profil: Profil, c: dict[str, Any], demande: str, tension: dict[str, Any] | None,
              note: NoteSpecialiste, portefeuilles: list[dict], controles: list[dict], a_citer: list[str],
              registre: Registre, j: Journal) -> tuple[Explication, dict[str, list[str]]]:
    agent = creer_agent("explication", EXPLICATION, outils_mesure(registre))
    prompt = _json({
        "profil": profil.model_dump(), "niveau_ouvert_par_defaut": c["niveau_explication_par_defaut"],
        "demande": demande, "tension_avec_le_profil": tension and tension["message"],
        "portefeuilles_retenus": [{k: p[k] for k in ("id", "nom", "intention", "lignes")} for p in portefeuilles],
        "controles_de_gouvernance": [{"titre": x["titre"], "statut": x["statut_detaille"], "detail": x["detail"]}
                                     for x in controles],
        "constats_marche_et_risque": note.constats,
        "reperes_a_citer": registre.resume(a_citer),
        "autres_reperes": registre.resume([r for r in registre.chiffres if r not in a_citer]),
    })
    expl: Explication = _appeler_verifie(agent, prompt, Explication, registre, j)
    verif = verifier_textes(registre, _textes(expl.model_dump()))
    j(f"explication : niveau ouvert {c['niveau_explication_par_defaut']}, vérification des textes {verif}")
    return expl, verif


# --- assemblage ---------------------------------------------------------------------

def executer(profil: Profil | dict[str, Any], demande: str, prenom: str | None = None,
             plafond_theme: float = PLAFOND_THEME_DEFAUT, journal: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Exécute tout le pipeline et renvoie la sortie JSON (docs/sortie-pipeline.md)."""
    j = journal or Journal()
    debut = time.time()
    profil = profil if isinstance(profil, Profil) else Profil(**profil)
    c = contraintes(profil, plafond_theme)
    registre = Registre()
    for nom, valeur in c["limites"].items():
        if nom != "min_lignes":
            registre.enregistrer_decision(
                f"limite_{nom}", valeur, "contraintes", {"tolerance_risque": profil.tolerance_risque,
                                                        "horizon_annees": profil.horizon_annees},
                c["origine"][nom], ["agents/profil.py (LIMITES_PAR_TOLERANCE)"],
                f"Limite du profil : {nom}. {c['nature']}.")

    for nom, cle in (("volatilite_max", "volatilite"), ("pire_baisse_max", "pire_baisse")):
        registre.enregistrer_decision(
            f"limite_{nom}", SEUILS_PAR_TOLERANCE[profil.tolerance_risque][cle], "contraintes",
            {"tolerance_risque": profil.tolerance_risque}, f"seuil de tools/gouvernance.py pour une tolérance « {profil.tolerance_risque} »",
            ["tools/gouvernance.py (SEUILS_PAR_TOLERANCE)"],
            f"Seuil de la gouvernance : {nom}. Hypothèse de conception, pas un chiffre de marché.",
            unite="fraction (seuil)")
    orch, anomalies = orchestrer(profil, c, demande, registre, j)
    positions = [p.model_dump() for p in orch.positions_demandees]
    tension = controle_demande({"texte": demande, "positions": positions}, profil, c["limites"])
    a_citer_demande: list[str] = []
    for p in orch.positions_demandees:
        if p.poids is not None:
            cle = (p.symbole or p.classe or p.role or "demande").lower().replace("-", "_").replace(".", "_")
            a_citer_demande.append(registre.enregistrer_decision(
                f"demande_{cle}", p.poids, "accueil", {"demande": demande},
                "part du capital demandée par l'utilisateur, recopiée de sa demande", ["demande de l'utilisateur"],
                f"Part demandée par l'utilisateur pour {p.symbole or p.classe or p.role}"))
    if tension and tension["statut"] == "à signaler":
        for s in tension["symboles"]:
            for r in mesurer_actifs_brut(registre, [s])[s]:
                a_citer_demande.append(r["repere"].strip("{}"))
            a_citer_demande += rattrapage_brut(registre, s)

    note = analyser_marche(profil, c, orch, demande, tension, registre, j)
    prop, retenus, verifs, historique = construire_et_gouverner(profil, c, orch, note, demande, tension, registre, j)
    portefeuilles, a_citer = chiffrer_retenus(retenus, orch, profil, registre)

    controles_ptf = {pid: [pour_interface(x) for x in v["controles"]] for pid, v in verifs.items()}
    principal = retenus[0].id if retenus else (prop.portefeuilles[0].id if prop.portefeuilles else None)
    controles = ([pour_interface(tension)] if tension else []) + (controles_ptf.get(principal, []))

    reperes_limites = [r for r in registre.chiffres if r.startswith(("limite_", "poids_"))]
    expl, verif = expliquer(profil, c, demande, tension, note, portefeuilles, controles,
                            list(dict.fromkeys(a_citer_demande + reperes_limites + a_citer)), registre, j)
    tous_les_textes = _textes([expl.model_dump(), note.constats, [p["intention"] for p in portefeuilles],
                               [l["raison"] for p in portefeuilles for l in p["lignes"]]])
    verif = verifier_textes(registre, tous_les_textes)
    controles.append({
        "statut": "alerte" if _probleme(verif) else "ok", "titre": "Chaque chiffre a sa source",
        "detail": ("Problèmes relevés dans les textes des agents : " + _json(verif)) if _probleme(verif)
        else "Tous les chiffres des textes renvoient à un appel d'outil. Touchez un chiffre pour voir son calcul.",
        "controle": "chiffres_sources", "statut_detaille": "à signaler" if _probleme(verif) else "conforme"})
    controles.append({"statut": "ok", "titre": "Simulation seulement", "detail": "Aucune transaction réelle.",
                      "controle": "simulation", "statut_detaille": "conforme"})

    essais = max((h["essai"] for h in historique), default=0)
    limites_outil = next(iter(verifs.values()))["limites_outil"] if verifs else []
    return {
        "version_format": VERSION_FORMAT,
        "exemple": False,
        "note": f"Sortie du pipeline (agents/pipeline.py), modèle {modele_bedrock() or 'défaut de Strands'} sur Amazon Bedrock.",
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duree_secondes": round(time.time() - debut, 1),
        "profil": {**profil.model_dump(), "prenom": prenom, "demande": demande},
        "contraintes": c,
        "orchestration": {**orch.model_dump(), "anomalies": anomalies},
        "etapes": [
            {"agent": "Orchestrateur", "fait": orch.resume},
            {"agent": "Marché et risque", "fait": note.resume},
            {"agent": "Constructeur", "fait": prop.resume},
            {"agent": "Gouvernance", "fait": f"{len(prop.portefeuilles)} portefeuilles simulés vérifiés contre votre "
                                             f"profil, {len(retenus)} retenu(s), en {essais} essai(s)."},
            {"agent": "Explication", "fait": expl.resume},
        ],
        "specialistes": {"marche_et_risque": note.model_dump()},
        "portefeuilles": portefeuilles,
        "gouvernance": {
            "essai": essais, "essais_max": ESSAIS_MAX,
            "statut": "accepte" if retenus else "rejete",
            "portefeuille_affiche": principal,
            "controles": controles,
            "par_portefeuille": controles_ptf,
            "historique": historique,
        },
        "explication": {"niveau_par_defaut": c["niveau_explication_par_defaut"],
                        **expl.model_dump(include={"sujet", "niveau1", "niveau2", "niveau3"})},
        "limites": {
            "faits": expl.limites.faits,
            "hypotheses": expl.limites.hypotheses + [
                f"Les limites du profil sont des {c['nature']}.",
                "Mesures par actif en devise de cotation ; mesures de portefeuille en "
                f"{'CAD' if devise_calcul(profil) == 'CAD' else 'devise de cotation'}, poids constants."],
            "limites": expl.limites.limites + limites_outil + LIMITES_FIXES,
        },
        "messages": expl.messages.model_dump(),
        "verification_textes": verif,
        "chiffres": registre.chiffres,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exécute le pipeline d'AlphaForge AI sur Bedrock.")
    parser.add_argument("scenario", nargs="?", help="amira, mateo ou robert (tests/scenarios/)")
    parser.add_argument("--profil", help="fichier JSON du profil validé")
    parser.add_argument("--demande", help="demande de l'utilisateur")
    parser.add_argument("--sortie", help="fichier de sortie (défaut : agents/sorties/<scénario>.json)")
    args = parser.parse_args(argv)
    if args.scenario:
        s = json.loads((RACINE / "tests" / "scenarios" / f"{args.scenario}.json").read_text(encoding="utf-8"))
        profil, demande, prenom = s["profil"], s["demande"], s["persona"]["nom"]
        chemin = Path(args.sortie) if args.sortie else SORTIES / f"{args.scenario}.json"
    elif args.profil and args.demande:
        profil, demande, prenom = json.loads(Path(args.profil).read_text(encoding="utf-8")), args.demande, None
        chemin = Path(args.sortie or SORTIES / "sortie.json")
    else:
        parser.error("donner un scénario, ou --profil et --demande")
    sortie = executer(profil, demande, prenom)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sortie écrite dans {chemin.relative_to(RACINE) if chemin.is_relative_to(RACINE) else chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
