import json
import sys

import pytest

from tools import verifier_cles


@pytest.fixture
def sans_cles(monkeypatch):
    for nom in verifier_cles.CLES:
        monkeypatch.delenv(nom, raising=False)


def test_env_absent(tmp_path, monkeypatch, sans_cles):
    monkeypatch.setattr(verifier_cles, "RACINE", tmp_path)
    ok, message = verifier_cles.verifier_env()
    assert not ok and ".env.example" in message and "environnement cloud" in message


def test_env_sans_fichier_mais_variables_presentes(tmp_path, monkeypatch):
    """Cas d'une session cloud : pas de fichier .env, les clés sont dans l'environnement."""
    monkeypatch.setattr(verifier_cles, "RACINE", tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "cle-fred-secrete")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    ok, message = verifier_cles.verifier_env()
    assert ok and "variables d'environnement" in message and "secrete" not in message


def test_env_avec_une_cle_vide(tmp_path, monkeypatch, sans_cles):
    (tmp_path / ".env").write_text("FRED_API_KEY=abc\nAWS_BEARER_TOKEN_BEDROCK=\n", encoding="utf-8")
    monkeypatch.setattr(verifier_cles, "RACINE", tmp_path)
    monkeypatch.setattr(verifier_cles, "charger_env", lambda: None)
    monkeypatch.setenv("FRED_API_KEY", "abc")
    ok, message = verifier_cles.verifier_env()
    assert not ok and "AWS_BEARER_TOKEN_BEDROCK" in message and "abc" not in message


def test_masquer_retire_les_cles(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "cle-fred-secrete")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    message = verifier_cles.masquer("erreur sur ...api_key=cle-fred-secrete et Bearer cle-bedrock-secrete")
    assert "secrete" not in message and message.count("***") == 2


def test_fred_ok_avec_dates_de_publication(monkeypatch):
    def telecharger(url):
        if "output_type=4" in url:
            obs = [{"date": "2026-11-10", "realtime_start": "2026-11-12", "value": "0"}]
        else:
            obs = [{"date": "2026-11-10", "value": "4.1"}, {"date": "2026-11-11", "value": "."}]
        return json.dumps({"observations": obs}).encode()

    monkeypatch.setenv("FRED_API_KEY", "cle-fred-secrete")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    ok, message = verifier_cles.verifier_fred()
    assert ok and "1 observations" in message and "oui" in message


def test_fred_cle_refusee_sans_fuite(monkeypatch):
    def telecharger(url):
        raise OSError(f"HTTP 400 pour {url}")

    monkeypatch.setenv("FRED_API_KEY", "cle-fred-secrete")
    monkeypatch.setattr("tools.ingestion._telecharger", telecharger)
    ok, message = verifier_cles.verifier_fred()
    assert not ok and "HTTP 400" in message and "cle-fred-secrete" not in message


def test_bedrock_sans_strands(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    monkeypatch.setitem(sys.modules, "strands", None)  # simule un paquet non installé
    ok, message = verifier_cles.verifier_bedrock()
    assert not ok and "pip install strands-agents" in message


def _faux_strands(monkeypatch, reponse=None, erreur=None):
    """Remplace le paquet strands : l'agent appelle l'outil puis renvoie `reponse`."""
    import types

    appels = []

    class Agent:
        def __init__(self, tools, model=None):
            self.tools, self.model = tools, model

        def __call__(self, question):
            if erreur:
                raise erreur
            appels.append(json.loads(self.tools[0]("NVDA")))
            return reponse

    module = types.SimpleNamespace(Agent=Agent, tool=lambda f: f)
    monkeypatch.setitem(sys.modules, "strands", module)
    return appels


def test_bedrock_ok_quand_le_chiffre_de_l_outil_est_dans_la_reponse(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    appels = _faux_strands(monkeypatch, reponse="La volatilité annualisée de NVDA est de 51,9 % (2021-2026).")
    ok, message = verifier_cles.verifier_bedrock()
    assert ok and "51,9 %" in message
    assert appels[0]["outil"] == "volatilite" and round(appels[0]["valeur"] * 100, 1) == 51.9


def test_bedrock_reponse_sans_le_bon_chiffre(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    _faux_strands(monkeypatch, reponse="Environ 40 %.")
    ok, message = verifier_cles.verifier_bedrock()
    assert not ok and "51.9" in message


def test_bedrock_erreur_exacte_sans_fuite(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    _faux_strands(monkeypatch, erreur=RuntimeError("AccessDenied pour le jeton cle-bedrock-secrete"))
    ok, message = verifier_cles.verifier_bedrock()
    assert not ok and "AccessDenied" in message and "cle-bedrock-secrete" not in message
