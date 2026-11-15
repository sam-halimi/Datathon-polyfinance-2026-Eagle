import os
import sys
import types

import pytest

from agents import modele
from tools import bedrock


@pytest.fixture
def faux_strands(monkeypatch):
    crees = []

    class Agent:
        def __init__(self, **reglages):
            reglages["jeton_vu"] = os.environ.get(bedrock.VARIABLE_JETON)
            crees.append(reglages)

    monkeypatch.setitem(sys.modules, "strands", types.SimpleNamespace(Agent=Agent))
    monkeypatch.setattr(modele, "_mode", None)
    monkeypatch.setattr(bedrock, "charger_env", lambda: [])
    for nom in (bedrock.VARIABLE_JETON, "BEDROCK_MODEL_ID") + bedrock.VARIABLES_PROXY:
        monkeypatch.delenv(nom, raising=False)
    return crees


def test_creer_agent_demarre_bedrock_par_le_proxy(monkeypatch, faux_strands):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "modele-test")
    modele.creer_agent("gouvernance", "Vérifie.", outils=[print])
    r = faux_strands[0]
    assert r["jeton_vu"] == bedrock.JETON_FACTICE and r["model"] == "modele-test"
    assert r["name"] == "gouvernance" and r["tools"] == [print] and r["callback_handler"] is None


def test_creer_agent_sans_authentification(faux_strands):
    with pytest.raises(RuntimeError):
        modele.creer_agent("gouvernance", "Vérifie.")
    assert not faux_strands


def test_demarrer_une_seule_fois(monkeypatch, faux_strands):
    appels = []
    monkeypatch.setattr(modele, "preparer_bedrock", lambda: appels.append(1) or "proxy")
    modele.creer_agent("a", "x")
    modele.creer_agent("b", "y")
    assert len(appels) == 1 and "model" not in faux_strands[0]
