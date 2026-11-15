import os

import pytest

from tools import bedrock


@pytest.fixture
def sans_cles(monkeypatch):
    for nom in (bedrock.VARIABLE_JETON,) + bedrock.VARIABLES_PROXY + bedrock.VARIABLES_IAM:
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setattr(bedrock, "charger_env", lambda: [])  # ne pas lire le .env de la machine


def test_mode(monkeypatch, sans_cles):
    assert bedrock.mode_bedrock() is None
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    assert bedrock.mode_bedrock() == "proxy"
    monkeypatch.setenv(bedrock.VARIABLE_JETON, "cle-bedrock-secrete")
    assert bedrock.mode_bedrock() == "jeton"


def test_le_jeton_factice_reste_en_mode_proxy(monkeypatch, sans_cles):
    monkeypatch.setenv(bedrock.VARIABLE_JETON, bedrock.JETON_FACTICE)
    assert bedrock.mode_bedrock() == "proxy"


def test_preparer_en_mode_proxy_pose_le_jeton_factice(monkeypatch, sans_cles):
    monkeypatch.setenv("https_proxy", "http://proxy.local:3128")
    assert bedrock.preparer_bedrock() == "proxy"
    assert os.environ[bedrock.VARIABLE_JETON] == bedrock.JETON_FACTICE
    assert bedrock.preparer_bedrock() == "proxy"  # un second appel ne change rien


def test_preparer_ne_remplace_pas_un_vrai_jeton(monkeypatch, sans_cles):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv(bedrock.VARIABLE_JETON, "cle-bedrock-secrete")
    assert bedrock.preparer_bedrock() == "jeton"
    assert os.environ[bedrock.VARIABLE_JETON] == "cle-bedrock-secrete"


def test_preparer_sans_jeton_ni_proxy(sans_cles):
    with pytest.raises(RuntimeError, match="Aucune authentification Bedrock"):
        bedrock.preparer_bedrock()


def test_jeton_temporaire_remet_l_environnement(monkeypatch, sans_cles):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    with pytest.raises(ValueError):
        with bedrock.jeton_temporaire() as mode:
            assert mode == "proxy" and os.environ[bedrock.VARIABLE_JETON] == bedrock.JETON_FACTICE
            raise ValueError
    assert bedrock.VARIABLE_JETON not in os.environ


def test_jeton_temporaire_sans_rien(sans_cles):
    with bedrock.jeton_temporaire() as mode:
        assert mode is None and bedrock.VARIABLE_JETON not in os.environ


def test_aide_proxy_cite_l_hote(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    assert "bedrock-runtime.us-west-2.amazonaws.com" in bedrock.aide_proxy()


def test_identifiants_aws_prioritaires_et_jeton_retire(monkeypatch, sans_cles):
    """Les identifiants AWS de l'environnement cloud passent avant tout jeton, qui est retiré."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv(bedrock.VARIABLE_JETON, "ancien-jeton")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-exemple")
    assert bedrock.mode_bedrock() == "iam"
    assert bedrock.preparer_bedrock() == "iam"
    assert bedrock.VARIABLE_JETON not in os.environ


def test_jeton_temporaire_en_mode_iam(monkeypatch, sans_cles):
    monkeypatch.setenv(bedrock.VARIABLE_JETON, "ancien-jeton")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-exemple")
    with bedrock.jeton_temporaire() as mode:
        assert mode == "iam" and bedrock.VARIABLE_JETON not in os.environ
    assert os.environ[bedrock.VARIABLE_JETON] == "ancien-jeton"


def test_un_seul_identifiant_ne_suffit_pas(monkeypatch, sans_cles):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    assert bedrock.mode_bedrock() is None
