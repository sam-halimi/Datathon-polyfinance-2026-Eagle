"""Pipeline AlphaForge AI : du profil validé aux portefeuilles simulés expliqués.

    python -m agents.pipeline robert          # scénario de tests/scenarios/robert.json
    python -m agents.pipeline chemin/profil.json

Étapes, chacune visible dans la sortie (`etapes`, `journal`) :

1. Orchestrateur (modèle) : lit la demande, retrouve les symboles dans la table sourcée,
   fixe le thème plafonné et l'univers des candidats.
2. Spécialistes : marché et risque (mesures de tools/ sur chaque candidat, puis constats écrits
   par un modèle). Macro et ESG s'ajoutent à l'étape 4 du plan.
3. Constructeur (modèle) : 2 ou 3 portefeuilles simulés.
4. Gouvernance (sans modèle) : `agents.gouvernance.controler`. Rejet = retour au constructeur,
   2 essais au plus.
5. Explication (modèle) : trois niveaux et limites, avec des repères {id} vers la table des chiffres.

Règle tenue mécaniquement : les textes écrits par un modèle ne contiennent aucun chiffre. Un
texte qui en contient est renvoyé une fois au modèle, puis retiré s'il est encore faux
(`journal.textes_retires`).
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field
from strands import tool

from agents import gouvernance as gv
from agents.journal import Journal, cle
from agents.modele import creer_agent
from agents.profil import Profil
from tools.bedrock import modele_bedrock
from tools import esg as esg_outils
from tools.donnees import univers
from tools.gouvernance import SECTEURS
from tools.portefeuille import parts_du_risque, stats_portefeuille

RACINE = Path(__file__).resolve().parents[1]
SCENARIOS = RACINE / "tests" / "scenarios"
SORTIES = Path(__file__).resolve().parent / "sorties"

CLASSE_LIBELLE = {"equity": "Action", "etf_equity": "FNB d'actions", "etf_bond": "FNB d'obligations",
                  "etf_commodity": "FNB d'or", "crypto": "Cryptoactif"}
Role = Literal["coeur", "amortisseur", "diversification", "theme", "audace"]
ROLE_LIBELLE = {"coeur": "Le cœur du portefeuille", "amortisseur": "L'amortisseur",
                "diversification": "La diversification", "theme": "L'inclinaison thématique, plafonnée",
                "audace": "La part audacieuse, plafonnée"}
VOCABULAIRE = ("Vocabulaire imposé : « portefeuille simulé », « assistant ». N'emploie jamais les mots "
               "« conseil » ni « conseiller ». Aucune prédiction de rendement futur : les données passées "
               "décrivent, elles ne promettent rien.")
PORTEE_SEUILS = ("Les seuils de volatilité et de pire baisse du profil s'appliquent au portefeuille simulé entier, "
                 "pas à un actif seul : ne compare pas un actif à ces seuils, compare-le aux autres actifs.")
REGLE_CHIFFRES = ("Règle absolue : tu n'écris AUCUN chiffre dans tes textes (ni nombre, ni pourcentage, "
                  "ni année). Pour citer une mesure, écris son repère exact entre accolades, par exemple "
                  "{vol_tsla}, pris dans la liste des chiffres disponibles. L'interface le remplace par la "
                  "valeur calculée. Écris des phrases courtes, simples, en français.")


# --- Schémas des sorties de modèle ------------------------------------------

class SymboleDemande(BaseModel):
    symbole: str = Field(description="Symbole exact de la table de l'univers (outil chercher_actif)")
    poids: float | None = Field(None, description="Part du capital demandée, en fraction (40 % -> 0.4), sinon null")


class DemandeAnalysee(BaseModel):
    symboles: list[SymboleDemande] = Field(default_factory=list, description=(
        "Actifs nommés explicitement dans la demande (nom ou symbole). Une catégorie (« la techno », « la crypto ») "
        "va dans classes, pas ici"))
    classes: list[Literal["crypto", "equity", "etf_bond", "etf_commodity", "etf_equity"]] = Field(
        default_factory=list, description="Classes d'actifs demandées en bloc (par exemple « la crypto »)")
    part_risquee: float | None = Field(None, description="Part demandée en actions et crypto ensemble, en fraction, sinon null")
    resume: str = Field(description="La demande reformulée en une phrase, sans aucun chiffre")


class Constats(BaseModel):
    constats: list[str] = Field(description="Deux à quatre constats courts, avec des repères {id}, sans chiffre écrit")


class LigneProposee(BaseModel):
    symbole: str
    poids: float = Field(description="Fraction du capital, entre 0 et 1")
    role: Role


class Proposition(BaseModel):
    id: str = Field(description="A, B ou C")
    nom: str = Field(description="Nom court du portefeuille simulé, sans chiffre")
    intention: str = Field(description="Une phrase : à quoi sert ce portefeuille pour ce profil, sans chiffre")
    lignes: list[LigneProposee]


class Propositions(BaseModel):
    portefeuilles: list[Proposition] = Field(description="Deux ou trois portefeuilles simulés, le plus adapté en premier")


class Messages(BaseModel):
    analyse: str
    repartition: str
    risque: str
    verifications: str
    pourquoi: str
    limites: str
    tout: str


class Explication(BaseModel):
    sujet: str = Field(description="La question à laquelle répond l'explication, sans chiffre")
    niveau1: str = Field(description="Une phrase, avec au moins un repère {id}")
    niveau2: list[str] = Field(description="Deux à quatre phrases : le pourquoi chiffré, avec repères {id}")
    chiffre_central: str = Field(description="Identifiant (sans accolades) du chiffre dont le calcul est montré au niveau 3")
    faits: list[str] = Field(description="Faits observés dans les données, avec repères {id}")
    hypotheses: list[str] = Field(description="Hypothèses du calcul")
    limites: list[str] = Field(description="Ce que l'assistant ne sait pas ou ne mesure pas")
    messages: Messages = Field(description="Une phrase que l'assistant dit à l'ouverture de chaque carte")


# --- Aides ---------------------------------------------------------------------

def _normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return " ".join(t.replace("-", " ").split())


def table_index(table) -> set[str]:
    return set(table.index)


def _lignes_univers(symboles) -> str:
    t = univers()
    return "\n".join(f"{s} | {t.at[s, 'name']} | {t.at[s, 'asset_class']} | {t.at[s, 'sector']} | {t.at[s, 'currency']}"
                     for s in symboles)


class Session:
    """Un passage du pipeline pour un profil et une demande."""

    def __init__(self, profil: Profil, demande: str, prenom: str | None = None) -> None:
        self.profil, self.demande_texte, self.prenom = profil, demande, prenom
        self.journal = Journal()
        self.textes_retires: list[dict[str, str]] = []
        self.c = gv.limites_du_profil(profil)
        self.table = univers()

    # -- textes de modèle : vérification mécanique --------------------------

    def _demander(self, agent, prompt: str, modele: type[BaseModel],
                  textes: Callable[[Any], list[str]]) -> BaseModel:
        obj = agent(prompt, structured_output_model=modele).structured_output
        erreurs = [e for t in textes(obj) for e in self.journal.verifier_texte(t)]
        if erreurs:
            obj = agent("Ta réponse ne respecte pas la règle des chiffres. Corrige exactement ces points et "
                        "renvoie la réponse complète :\n- " + "\n- ".join(erreurs),
                        structured_output_model=modele).structured_output
        return obj

    def _propre(self, texte: str, ou: str) -> str | None:
        erreurs = self.journal.verifier_texte(texte)
        if erreurs:
            self.textes_retires.append({"ou": ou, "texte": texte, "raison": "; ".join(erreurs)})
            return None
        return texte

    # -- 1. Orchestrateur ----------------------------------------------------

    def orchestrer(self) -> None:
        self.journal.agent_courant = "Orchestrateur"
        table = self.table

        @tool
        def chercher_actif(texte: str) -> str:
            """Cherche un actif de l'univers sourcé (data/assets_universe.csv) par nom, symbole ou secteur.
            Renvoie les lignes « symbole | nom | classe | secteur | devise ». Seuls ces symboles existent."""
            t = _normaliser(texte)
            trouves = [s for s in table.index if t in _normaliser(s) or t in _normaliser(table.at[s, "name"])
                       or t in _normaliser(table.at[s, "sector"]) or t in _normaliser(table.at[s, "asset_class"])]
            return _lignes_univers(trouves) if trouves else "Aucun actif de l'univers ne correspond."

        agent = creer_agent("Orchestrateur", (
            "Tu es l'orchestrateur d'un assistant qui construit des portefeuilles simulés. Tu lis la demande "
            "de l'utilisateur et tu en extrais les actifs et les parts demandés. Un symbole ne vient jamais de "
            "ta mémoire : utilise l'outil chercher_actif et ne garde que des symboles qu'il renvoie. " + VOCABULAIRE),
            [chercher_actif])
        d = self._demander(agent, (
            f"Profil validé : {self.profil.model_dump_json()}\nDemande de l'utilisateur : « {self.demande_texte} »\n"
            "Extrais la demande."), DemandeAnalysee, lambda o: [o.resume])
        symboles = [x.model_dump() for x in d.symboles if x.symbole in table.index]
        self.demande = {"texte": self.demande_texte, "resume": self._propre(d.resume, "demande.resume") or "",
                        "symboles": symboles, "classes": list(d.classes), "part_risquee": d.part_risquee}

        # Thème : un centre d'intérêt devient un secteur de la table sourcée, plafonné.
        self.theme = None
        for interet in self.profil.centres_interet:
            secteur = SECTEURS.get(_normaliser(interet))
            if secteur and self.c["limites"]["plafond_theme"] > 0:
                membres = [s for s in table.index if table.at[s, "sector"] == secteur and table.at[s, "asset_class"] == "equity"]
                self.theme = {"nom": interet, "secteur": secteur, "symboles": membres, "source": "data/assets_universe.csv"}
                break

        # Univers des candidats : la table, moins les exclusions et les classes plafonnées à zéro.
        exclus: dict[str, str] = {}
        for s in table.index:
            if table.at[s, "asset_class"] == "crypto" and self.c["limites"]["max_crypto"] == 0:
                exclus[s] = f"crypto plafonnée à zéro ({self.c['origine']['max_crypto']})"
            for terme in self.profil.exclusions:
                n = _normaliser(terme)
                if n == _normaliser(s) or SECTEURS.get(n) == table.at[s, "sector"]:
                    exclus[s] = f"exclusion « {terme} » du profil"
        self.exclus = exclus
        self.candidats = [s for s in table.index if s not in exclus]
        self.ids_limites = gv.enregistrer_limites(self.journal, self.c)

        theme = (f" Thème « {self.theme['nom']} » ({self.theme['secteur']}), plafonné." if self.theme else "")
        self.journal.etape("Orchestrateur", f"Lit votre profil et votre demande, fixe les plafonds du profil.{theme}")

    # -- 2. Spécialiste marché et risque ---------------------------------------

    def marche_et_risque(self) -> None:
        self.journal.agent_courant = "Marché et risque"
        j = self.journal
        self.mesures: dict[str, dict[str, str]] = {}
        for s in sorted(set(self.candidats) | {d["symbole"] for d in self.demande["symboles"]}):
            self.mesures[s] = {"vol": j.mesurer("volatilite", cle("vol", s), symbole=s)["valeur"],
                               "pb": j.mesurer("pire_baisse", cle("pb", s), symbole=s)["valeur"]}

        # Point faible du thème : sa corrélation avec la techno déjà présente dans un FNB large.
        self.corr_theme: dict[str, str] = {}
        if self.theme and "QQQ" in table_index(self.table):
            for m in self.theme["symboles"]:
                self.corr_theme[m] = j.mesurer("correlations", cle("corr", m, "QQQ"), symboles=[m, "QQQ"])["valeur"]

        @tool
        def correlation(symbole_a: str, symbole_b: str) -> str:
            """Corrélation des rendements quotidiens de deux actifs (tools.correlations). Renvoie le repère et la valeur."""
            ident = j.mesurer("correlations", cle("corr", symbole_a, symbole_b), symboles=[symbole_a, symbole_b])["valeur"]
            return j.apercu(ident)

        @tool
        def gain_de_rattrapage(symbole: str) -> str:
            """Gain nécessaire pour revenir au point de départ après la pire baisse d'un actif (tools.gain_de_rattrapage)."""
            pb = self.mesures.get(symbole, {}).get("pb") or j.mesurer("pire_baisse", cle("pb", symbole), symbole=symbole)["valeur"]
            ident = j.enregistrer(cle("rattrapage", symbole), gv._rattrapage(j, pb))
            return j.apercu(ident)

        agent = creer_agent("Marché et risque", (
            "Tu es le spécialiste marché et risque. Tu décris le risque observé sur la fenêtre de données, "
            "sans débat et sans prédire. Tu peux appeler correlation et gain_de_rattrapage pour compléter. "
            + PORTEE_SEUILS + " " + REGLE_CHIFFRES + " " + VOCABULAIRE), [correlation, gain_de_rattrapage])
        demandes = ", ".join(d["symbole"] for d in self.demande["symboles"]) or "aucun actif nommé"
        o = self._demander(agent, (
            f"Profil : tolérance {self.profil.tolerance_risque}, horizon {self.profil.horizon_annees} ans, "
            f"objectif {self.profil.objectif}.\nDemande : « {self.demande_texte} » (actifs nommés : {demandes}).\n"
            f"Chiffres disponibles :\n{j.catalogue()}\n\n"
            "Écris deux à quatre constats utiles au constructeur et à l'utilisateur : le risque des actifs demandés "
            "comparé au profil, et ce qui peut amortir."), Constats, lambda o: o.constats)
        self.constats_marche = [t for i, t in enumerate(o.constats) if self._propre(t, f"marche.constats[{i}]")]
        self.journal.etape("Marché et risque", (
            f"Mesure la volatilité et la pire baisse de {len(self.mesures)} actifs sur la fenêtre de données."))

    # -- 2 bis. Spécialiste ESG et qualité ---------------------------------------

    def _criteres_esg(self) -> list[str]:
        prefs = [_normaliser(x) for x in self.profil.preferences]
        excl = [_normaliser(x) for x in self.profil.exclusions]
        criteres = []
        if any("fossil" in x or "petrol" in x for x in excl):
            criteres.append("activite_fossile")
        if any("esg" in x or "controvers" in x for x in prefs + excl):
            criteres.append("controverse")
        return criteres

    def esg_et_qualite(self) -> None:
        j, table = self.journal, self.table
        j.agent_courant = "ESG et qualité"
        self.criteres_esg = self._criteres_esg()
        self.esg = {"criteres": self.criteres_esg, "fiches": {}, "expositions_fnb": {}, "constats": []}
        if not self.criteres_esg:
            j.etape("ESG et qualité", "Aucune préférence ni exclusion ESG dans le profil : rien à écarter.")
            return
        actions = [x for x in table.index if table.at[x, "asset_class"] == "equity"]
        for x in actions:
            f = esg_outils.fiche_esg(x)
            self.esg["fiches"][x] = f
            for crit in self.criteres_esg:
                if f.get(crit) == "oui":
                    url = f[f"source_{'fossile' if crit == 'activite_fossile' else 'controverse'}_url"]
                    date_s = f[f"source_{'fossile' if crit == 'activite_fossile' else 'controverse'}_date"]
                    self.exclus[x] = (f"{'activité fossile' if crit == 'activite_fossile' else 'controverse documentée'} "
                                      f"selon {esg_outils.FICHIER_ESG} (source : {url}, {date_s})")
                    break
            if "activite_fossile" in self.criteres_esg and table.at[x, "sector"] == "Energy" and x not in self.exclus:
                self.exclus[x] = "secteur Energy (data/assets_universe.csv) et exclusion des énergies fossiles"
        self.candidats = [x for x in table.index if x not in self.exclus]
        for fnb in esg_outils.fnb_connus():
            for crit in self.criteres_esg:
                self.esg["expositions_fnb"][f"{fnb}|{crit}"] = self._exposition_fnb(fnb, crit)

        @tool
        def fiche_esg(symbole: str) -> str:
            """Fiche ESG sourcée d'une action (data/esg_actions.csv) : activité fossile, controverse, résumé,
            source et date. Statut « information manquante » si l'action n'est pas dans la table."""
            f = esg_outils.fiche_esg(symbole)
            return json.dumps(f, ensure_ascii=False)

        expos = "\n".join(f"{k} : {j.apercu(v['valeur'])} ; part non jugée {j.apercu(v['inconnue'])}"
                           for k, v in self.esg["expositions_fnb"].items())
        agent = creer_agent("ESG et qualité", (
            "Tu es le spécialiste ESG et qualité. Tu ne juges jamais une société de mémoire : seulement avec "
            "l'outil fiche_esg, qui lit une table sourcée et datée. Si la fiche dit « information manquante », "
            "tu le dis. Tu signales qu'un FNB large peut contenir des sociétés exclues. " + REGLE_CHIFFRES + " " + VOCABULAIRE),
            [fiche_esg])
        demandes = [d["symbole"] for d in self.demande["symboles"]]
        o = self._demander(agent, (
            f"Profil : préférences {self.profil.preferences}, exclusions {self.profil.exclusions}.\n"
            f"Demande : « {self.demande_texte} » (actifs nommés : {demandes}).\n"
            f"Critères appliqués : {self.criteres_esg}. Actions écartées : {sorted(self.exclus)}.\n"
            f"Expositions des FNB larges (repères) :\n{expos}\n\n"
            "Consulte la fiche des actifs demandés, puis écris deux à quatre constats courts : ce que disent les "
            "fiches sur les actifs demandés (sans dates ni montants, la source est affichée à part), et ce que "
            "contiennent les FNB larges."), Constats, lambda o: o.constats)
        self.esg["constats"] = [t for i, t in enumerate(o.constats) if self._propre(t, f"esg.constats[{i}]")]
        n = sum(1 for v in self.exclus.values() if "esg_actions" in v or "Energy" in v)
        j.etape("ESG et qualité", f"Consulte la table ESG sourcée : {n} action(s) écartée(s) selon vos critères, "
                                  "et mesure ce que contiennent les FNB larges.")

    def _exposition_fnb(self, fnb: str, crit: str) -> dict[str, str]:
        j = self.journal
        res = esg_outils.exposition_fnb(fnb, crit)
        base = cle("expo", fnb, crit)
        v = j.enregistrer(base, {**{k: res[k] for k in ("outil", "parametres", "periode", "unite", "formule",
                                                          "sources", "details")}, "valeur": res["valeur"]})
        inc = j.enregistrer(cle("inconnu", fnb, crit), {
            **{k: res[k] for k in ("outil", "parametres", "periode", "formule", "sources", "details")},
            "valeur": res["details"]["part_inconnue"], "champ": "part_inconnue",
            "unite": "fraction de l'actif net du FNB non jugée par la table ESG"})
        return {"valeur": v, "inconnue": inc, "titres": list(res["details"]["titres_signales"]),
                "date": res["details"]["date_composition"]}

    def exclusions_traitees(self) -> list[str]:
        """Exclusions du profil vérifiées par le spécialiste ESG (et non par l'outil, qui ne les connaît pas)."""
        if "activite_fossile" not in self.criteres_esg:
            return []
        return [t for t in self.profil.exclusions if "fossil" in _normaliser(t) or "petrol" in _normaliser(t)]

    def controles_esg(self, ptf: dict[str, Any]) -> list[dict[str, Any]]:
        """Contrôles ajoutés à la gouvernance quand le profil a des critères ESG."""
        if not self.criteres_esg:
            return []
        j, table = self.journal, self.table
        poids = ptf["poids"]
        controles = []
        for crit in self.criteres_esg:
            libelle = "activité fossile" if crit == "activite_fossile" else "controverse documentée"
            directs = [x for x in poids if table.at[x, "asset_class"] == "equity"
                       and esg_outils.fiche_esg(x).get(crit) == "oui"]
            inconnus = [x for x in poids if table.at[x, "asset_class"] == "equity"
                        and esg_outils.fiche_esg(x).get(crit, "inconnu") == "inconnu"]
            statut = "non conforme" if directs else ("information manquante" if inconnus else "conforme")
            msg = (f"Actions détenues en direct avec {libelle} : {directs}." if directs else
                   f"Statut inconnu dans la table ESG pour : {inconnus}." if inconnus else
                   f"Aucune action détenue en direct avec {libelle} selon {esg_outils.FICHIER_ESG}.")
            controles.append({"controle": "exclusion_esg", "statut": statut, "bloquant": statut == "non conforme",
                              "message": msg, "actifs": directs or inconnus, "source": esg_outils.FICHIER_ESG,
                              "critere": crit})
            for fnb in [x for x in poids if table.at[x, "asset_class"] == "etf_equity"]:
                cle_e = f"{fnb}|{crit}"
                if cle_e not in self.esg["expositions_fnb"]:
                    controles.append({"controle": "transparence_fnb", "statut": "information manquante",
                                      "bloquant": False, "actifs": [fnb], "source": esg_outils.FICHIER_FNB,
                                      "message": f"{fnb} : composition absente de {esg_outils.FICHIER_FNB}, "
                                                 f"il peut contenir des sociétés avec {libelle}."})
                    continue
                e = self.esg["expositions_fnb"][cle_e]
                titres = f" ({', '.join(e['titres'])})" if e["titres"] else ""
                controles.append({
                    "controle": "transparence_fnb", "statut": "à signaler", "bloquant": False,
                    "actifs": [fnb], "source": esg_outils.FICHIER_FNB, "critere": crit,
                    "chiffres": [e["valeur"], e["inconnue"]],
                    "message": (f"{fnb} (composition du {e['date']}) : {{{e['valeur']}}} de l'actif net dans des "
                                f"actions avec {libelle} de la table{titres} ; {{{e['inconnue']}}} du fonds n'est pas "
                                f"jugé par la table ESG.")})
        return controles

    # -- 2 ter. Spécialiste macro et taux -------------------------------------------

    def macro_et_taux(self) -> None:
        j, table = self.journal, self.table
        j.agent_courant = "Macro et taux"
        self.sensibilites: dict[str, str] = {}
        for x in [c for c in self.candidats if table.at[c, "asset_class"] == "etf_bond"]:
            serie = ("BD.CDN.2YR.DQ.YLD" if x == "ZST.TO" else "BD.CDN.10YR.DQ.YLD") if x.endswith(".TO") else "DGS10"
            self.sensibilites[x] = j.mesurer("sensibilite_taux", cle("sens", x), symbole=x, serie_taux=serie)["valeur"]
        pentes = {pays: j.mesurer("pente_courbe", cle("pente", pays), pays=pays)["valeur"] for pays in ("Canada", "États-Unis")}
        agent = creer_agent("Macro et taux", (
            "Tu es le spécialiste macro et taux. Tu décris comment les obligations ont réagi aux taux sur la "
            "fenêtre et l'état de la courbe des taux, sans prévoir les taux. " + REGLE_CHIFFRES + " " + VOCABULAIRE), [])
        ids = list(self.sensibilites.values()) + list(pentes.values())
        o = self._demander(agent, (
            f"Profil : horizon {self.profil.horizon_annees} ans, objectif {self.profil.objectif}.\n"
            f"Chiffres disponibles :\n{j.catalogue(ids)}\n\nÉcris deux ou trois constats courts pour le constructeur : "
            "quelles obligations sont sensibles aux taux, lesquelles le sont peu, et ce que dit la courbe."),
            Constats, lambda o: o.constats)
        self.constats_macro = [t for i, t in enumerate(o.constats) if self._propre(t, f"macro.constats[{i}]")]
        j.etape("Macro et taux", f"Mesure la sensibilité aux taux de {len(self.sensibilites)} FNB obligataires "
                                 "et la pente des courbes canadienne et américaine.")

    # -- 3. Constructeur, 4. Gouvernance ---------------------------------------

    def construire_et_verifier(self) -> None:
        j, lim, table = self.journal, self.c["limites"], self.table
        devise = "CAD" if self.profil.devise == "CAD" else "cotation"

        @tool
        def essayer(poids: dict[str, float]) -> str:
            """Mesure un portefeuille simulé avant de le proposer : volatilité, pire baisse, part du risque
            par ligne (tools.stats_portefeuille, tools.parts_du_risque). poids = {symbole: fraction}, somme 1."""
            try:
                st = stats_portefeuille(poids, devise=devise)["valeur"]
                pr = parts_du_risque(poids, devise=devise)["valeur"]
            except Exception as e:  # noqa: BLE001 - l'erreur est rendue au modèle pour qu'il corrige
                return f"Erreur : {e}"
            parts = ", ".join(f"{s} {v:.0%}" for s, v in sorted(pr.items(), key=lambda x: -x[1]))
            return (f"volatilité {st['volatilite']:.1%} (seuil {self.c['seuils_outil'][self.c['tolerance']]['volatilite']:.0%}), "
                    f"pire baisse {st['pire_baisse']:.1%} (plancher {self.c['seuils_outil'][self.c['tolerance']]['pire_baisse']:.0%}) ; "
                    f"parts du risque : {parts}")

        self.journal.agent_courant = "Constructeur"
        theme = (f"Thème plafonné « {self.theme['nom']} » : symboles {self.theme['symboles']}, rôle « theme », "
                 f"total au plus {lim['plafond_theme']:.0%}." if self.theme else "Aucun thème.")
        consignes = (
            f"Limites du profil (hypothèses de l'équipe) : un titre (action) au plus {lim['max_titre_individuel']:.0%} ; "
            f"crypto au plus {lim['max_crypto']:.0%} ; actions, FNB d'actions et crypto ensemble au plus "
            f"{lim['max_part_risquee']:.0%} ; actions d'un même secteur au plus {lim['max_un_secteur']:.0%} ; "
            f"au moins {lim['min_lignes']} lignes. Volatilité historique au plus "
            f"{self.c['seuils_outil'][self.c['tolerance']]['volatilite']:.0%}, pire baisse pas pire que "
            f"{self.c['seuils_outil'][self.c['tolerance']]['pire_baisse']:.0%}. {theme}")
        catalogue = "\n".join(f"{s} | {table.at[s, 'name']} | {table.at[s, 'asset_class']} | {table.at[s, 'sector']} | "
                              f"{j.apercu(m['vol'])} | {j.apercu(m['pb'])}"
                              for s, m in self.mesures.items() if s in self.candidats)
        agent = creer_agent("Constructeur", (
            "Tu es le constructeur. Tu proposes deux ou trois portefeuilles simulés, différents entre eux, qui "
            "respectent toutes les limites du profil. Tu n'utilises que les candidats listés. Une demande de "
            "l'utilisateur qui dépasse une limite est ramenée sous la limite, jamais acceptée telle quelle. "
            "Vérifie chaque portefeuille avec l'outil essayer avant de le proposer. Les poids sont des "
            "fractions dont la somme vaut exactement 1. Le nom et l'intention ne contiennent aucun chiffre. "
            + VOCABULAIRE), [essayer])
        demande = []
        if self.theme:
            demande.append("Au moins un portefeuille contient le thème (rôle « theme »), au plafond ou en dessous.")
        if "crypto" in self.demande["classes"] and lim["max_crypto"] > 0:
            demande.append("La crypto est demandée et permise : au moins un portefeuille en contient, sous son plafond.")
        if self.criteres_esg:
            demande.append("Profil ESG : un FNB large peut contenir des sociétés exclues (voir les constats ESG) ; "
                           "préfère le FNB filtré ESGV aux FNB larges quand c'est possible.")
        prompt = (f"Profil : {self.profil.model_dump_json()}\nDemande : « {self.demande_texte} »\n{consignes}\n"
                  + " ".join(demande) + "\n"
                  f"Constats du spécialiste marché et risque : {self.constats_marche}\n"
                  f"Constats du spécialiste macro et taux : {self.constats_macro}\n"
                  f"Constats du spécialiste ESG : {self.esg['constats']}\n"
                  f"Candidats (symbole | nom | classe | secteur | volatilité | pire baisse) :\n{catalogue}")
        self.historique: list[dict[str, Any]] = []
        acceptes: dict[str, dict[str, Any]] = {}
        for essai in range(1, gv.ESSAIS_MAX + 1):
            self.journal.agent_courant = "Constructeur"
            props = agent(prompt, structured_output_model=Propositions).structured_output
            self.journal.agent_courant = "Gouvernance"
            rejets_texte = []
            for p in props.portefeuilles[:3]:
                ptf = self._normaliser_ptf(p)
                verdict = gv.controler(ptf, self.profil, self.c, self.controles_esg(ptf), self.exclusions_traitees())
                self.historique.append({"essai": essai, "portefeuille": p.id, "nom": p.nom,
                                        "poids": ptf["poids"], "accepte": verdict["accepte"], "rejets": verdict["rejets"]})
                if verdict["accepte"]:
                    acceptes[p.id] = {"proposition": p, "ptf": ptf, "verdict": verdict, "essai": essai}
                else:
                    msgs = [x["message"] for x in verdict["controles"] if x["statut"] == "non conforme"]
                    rejets_texte.append(f"Portefeuille {p.id} rejeté : " + " ; ".join(msgs))
            if not rejets_texte or essai == gv.ESSAIS_MAX:  # tout rejet retourne au constructeur
                break
            prompt = ("La gouvernance a rejeté des portefeuilles. Corrige-les et renvoie deux ou trois "
                      "portefeuilles complets (les acceptés peuvent rester identiques) :\n" + "\n".join(rejets_texte))
        self.essais = max(h["essai"] for h in self.historique)
        self.acceptes = list(acceptes.values())[:3]
        n_rejets = sum(1 for h in self.historique if not h["accepte"])
        self.journal.etape("Constructeur", f"Propose des portefeuilles simulés ; {len(self.acceptes)} retenus après "
                                           f"{self.essais} essai(s).")
        self.journal.etape("Gouvernance", "Vérifie chaque proposition contre votre profil" + (
            f" : {n_rejets} proposition(s) rejetée(s) et renvoyée(s) au constructeur." if n_rejets
            else " : toutes conformes au premier essai."))

    def _normaliser_ptf(self, p: Proposition) -> dict[str, Any]:
        poids: dict[str, float] = {}
        for l in p.lignes:
            if l.poids > 0:
                poids[l.symbole] = poids.get(l.symbole, 0.0) + float(l.poids)
        roles = {l.symbole: l.role for l in p.lignes}
        membres = [s for s, r in roles.items() if r == "theme"]
        theme = {"nom": self.theme["nom"], "symboles": membres} if self.theme and membres else (
            {"nom": "thème", "symboles": membres} if membres else None)
        return {"poids": poids, "roles": roles, "theme": theme}

    # -- mesures des portefeuilles retenus --------------------------------------

    def mesurer_portefeuilles(self) -> list[dict[str, Any]]:
        j, table = self.journal, self.table
        j.agent_courant = "Gouvernance"
        devise = "CAD" if self.profil.devise == "CAD" else "cotation"
        sortie = []
        for a in self.acceptes:
            p, ptf = a["proposition"], a["ptf"]
            base = cle("ptf", p.id)
            st = j.mesurer("stats_portefeuille", base, poids=ptf["poids"], devise=devise)
            parts = j.mesurer("parts_du_risque", cle("part", p.id), poids=ptf["poids"], devise=devise)
            lignes = [{"symbole": s, "nom": table.at[s, "name"], "classe": CLASSE_LIBELLE[table.at[s, "asset_class"]],
                       "classe_code": table.at[s, "asset_class"], "role": ROLE_LIBELLE[ptf["roles"][s]],
                       "role_code": ptf["roles"][s], "poids": w} for s, w in sorted(ptf["poids"].items(), key=lambda x: -x[1])]
            sortie.append({
                "id": p.id, "nom": self._propre(p.nom, f"portefeuille {p.id}.nom") or f"Portefeuille {p.id}",
                "intention": self._propre(p.intention, f"portefeuille {p.id}.intention") or "",
                "lignes": lignes, "volatilite": st["volatilite"], "pire_baisse": st["pire_baisse"],
                "parts_du_risque": {s: parts[s] for s in ptf["poids"]},
                "pires_baisses": {s: self.mesures[s]["pb"] for s in ptf["poids"]},
                "volatilites": {s: self.mesures[s]["vol"] for s in ptf["poids"]},
                "theme": ptf["theme"], "essai": a["essai"],
                "controles": [gv.pour_interface(x) for x in a["verdict"]["controles"]],
            })
        return sortie

    # -- 5. Explication -------------------------------------------------------

    def expliquer(self, portefeuilles: list[dict[str, Any]], controles_demande: list[dict[str, Any]]) -> dict[str, Any]:
        j = self.journal
        j.agent_courant = "Explication"
        retenu = portefeuilles[0]
        agent = creer_agent("Explication", (
            "Tu es l'agent d'explication. Tu expliques le portefeuille simulé retenu à l'utilisateur, en trois "
            "niveaux : une phrase, puis le pourquoi chiffré, puis le calcul. Tu distingues faits, hypothèses et "
            "limites. Tu n'inventes aucune justification : tu t'appuies sur les contrôles et les chiffres fournis. "
            "Si la demande de l'utilisateur dépasse son profil, tu le dis clairement et tu n'acquiesces pas. "
            + PORTEE_SEUILS + " " + REGLE_CHIFFRES + " " + VOCABULAIRE), [])
        lignes = ", ".join(f"{l['symbole']} ({l['role_code']})" for l in retenu["lignes"])
        prompt = (
            f"Profil : {self.profil.model_dump_json()}\nDemande : « {self.demande_texte} »\n"
            f"Portefeuille simulé retenu : {retenu['nom']} — {lignes}. Repères : volatilité {{{retenu['volatilite']}}}, "
            f"pire baisse {{{retenu['pire_baisse']}}}, parts du risque {retenu['parts_du_risque']}.\n"
            f"Contrôles sur la demande : {[c['message'] for c in controles_demande]}\n"
            f"Constats du spécialiste marché et risque : {self.constats_marche}\n"
            f"Constats du spécialiste macro et taux : {self.constats_macro}\n"
            f"Constats du spécialiste ESG : {self.esg['constats']}\n"
            f"Fiches ESG des actifs demandés : {[self.esg['fiches'].get(d['symbole']) for d in self.demande['symboles']]}\n"
            f"Contrôles du portefeuille retenu : {[c['detail'] for c in retenu['controles'] if c['statut'] != 'ok']}\n"
            f"Chiffres disponibles :\n{j.catalogue()}\n\n"
            "Rédige l'explication. Le sujet répond à la tension principale entre la demande et le profil. "
            "Les messages sont dits par l'assistant à l'ouverture de chaque carte : une phrase courte chacun.")

        def textes(o: Explication) -> list[str]:
            return ([o.sujet, o.niveau1, *o.niveau2, *o.faits, *o.hypotheses, *o.limites]
                    + list(o.messages.model_dump().values()) + [f"{{{o.chiffre_central}}}"])

        o = self._demander(agent, prompt, Explication, textes)
        central = o.chiffre_central if o.chiffre_central in j.chiffres else retenu["volatilite"]
        ref = j.chiffres[central]
        n3 = [f"Outil : {ref['outil']}" + (f" ({ref['champ']})" if ref.get("champ") else "")
              + f", paramètres {json.dumps({k: v for k, v in ref['parametres'].items() if k != 'poids'}, ensure_ascii=False)}."]
        if "poids" in ref["parametres"]:
            n3.append("Poids w : " + ", ".join(f"{s} {w * 100:.0f} %" for s, w in ref["parametres"]["poids"].items()) + ".")
        per = ref["periode"]
        if per.get("debut"):
            n3.append(f"Période : du {per['debut']} au {per['fin']}, {per['observations']} observations.")
        n3.append(f"Sources : {', '.join(ref['sources'])}.")
        n3.append(f"Résultat : {{{central}}}.")
        defauts = Messages(analyse="Je lance l'analyse. Chaque étape est visible.",
                           repartition="Voici le portefeuille simulé retenu.", risque="Voici ce que coûte le risque.",
                           verifications="J'ai vérifié la proposition contre votre profil.",
                           pourquoi="Voici pourquoi.", limites="Ce que je sais, ce que je suppose, ce que je ne sais pas.",
                           tout="Voici tout, sur un seul écran.").model_dump()
        messages = {k: self._propre(v, f"messages.{k}") or defauts[k] for k, v in o.messages.model_dump().items()}
        garder = lambda liste, ou: [t for i, t in enumerate(liste) if self._propre(t, f"{ou}[{i}]")]  # noqa: E731
        j.etape("Explication", "Explique le portefeuille retenu en trois niveaux, avec ses limites.")
        return {
            "explication": {
                "niveau_par_defaut": self.c["niveau_explication_par_defaut"],
                "sujet": self._propre(o.sujet, "explication.sujet") or "Pourquoi ce portefeuille simulé",
                "niveau1": self._propre(o.niveau1, "explication.niveau1") or "",
                "niveau2": garder(o.niveau2, "explication.niveau2"),
                "niveau3": {"formule": ref["formule"], "lignes": n3},
                "chiffre_central": central,
            },
            "limites_modele": {"faits": garder(o.faits, "faits"), "hypotheses": garder(o.hypotheses, "hypotheses"),
                               "limites": garder(o.limites, "limites")},
            "messages": messages,
        }

    # -- assemblage -----------------------------------------------------------

    def limites_calculees(self, portefeuilles: list[dict[str, Any]], limites_outil: list[str]) -> dict[str, list[str]]:
        """Faits, hypothèses et limites écrits par le code, à partir des références de tools/."""
        j, table = self.journal, self.table
        faits, vus = [], set()
        for p in portefeuilles:
            for l in p["lignes"]:
                s = l["symbole"]
                if l["classe_code"] == "etf_bond" and s not in vus:
                    vus.add(s)
                    d = j.chiffres[self.mesures[s]["pb"]]["details"]
                    faits.append(f"{table.at[s, 'name']} ({s}) : pire baisse {{{self.mesures[s]['pb']}}} sur la fenêtre, "
                                 f"du {d['date_pic']} au {d['date_creux']}. Les obligations n'ont pas toujours protégé.")
                    if s in self.sensibilites:
                        faits.append(f"Quand le taux de référence monte d'un point, {s} a varié d'environ "
                                     f"{{{self.sensibilites[s]}}} (régression sur la fenêtre, pas une prévision).")
        if self.corr_theme and any(l["role_code"] == "theme" for p in portefeuilles for l in p["lignes"]):
            faits.append("Point faible du thème : il bouge avec la techno déjà présente dans les FNB larges. "
                         "Corrélation avec QQQ : " + ", ".join(f"{m} {{{i}}}" for m, i in self.corr_theme.items()) + ".")
        for d in self.demande["symboles"]:
            f = self.esg.get("fiches", {}).get(d["symbole"])
            if f and f["statut"] == "connu":
                faits.append(f"{d['symbole']} selon {f['fichier']} : activité fossile « {f['activite_fossile']} », "
                             f"controverse « {f['controverse']} ». {f['resume_controverse']} "
                             f"(source : {f['source_url']}, {f['source_date']}).")
        per = next((r["periode"] for r in j.chiffres.values() if r["outil"] == "volatilite"), {})
        if per:
            faits.insert(0, f"Prix quotidiens du {per['debut']} au {per['fin']} (data/prices_daily.csv, adj_close).")
        hypotheses = [
            "Le passé décrit le risque. Il ne promet rien pour l'avenir.",
            "Mesures par actif dans la devise de cotation ; mesures de portefeuille converties en dollars canadiens "
            "(data/fx_usdcad_daily.csv) pour un profil en CAD.",
            f"Les plafonds du profil sont des {self.c['nature']}.",
        ]
        limites = ["Univers de trente et un actifs choisi en 2026 : biais du survivant.",
                   "Les plafonds par titre et par secteur portent sur les actions détenues en direct ; ce que "
                   "contiennent les FNB n'est mesuré que pour les critères ESG (data/fnb_composition.csv).",
                   *[t for t in limites_outil if "transparence" not in t]]
        if self.criteres_esg:
            limites += [
                "Données ESG : 20 actions seulement (data/esg_actions.csv), sources consultées le 2026-11-15 ; "
                "aucune note ESG chiffrée de fournisseur ; « non » veut dire qu'aucune controverse n'apparaît dans "
                "le dernier dépôt annuel, pas qu'il n'y en a aucune.",
                "Composition des FNB : SPY, QQQ, XIU.TO au 2026-11-12, ESGV au 2026-08-31 et seulement pour nos titres ; "
                "le reste de chaque fonds n'est pas jugé.",
            ]
        return {"faits": faits, "hypotheses": hypotheses, "limites": limites}

    def executer(self) -> dict[str, Any]:
        debut = time.time()
        self.orchestrer()
        self.esg_et_qualite()
        self.journal.agent_courant = "Gouvernance"
        controles_demande = gv.demande_hors_profil(self.demande, self.c, self.journal, self.ids_limites)
        self.marche_et_risque()
        self.macro_et_taux()
        self.construire_et_verifier()
        if not self.acceptes:
            raise RuntimeError(f"Aucun portefeuille accepté après {gv.ESSAIS_MAX} essais : {self.historique}")
        portefeuilles = self.mesurer_portefeuilles()
        exp = self.expliquer(portefeuilles, controles_demande)
        retenu = portefeuilles[0]
        limites_outil = self.acceptes[0]["verdict"]["limites_outil"]
        calc = self.limites_calculees(portefeuilles, limites_outil)
        controles = ([gv.pour_interface(x) for x in controles_demande] + retenu["controles"]
                     + [{"statut": "ok", "titre": gv.TITRES["simulation"], "detail": "Aucune transaction réelle.",
                         "controle": "simulation", "statut_outil": "conforme"}])
        profil = {**self.profil.model_dump(), "demande": self.demande_texte}
        if self.prenom:
            profil["prenom"] = self.prenom
        return {
            "exemple": False,
            "note": f"Sortie du pipeline agents/pipeline.py du {date.today().isoformat()}.",
            "profil": profil,
            "demande_analysee": self.demande,
            "etapes": self.journal.etapes,
            "portefeuilles": portefeuilles,
            "gouvernance": {"essai": self.essais, "essais_max": gv.ESSAIS_MAX,
                            "statut": "accepte", "portefeuille_retenu": retenu["id"],
                            "controles": controles, "historique": self.historique},
            "explication": exp["explication"],
            "limites": {k: calc[k] + exp["limites_modele"][k] for k in ("faits", "hypotheses", "limites")},
            "messages": exp["messages"],
            "chiffres": self.journal.chiffres,
            "contraintes": {"limites": self.c["limites"], "origine": self.c["origine"],
                            "exclusions": self.c["exclusions"], "nature": self.c["nature"],
                            "seuils_risque": {k: self.c["seuils_outil"][self.c["tolerance"]][k] for k in ("volatilite", "pire_baisse")}},
            "specialistes": {"marche_et_risque": self.constats_marche, "macro": self.constats_macro, "esg": self.esg},
            "theme": self.theme,
            "exclus": self.exclus,
            "journal": {"appels": self.journal.appels, "textes_retires": self.textes_retires},
            "meta": {"modele": modele_bedrock() or "défaut de Strands", "duree_secondes": round(time.time() - debut, 1),
                     "date": date.today().isoformat()},
        }


def lancer_scenario(nom_ou_chemin: str) -> dict[str, Any]:
    chemin = Path(nom_ou_chemin)
    if not chemin.exists():
        chemin = SCENARIOS / f"{nom_ou_chemin}.json"
    s = json.loads(chemin.read_text(encoding="utf-8"))
    prenom = s.get("persona", {}).get("nom")
    sortie = Session(Profil(**s["profil"]), s["demande"], prenom).executer()
    sortie["scenario"] = s.get("id")
    return sortie


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        sys.exit(1)
    for nom in argv:
        sortie = lancer_scenario(nom)
        SORTIES.mkdir(exist_ok=True)
        fichier = SORTIES / f"{sortie.get('scenario') or Path(nom).stem}.json"
        fichier.write_text(json.dumps(sortie, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"{fichier.relative_to(RACINE)} : {len(sortie['portefeuilles'])} portefeuille(s), "
              f"{sortie['gouvernance']['essai']} essai(s), {len(sortie['chiffres'])} chiffres, "
              f"{len(sortie['journal']['textes_retires'])} texte(s) retiré(s), {sortie['meta']['duree_secondes']} s")


if __name__ == "__main__":
    main(sys.argv[1:])
