import json
import sys

import pytest

from tools import verifier_cles


@pytest.fixture
def sans_cles(monkeypatch):
    """Ni clé ni proxy : les tests ne dépendent pas de la machine qui les lance."""
    for nom in verifier_cles.SECRETS + verifier_cles.VARIABLES_PROXY:
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


def test_env_session_cloud_avec_proxy_sans_jeton(tmp_path, monkeypatch, sans_cles):
    """Session cloud : le proxy authentifie Bedrock, seule FRED_API_KEY est exigée."""
    monkeypatch.setattr(verifier_cles, "RACINE", tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "cle-fred-secrete")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    ok, message = verifier_cles.verifier_env()
    assert ok and "proxy" in message and "AWS_BEARER_TOKEN_BEDROCK" not in message and "secrete" not in message


def test_env_proxy_ne_dispense_pas_de_fred(tmp_path, monkeypatch, sans_cles):
    monkeypatch.setattr(verifier_cles, "RACINE", tmp_path)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    ok, message = verifier_cles.verifier_env()
    assert not ok and "FRED_API_KEY" in message and "AWS_BEARER_TOKEN_BEDROCK" not in message


def test_mode_bedrock(monkeypatch, sans_cles):
    assert verifier_cles.mode_bedrock() is None
    monkeypatch.setenv("https_proxy", "http://proxy.local:3128")
    assert verifier_cles.mode_bedrock() == "proxy"
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    assert verifier_cles.mode_bedrock() == "jeton"  # un vrai jeton passe avant le proxy


def test_masquer_retire_les_identifiants_aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIDENTIFIANTSECRET")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "cle-aws-secrete")
    message = verifier_cles.masquer("signature AKIAIDENTIFIANTSECRET/cle-aws-secrete refusée")
    assert "SECRET" not in message and "secrete" not in message and message.count("***") == 2


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
    """Remplace le paquet strands : l'agent appelle l'outil puis renvoie `reponse`.

    Chaque appel note aussi le jeton vu par boto3 au moment de la requête (`jeton_vu`).
    """
    import os
    import types

    appels = []

    class Agent:
        def __init__(self, tools, model=None):
            self.tools, self.model = tools, model

        def __call__(self, question):
            jeton_vu = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            if erreur:
                raise erreur
            appels.append({**json.loads(self.tools[0]("NVDA")), "jeton_vu": jeton_vu})
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


def test_bedrock_sans_jeton_ni_proxy(monkeypatch, sans_cles):
    ok, message = verifier_cles.verifier_bedrock()
    assert not ok and "AWS_BEARER_TOKEN_BEDROCK absente" in message and "proxy" in message


def test_bedrock_par_le_proxy_avec_jeton_factice_le_temps_de_l_appel(monkeypatch, sans_cles):
    """Le proxy ajoute le vrai jeton : boto3 reçoit un jeton factice pendant l'appel, retiré ensuite."""
    import os

    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    appels = _faux_strands(monkeypatch, reponse="La volatilité annualisée de NVDA est de 51,9 % (2021-2026).")
    ok, message = verifier_cles.verifier_bedrock()
    assert ok and "51,9 %" in message and "proxy" in message
    assert appels[0]["jeton_vu"] == verifier_cles.JETON_FACTICE
    assert "AWS_BEARER_TOKEN_BEDROCK" not in os.environ


def test_bedrock_par_le_proxy_erreur_cite_l_hote_attendu(monkeypatch, sans_cles):
    import os

    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    _faux_strands(monkeypatch, erreur=RuntimeError("UnrecognizedClientException"))
    ok, message = verifier_cles.verifier_bedrock()
    assert not ok and "UnrecognizedClientException" in message
    assert "bedrock-runtime.us-west-2.amazonaws.com" in message
    assert "AWS_BEARER_TOKEN_BEDROCK" not in os.environ  # retiré même après une erreur


def test_bedrock_un_vrai_jeton_n_est_pas_remplace(monkeypatch, sans_cles):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "cle-bedrock-secrete")
    appels = _faux_strands(monkeypatch, reponse="51,9 %")
    ok, message = verifier_cles.verifier_bedrock()
    assert ok and appels[0]["jeton_vu"] == "cle-bedrock-secrete" and "secrete" not in message
