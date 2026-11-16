"""Comptes (agents/comptes.py) : sans réseau, avec un faux client Cognito."""

import pytest

from agents import comptes, serveur


class ErreurCognito(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FauxCognito:
    """Garde les comptes en mémoire et applique la règle du mot de passe du groupe."""

    def __init__(self):
        self.mots_de_passe: dict[str, str | None] = {}
        self.appels: list[str] = []

    def admin_create_user(self, UserPoolId, Username, MessageAction):
        self.appels.append("creer")
        if Username in self.mots_de_passe:
            raise ErreurCognito("UsernameExistsException")
        self.mots_de_passe[Username] = None

    def admin_set_user_password(self, UserPoolId, Username, Password, Permanent):
        if len(Password) < 8 or Password.isalpha() or Password.upper() == Password:
            raise ErreurCognito("InvalidPasswordException")
        self.mots_de_passe[Username] = Password

    def admin_delete_user(self, UserPoolId, Username):
        self.appels.append("retirer")
        del self.mots_de_passe[Username]

    def admin_initiate_auth(self, UserPoolId, ClientId, AuthFlow, AuthParameters):
        u, p = AuthParameters["USERNAME"], AuthParameters["PASSWORD"]
        if u not in self.mots_de_passe:
            raise ErreurCognito("UserNotFoundException")
        if self.mots_de_passe[u] != p:
            raise ErreurCognito("NotAuthorizedException")
        return {"AuthenticationResult": {"AccessToken": f"jeton-{u}", "ExpiresIn": 28800}}

    def get_user(self, AccessToken):
        u = AccessToken.removeprefix("jeton-")
        if not AccessToken.startswith("jeton-") or u not in self.mots_de_passe:
            raise ErreurCognito("NotAuthorizedException")
        return {"Username": u}


@pytest.fixture
def cognito(monkeypatch):
    faux = FauxCognito()
    monkeypatch.setenv("EAGLE_COGNITO_GROUPE", "us-east-1_test")
    monkeypatch.setenv("EAGLE_COGNITO_CLIENT", "client-test")
    monkeypatch.setattr(comptes, "_client", lambda: faux)
    return faux


def test_sans_reglage_les_comptes_sont_inactifs_et_rien_n_est_exige(monkeypatch):
    monkeypatch.delenv("EAGLE_COGNITO_GROUPE", raising=False)
    monkeypatch.delenv("EAGLE_COGNITO_CLIENT", raising=False)
    assert comptes.actifs() is False
    assert comptes.exiger("POST", "/analyse", {}) is None
    assert serveur.repondre("GET", "/sante", {}, {})["comptes"] is False
    with pytest.raises(serveur.Refus):
        serveur.repondre("POST", "/compte/creer", {}, {"identifiant": "camille", "mot_de_passe": "eagle2026x"})


def test_creer_puis_se_connecter(cognito):
    r = serveur.repondre("POST", "/compte/creer", {}, {"identifiant": " Camille ", "mot_de_passe": "eagle2026x"})
    assert r == {"jeton": "jeton-camille", "expire_dans": 28800, "identifiant": "camille"}
    assert serveur.repondre("POST", "/compte/connexion", {}, {"identifiant": "camille", "mot_de_passe": "eagle2026x"})["jeton"]
    assert serveur.repondre("GET", "/compte", {}, {}, {"Authorization": "Bearer jeton-camille"}) == {"identifiant": "camille"}
    assert serveur.repondre("GET", "/sante", {}, {})["comptes"] is True


def test_identifiant_deja_pris(cognito):
    comptes.creer({"identifiant": "camille", "mot_de_passe": "eagle2026x"})
    with pytest.raises(comptes.RefusCompte) as e:
        comptes.creer({"identifiant": "camille", "mot_de_passe": "autre2026x"})
    assert e.value.code == 409 and "déjà pris" in str(e.value)


def test_mot_de_passe_trop_faible_ne_laisse_pas_de_compte(cognito):
    with pytest.raises(comptes.RefusCompte) as e:
        comptes.creer({"identifiant": "camille", "mot_de_passe": "court"})
    assert e.value.code == 400 and comptes.REGLE_MOT_DE_PASSE in str(e.value)
    assert "camille" not in cognito.mots_de_passe and cognito.appels == ["creer", "retirer"]


@pytest.mark.parametrize("identifiant", ["", "ab", "avec espace", "é-accent", "-debut", "x" * 33, "a@b.c"])
def test_identifiant_invalide(cognito, identifiant):
    with pytest.raises(comptes.RefusCompte):
        comptes.creer({"identifiant": identifiant, "mot_de_passe": "eagle2026x"})
    assert not cognito.appels


def test_mauvais_mot_de_passe_et_compte_inconnu_donnent_la_meme_phrase(cognito):
    comptes.creer({"identifiant": "camille", "mot_de_passe": "eagle2026x"})
    phrases = set()
    for corps in ({"identifiant": "camille", "mot_de_passe": "faux2026xx"}, {"identifiant": "inconnu", "mot_de_passe": "eagle2026x"}):
        with pytest.raises(comptes.RefusCompte) as e:
            comptes.connecter(corps)
        assert e.value.code == 401
        phrases.add(str(e.value))
    assert len(phrases) == 1


@pytest.mark.parametrize("methode,chemin", sorted(comptes.ROUTES_PROTEGEES))
def test_sans_jeton_la_requete_passe_en_invite(cognito, monkeypatch, methode, chemin):
    """« Continuer sans compte » : pas de jeton, pas de refus de compte (la requête échoue ensuite sur son corps vide)."""
    monkeypatch.delenv("EAGLE_COMPTE_OBLIGATOIRE", raising=False)
    assert comptes.exiger(methode, chemin, {}) is None
    with pytest.raises(serveur.Refus):
        serveur.repondre(methode, chemin, {}, {}, {})


@pytest.mark.parametrize("methode,chemin", sorted(comptes.ROUTES_PROTEGEES))
def test_un_jeton_presente_est_toujours_verifie(cognito, monkeypatch, methode, chemin):
    monkeypatch.delenv("EAGLE_COMPTE_OBLIGATOIRE", raising=False)
    comptes.creer({"identifiant": "camille", "mot_de_passe": "eagle2026x"})
    for entetes in ({"Authorization": "Bearer faux"}, {"Authorization": "jeton-camille"}):
        with pytest.raises(comptes.RefusCompte) as e:
            serveur.repondre(methode, chemin, {}, {}, entetes)
        assert e.value.code == 401


@pytest.mark.parametrize("methode,chemin", sorted(comptes.ROUTES_PROTEGEES))
def test_compte_obligatoire_si_on_le_regle(cognito, monkeypatch, methode, chemin):
    monkeypatch.setenv("EAGLE_COMPTE_OBLIGATOIRE", "1")
    comptes.creer({"identifiant": "camille", "mot_de_passe": "eagle2026x"})
    for entetes in ({}, {"Authorization": "Bearer faux"}, {"Authorization": "jeton-camille"}):
        with pytest.raises(comptes.RefusCompte) as e:
            serveur.repondre(methode, chemin, {}, {}, entetes)
        assert e.value.code == 401
    # Avec un jeton valide, la requête passe le contrôle : elle échoue ensuite pour une autre raison (corps vide).
    with pytest.raises(serveur.Refus):
        serveur.repondre(methode, chemin, {}, {}, {"authorization": "Bearer jeton-camille"})


def test_sante_et_demonstration_restent_ouvertes(cognito):
    assert serveur.repondre("GET", "/sante", {}, {})["ok"] is True
    assert serveur.repondre("GET", "/demonstration/robert", {}, {})["portefeuilles"]


def test_panne_passagere_donne_503_et_une_phrase_claire():
    code, phrase = serveur.phrase_d_echec(Exception("serviceUnavailableException: Bedrock is unable to process your request."), "ici")
    assert code == 503 and "momentanément indisponible" in phrase and "relancez" in phrase
    code, phrase = serveur.phrase_d_echec(KeyError("x"), "dans les journaux")
    assert code == 500 and "KeyError" in phrase
