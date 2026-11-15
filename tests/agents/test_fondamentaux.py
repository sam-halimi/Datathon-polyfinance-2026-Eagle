"""Fondamentaux : « information manquante » tant que data/fondamentaux.csv n'existe pas, jamais inventés."""

from agents import gouvernance as gv
from agents import lignes
from agents.adequation import evaluer
from agents.journal import Journal
from agents.profil import Profil

POIDS = {"XIU.TO": 0.2, "ESGV": 0.2, "XBB.TO": 0.25, "ZST.TO": 0.15, "GLD": 0.1, "MSFT": 0.05, "RY.TO": 0.05}
PROFIL = Profil(horizon_annees=6, objectif="revenu", tolerance_risque="faible", connaissance_niveau=3,
                preferences=["dividendes"], capital_fictif=400000)


def _adequation():
    j = Journal()
    ids = gv.enregistrer_limites(j, gv.limites_du_profil(PROFIL))
    return {(e["critere"], e["element"]): e for e in evaluer(PROFIL, POIDS, j, "A", ids)}


def test_absent_information_manquante_partout():
    assert not lignes.FICHIER_FONDAMENTAUX.is_file()
    assert lignes.statut_fondamentaux() == "information manquante"
    fd = lignes.fondamentaux("RY.TO")
    assert fd["statut"] == "information manquante" and fd["source_couverture"] == "data/base/couverture.csv"
    sources = lignes.sources_ligne("MSFT", "CAD")
    assert any(s["fichier"] == "data/fondamentaux.csv" and "information manquante" in s["objet"] for s in sources)
    assert not any(s["fichier"] == "data/fondamentaux.csv" for s in lignes.sources_ligne("SPY", "CAD"))  # pas un FNB
    a = _adequation()
    for cle in (("objectif", None), ("preferences", "dividendes")):
        assert a[cle]["statut"] == "non couvert" and "information manquante" in a[cle]["raison"]


def test_un_fichier_qui_apparait_n_est_pas_lu_en_silence(tmp_path, monkeypatch):
    faux = tmp_path / "fondamentaux.csv"
    faux.write_text("ticker,dividende\nRY.TO,0.04\n", encoding="utf-8")
    monkeypatch.setattr(lignes, "FICHIER_FONDAMENTAUX", faux)
    assert lignes.statut_fondamentaux() == "fichier présent, non branché"
    a = _adequation()
    assert a[("objectif", None)]["statut"] == "non couvert" and "non branché" in a[("objectif", None)]["raison"]
