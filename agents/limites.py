"""Limites et hypothèses propres à un portefeuille simulé, calculées par le code.

Chaque limite nomme la ou les lignes concernées et porte au moins un repère `{id}` vers un
chiffre de tools/. Elles sont triées par importance pour ce profil : le même fait (une pire
baisse longue, des obligations sensibles aux taux) pèse plus pour un horizon court ou une
tolérance faible. Les poids d'importance sont des hypothèses de l'équipe, écrites ici.

Chaque hypothèse dit ce qui changerait si elle tombait, chiffré par tools/ (fenêtre plus
courte, corrélations à 1, calcul sans conversion en CAD, plafonds de l'équipe).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from agents.adequation import _ref, mesures_portefeuille, normaliser
from agents.journal import Journal, cle
from agents.profil import Profil
from tools import esg as esg_outils
from tools.donnees import univers

PART_OBLIGATIONS_LOURDE = 0.25
ANNEES_FENETRE_RECENTE = 2

# Importance de base de chaque type de limite, puis multiplicateurs selon le profil.
IMPORTANCE = {"source_de_risque": 3.0, "duree_pire_baisse": 2.5, "taux": 2.0, "dollar_americain": 1.5,
              "recoupement_fnb": 1.5, "theme_non_couvert": 1.5, "donnee_manquante": 1.0}


def _multiplicateur(type_: str, profil: Profil) -> float:
    prudent = profil.tolerance_risque == "faible" or profil.objectif == "préservation du capital"
    court = profil.horizon_annees < 5
    esg = bool(profil.exclusions) or any("esg" in normaliser(x) for x in profil.preferences)
    m = 1.0
    if type_ == "duree_pire_baisse" and (prudent or court):
        m *= 2.0
    if type_ == "taux" and (prudent or court):
        m *= 1.5
    if type_ in ("donnee_manquante", "recoupement_fnb") and esg:
        m *= 2.0
    if type_ == "theme_non_couvert" and profil.centres_interet:
        m *= 2.0
    if type_ == "source_de_risque" and profil.tolerance_risque == "élevé":
        m *= 0.8
    return m


def _limite(type_: str, texte: str, lignes: list[str], chiffres: list[str], profil: Profil, poids: float = 1.0):
    return {"texte": texte, "type": type_, "lignes": lignes, "chiffres": chiffres,
            "_score": IMPORTANCE[type_] * _multiplicateur(type_, profil) * poids}


def _serie_taux(symbole: str) -> str:
    if not symbole.endswith(".TO"):
        return "DGS10"
    return "BD.CDN.2YR.DQ.YLD" if symbole == "ZST.TO" else "BD.CDN.10YR.DQ.YLD"


def limites_specifiques(profil: Profil, poids: dict[str, float], ident: str, j: Journal,
                        mesures: dict[str, dict[str, str]], ids_limites: dict[str, str],
                        interets_non_couverts: list[dict[str, str]]) -> list[dict[str, Any]]:
    table = univers()
    devise = "CAD" if profil.devise == "CAD" else "cotation"
    m = mesures_portefeuille(j, ident, poids, devise)
    nom = lambda s: f"{table.at[s, 'name']} ({s})"  # noqa: E731
    sortie = []

    # 1. Première source de risque.
    parts = {s: j.chiffres[i]["valeur"] for s, i in m["parts"].items()}
    s = max(parts, key=parts.get)
    pid = j.chiffres.get(cle("poids", ident, s)) and cle("poids", ident, s)
    sortie.append(_limite(
        "source_de_risque",
        f"{nom(s)} porte {{{m['parts'][s]}}} du risque du portefeuille" + (f" pour {{{pid}}} du capital" if pid else "")
        + f" : sa pire baisse sur la fenêtre est {{{mesures[s]['pb']}}}. Si elle se répète, c'est d'abord cette ligne qui pèse.",
        [s], [m["parts"][s], mesures[s]["pb"]] + ([pid] if pid else []), profil, 1 + max(0.0, parts[s] - poids[s])))

    # 2. Exposition au dollar américain (profil en CAD).
    usd = [x for x in poids if table.at[x, "currency"] == "USD"]
    if usd and profil.devise == "CAD":
        expo = sum(poids[x] for x in usd)
        eid = j.enregistrer(cle("expo_usd", ident), _ref(
            "agents.limites.exposition_devise", {"portefeuille": ident, "devise": "USD"}, expo, "fraction du capital",
            "Σ poids des lignes cotées en USD", ["data/assets_universe.csv (currency)"], "calcul sur les poids décidés"))
        grande = max(usd, key=lambda x: poids[x])
        rc = j.mesurer("rendement_en_cad", cle("cad", grande), symbole=grande)["valeur"]
        ref = j.chiffres[rc]
        change = j.enregistrer(cle("change", grande), {
            **{k: ref[k] for k in ("outil", "parametres", "periode", "sources")},
            "valeur": ref["details"]["effet_change_total"], "unite": "fraction", "champ": "effet_change_total",
            "formule": "taux USD/CAD de fin / taux de début − 1", "details": ref["details"]})
        sortie.append(_limite(
            "dollar_americain",
            f"{', '.join(usd)} sont cotés en dollars américains : {{{eid}}} du capital. Leur valeur en dollars "
            f"canadiens suit aussi le taux de change : sur la fenêtre, le change seul a fait varier {grande} de {{{change}}}.",
            usd, [eid, change], profil, 1 + expo))

    # 3. Sensibilité aux taux quand les obligations pèsent lourd.
    obligations = [x for x in poids if table.at[x, "asset_class"] == "etf_bond"]
    part_oblig = sum(poids[x] for x in obligations)
    if obligations and part_oblig >= PART_OBLIGATIONS_LOURDE:
        sens = {x: j.mesurer("sensibilite_taux", cle("sens", x), symbole=x, serie_taux=_serie_taux(x))["valeur"]
                for x in obligations}
        pondere = sum(poids[x] * j.chiffres[sens[x]]["valeur"] for x in obligations)
        sid = j.enregistrer(cle("sens_ptf", ident), _ref(
            "agents.limites.sensibilite_ponderee", {"portefeuille": ident, "lignes": obligations}, pondere,
            "fraction de variation du capital par point de taux", "Σ poids × sensibilite_taux de chaque FNB obligataire",
            ["sensibilite_taux (tools/macro.py)", "data/base/series.csv"], "calcul sur des chiffres de tools/"))
        oid = j.enregistrer(cle("oblig", ident), _ref(
            "agents.limites.part_classe", {"portefeuille": ident, "classe": "etf_bond"}, part_oblig, "fraction du capital",
            "Σ poids des FNB obligataires", ["data/assets_universe.csv"], "calcul sur les poids décidés"))
        detail = ", ".join(f"{x} {{{sens[x]}}}" for x in obligations)
        sortie.append(_limite(
            "taux",
            f"Les obligations ({', '.join(obligations)}) font {{{oid}}} du capital. Quand le taux de référence a monté "
            f"d'un point sur la fenêtre, leur prix a varié d'environ : {detail}. Pour le portefeuille : {{{sid}}}.",
            obligations, [oid, sid, *sens.values()], profil, 1 + part_oblig))

    # 4. Durée de la pire baisse face à l'horizon.
    contrib = min(poids, key=lambda x: poids[x] * j.chiffres[mesures[x]["pb"]]["valeur"])
    retour = "jusqu'au retour au sommet" if m["retour"] else "sans retour au sommet à la fin de la fenêtre"
    sortie.append(_limite(
        "duree_pire_baisse",
        f"La pire baisse du portefeuille ({{{m['stats']['pire_baisse']}}}) a duré {{{m['duree']}}} an(s) {retour}, "
        f"pour un horizon de {profil.horizon_annees} an(s). La ligne qui y contribue le plus : {nom(contrib)}, "
        f"pire baisse {{{mesures[contrib]['pb']}}}.",
        [contrib], [m["stats"]["pire_baisse"], m["duree"], mesures[contrib]["pb"]], profil,
        1 + m["duree_annees"] / max(profil.horizon_annees, 1)))

    # 5. Recoupements : deux FNB qui détiennent les mêmes titres, ou un titre détenu aussi via un FNB.
    sortie += _recoupements(profil, poids, ident, j)

    # 6. Centres d'intérêt que l'univers ne couvre pas.
    for x in interets_non_couverts:
        lid = ids_limites.get("plafond_theme")
        sortie.append(_limite(
            "theme_non_couvert",
            f"« {x['interet']} » n'a aucune ligne : {x['raison']}. Aucune ligne n'occupe la place du thème"
            + (f" (plafond {{{lid}}})." if lid else "."), [], [lid] if lid else [], profil))

    # 7. Donnée manquante pour une ligne précise.
    sortie += _donnees_manquantes(profil, poids, ident, j)

    sortie.sort(key=lambda x: -x["_score"])
    for rang, x in enumerate(sortie, 1):
        x["importance"] = rang
        del x["_score"]
    return sortie


def _recoupements(profil: Profil, poids: dict[str, float], ident: str, j: Journal) -> list[dict[str, Any]]:
    table = univers()
    comp = esg_outils.composition()
    connus = set(esg_outils.fnb_connus())
    fnb = [x for x in poids if table.at[x, "asset_class"] == "etf_equity" and x in connus]
    sortie = []
    for i, a in enumerate(fnb):
        for b in fnb[i + 1:]:
            wa = comp[comp["fnb"] == a].set_index("symbole_detenu")["poids"]
            wb = comp[comp["fnb"] == b].set_index("symbole_detenu")["poids"]
            communs = wa.index.intersection(wb.index)
            recoup = float(sum(min(wa[c], wb[c]) for c in communs))
            if recoup <= 0:
                continue
            rid = j.enregistrer(cle("recoupement", a, b), _ref(
                "agents.limites.recoupement_fnb", {"fnb": [a, b]}, recoup, "fraction de l'actif net",
                "Σ sur les titres communs de min(poids dans A, poids dans B)", [esg_outils.FICHIER_FNB],
                "calcul sur la composition publiée des FNB", titres_communs=len(communs)))
            sortie.append(_limite(
                "recoupement_fnb",
                f"{a} et {b} détiennent en partie les mêmes titres : {{{rid}}} de leur actif se recoupe. "
                "Les deux lignes diversifient moins que leur nombre ne le laisse croire.",
                [a, b], [rid], profil, 1 + recoup))
    for s in [x for x in poids if table.at[x, "asset_class"] == "equity"]:
        res = esg_outils.exposition_titre(poids, s)
        via = sum(res["details"]["a_travers_les_fnb"].values())
        if via <= 1e-9:
            continue
        tid = j.enregistrer(cle("titre", ident, s), {**{k: res[k] for k in (
            "outil", "parametres", "periode", "unite", "formule", "sources", "details")}, "valeur": res["valeur"]})
        pid = cle("poids", ident, s)
        sortie.append(_limite(
            "recoupement_fnb",
            f"{s} est détenu en direct ({{{pid}}}) et aussi à travers "
            f"{', '.join(res['details']['a_travers_les_fnb'])} : exposition réelle {{{tid}}} du capital.",
            [s, *res["details"]["a_travers_les_fnb"]], [pid, tid], profil, 1 + res["valeur"]))
    return sortie


def _donnees_manquantes(profil: Profil, poids: dict[str, float], ident: str, j: Journal) -> list[dict[str, Any]]:
    table = univers()
    sortie = []
    connus = set(esg_outils.fnb_connus())
    comp = esg_outils.composition()
    for s in sorted(poids, key=lambda x: -poids[x]):
        classe = table.at[s, "asset_class"]
        pid = cle("poids", ident, s)
        manque = []
        if classe == "equity":
            f = esg_outils.fiche_esg(s)
            if f["statut"] != "connu" or f.get("controverse") == "inconnu":
                manque.append("controverse inconnue dans data/esg_actions.csv")
            manque.append("fondamentaux (bénéfices, dette, dividendes) : data/fondamentaux.csv absent")
        elif classe == "etf_equity":
            if s not in connus:
                manque.append("composition absente de data/fnb_composition.csv")
            else:
                dates = comp[comp["fnb"] == s]["date"]
                partielle = s == "ESGV"  # composition relevée pour les titres de l'univers seulement
                if partielle:
                    manque.append(f"composition connue seulement pour nos titres, au {dates.max()}")
        if manque and pid in j.chiffres:
            sortie.append(_limite(
                "donnee_manquante", f"{s} ({{{pid}}} du capital) : information manquante, " + " ; ".join(manque) + ".",
                [s], [pid], profil, 1 + poids[s]))
    return sortie


def hypotheses_specifiques(profil: Profil, poids: dict[str, float], ident: str, j: Journal,
                           ids_limites: dict[str, str], c: dict[str, Any]) -> list[dict[str, Any]]:
    table = univers()
    devise = "CAD" if profil.devise == "CAD" else "cotation"
    m = mesures_portefeuille(j, ident, poids, devise)
    vol, pb = m["stats"]["volatilite"], m["stats"]["pire_baisse"]
    per = m["periode"]
    sortie = []

    # Fenêtre de cinq ans : ce que donneraient les deux dernières années seules.
    fin = date.fromisoformat(per["fin"])
    debut_recent = fin.replace(year=fin.year - ANNEES_FENETRE_RECENTE).isoformat()
    rec = j.mesurer("stats_portefeuille", cle("ptf", ident, "recent"), poids=poids, devise=devise, debut=debut_recent)
    sortie.append({
        "type": "fenetre", "lignes": list(poids),
        "texte": f"Les chiffres décrivent la fenêtre du {per['debut']} au {per['fin']} : volatilité {{{vol}}}, "
                 f"pire baisse {{{pb}}}.",
        "si_elle_tombe": f"Sur les deux dernières années seules, la volatilité serait {{{rec['volatilite']}}} et la pire "
                         f"baisse {{{rec['pire_baisse']}}} : une autre période donne d'autres chiffres.",
        "chiffres": [vol, pb, rec["volatilite"], rec["pire_baisse"]]})

    # Corrélations supposées stables : la volatilité si toutes les lignes bougeaient ensemble.
    sans = j.enregistrer(cle("ptf", ident, "vol_sans_diversification"), {
        **{k: j.chiffres[vol][k] for k in ("outil", "parametres", "periode", "sources")},
        "valeur": m["details"]["volatilite_sans_diversification"], "unite": "fraction annualisée",
        "champ": "volatilite_sans_diversification", "formule": "Σ wᵢ σᵢ (toutes les corrélations à 1)",
        "details": {"nature": "fait mesuré"}})
    parts = sorted(m["parts"], key=lambda s: -j.chiffres[m["parts"][s]]["valeur"])[:2]
    corr = None
    if len(parts) == 2:
        corr = j.mesurer("correlations", cle("corr", *parts), symboles=parts)["valeur"]
    sortie.append({
        "type": "correlations", "lignes": parts,
        "texte": "Les corrélations mesurées sur la fenêtre sont supposées stables"
                 + (f" (par exemple {parts[0]} et {parts[1]} : {{{corr}}})." if corr else "."),
        "si_elle_tombe": f"Si toutes les lignes bougeaient ensemble (corrélations à un), la volatilité passerait "
                         f"de {{{vol}}} à {{{sans}}}.",
        "chiffres": [x for x in (corr, vol, sans) if x]})

    # Conversion en dollars canadiens.
    usd = [x for x in poids if table.at[x, "currency"] == "USD"]
    if usd and profil.devise == "CAD":
        cot = j.mesurer("stats_portefeuille", cle("ptf", ident, "cotation"), poids=poids, devise="cotation")
        sortie.append({
            "type": "conversion_cad", "lignes": usd,
            "texte": f"Les lignes cotées en dollars américains ({', '.join(usd)}) sont converties en dollars canadiens "
                     "au taux de la Banque du Canada, jour par jour.",
            "si_elle_tombe": f"Sans conversion, chaque actif dans sa devise de cotation, la volatilité serait "
                             f"{{{cot['volatilite']}}} au lieu de {{{vol}}}.",
            "chiffres": [cot["volatilite"], vol]})

    # Plafonds de l'équipe : les lignes qui sont au plafond.
    lim = c["limites"]
    au_plafond = [s for s, w in poids.items() if table.at[s, "asset_class"] == "equity"
                  and abs(w - lim["max_titre_individuel"]) < 1e-6]
    risquee = sum(w for s, w in poids.items() if table.at[s, "asset_class"] in ("equity", "etf_equity", "crypto"))
    lid_titre, lid_risque = ids_limites.get("max_titre_individuel"), ids_limites.get("max_part_risquee")
    if au_plafond and lid_titre:
        texte = (f"Le plafond par titre de l'équipe ({{{lid_titre}}}) fixe le poids de {', '.join(au_plafond)} : "
                 "c'est une hypothèse de conception, pas une mesure de marché.")
        chiffres, lignes = [lid_titre], au_plafond
    else:
        rid = cle("risquee", ident)
        if rid not in j.chiffres:
            j.enregistrer(rid, _ref("agents.adequation.part_risquee", {"portefeuille": ident}, risquee,
                                    "fraction du capital", "Σ poids des actions, FNB d'actions et cryptoactifs",
                                    ["data/assets_universe.csv (asset_class)"], "calcul sur les poids décidés"))
        texte = (f"La part risquée du portefeuille ({{{rid}}}) est bornée par le plafond de l'équipe ({{{lid_risque}}}) : "
                 "une hypothèse de conception, pas une mesure de marché.")
        chiffres, lignes = [x for x in (rid, lid_risque) if x], []
    sortie.append({"type": "plafonds", "lignes": lignes, "texte": texte,
                   "si_elle_tombe": "Avec d'autres plafonds, le constructeur aurait proposé d'autres poids ; "
                                    f"la gouvernance contrôle ceux du profil (tolérance « {profil.tolerance_risque} », "
                                    f"horizon {profil.horizon_annees} an(s)).", "chiffres": chiffres})
    return sortie
