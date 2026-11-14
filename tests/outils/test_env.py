import os

from tools.env import charger_env


def test_charge_les_cles_sans_ecraser_le_terminal(tmp_path, monkeypatch):
    fichier = tmp_path / ".env"
    fichier.write_text(
        "# commentaire\n"
        "CLE_TEST_A=abc123\n"
        'CLE_TEST_B="avec guillemets"\n'
        "export CLE_TEST_C=xyz\n"
        "CLE_TEST_VIDE=\n"
        "CLE_TEST_DEJA_LA=du_fichier\n"
        "ligne sans signe egal\n",
        encoding="utf-8",
    )
    for nom in ("CLE_TEST_A", "CLE_TEST_B", "CLE_TEST_C", "CLE_TEST_VIDE"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("CLE_TEST_DEJA_LA", "du_terminal")

    charges = charger_env(fichier)

    assert charges == ["CLE_TEST_A", "CLE_TEST_B", "CLE_TEST_C"]
    assert os.environ["CLE_TEST_A"] == "abc123"
    assert os.environ["CLE_TEST_B"] == "avec guillemets"
    assert os.environ["CLE_TEST_C"] == "xyz"
    assert "CLE_TEST_VIDE" not in os.environ
    assert os.environ["CLE_TEST_DEJA_LA"] == "du_terminal"
    for nom in charges:  # ne pas laisser de traces pour les autres tests
        monkeypatch.delenv(nom, raising=False)


def test_sans_fichier_ne_fait_rien(tmp_path):
    assert charger_env(tmp_path / ".env") == []
