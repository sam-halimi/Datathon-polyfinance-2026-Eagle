import os

import pytest

from tools import bedrock


@pytest.fixture
def sans_cles(monkeypatch):
    for nom in ((bedrock.VARIABLE_JETON, "BEDROCK_AUTH", "BEDROCK_REGION") + bedrock.VARIABLES_PROXY
                + bedrock.VARIABLES_IDENTIFIANTS):
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
    with pytest.raises(RuntimeError, match="aucun proxy"):
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


def test_identifiants_aws_passent_avant_le_proxy(monkeypatch, sans_cles):
    """Rôle temporaire (atelier AWS) : boto3 signe lui-même, aucun jeton factice n'est posé."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.local:3128")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-exemple")
    assert bedrock.mode_bedrock() == "identifiants"
    monkeypatch.setenv(bedrock.VARIABLE_JETON, bedrock.JETON_FACTICE)  # reste d'un passage en mode proxy
    assert bedrock.preparer_bedrock() == "identifiants" and bedrock.VARIABLE_JETON not in os.environ
    monkeypatch.setenv(bedrock.VARIABLE_JETON, "cle-bedrock-secrete")
    assert bedrock.mode_bedrock() == "jeton"  # un vrai jeton passe toujours en premier


def test_bedrock_auth_impose_le_mode(monkeypatch, sans_cles):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-exemple")
    monkeypatch.setenv("BEDROCK_AUTH", "proxy")
    assert bedrock.preparer_bedrock() == "proxy" and os.environ[bedrock.VARIABLE_JETON] == bedrock.JETON_FACTICE


def test_bedrock_region(monkeypatch, sans_cles):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAEXEMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-exemple")
    with bedrock.jeton_temporaire() as mode:
        assert mode == "identifiants" and os.environ["AWS_DEFAULT_REGION"] == "us-west-2"
    assert os.environ["AWS_REGION"] == os.environ["AWS_DEFAULT_REGION"] == "us-east-1"  # remis en état
    bedrock.preparer_bedrock()
    assert os.environ["AWS_REGION"] == os.environ["AWS_DEFAULT_REGION"] == "us-west-2"
