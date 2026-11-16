"""Comptes d'Eagle : un identifiant et un mot de passe, gardés par Amazon Cognito.

Eagle ne stocke ni mot de passe ni adresse courriel. Le compte se résume à un identifiant choisi
par la personne (un pseudonyme suffit) : aucune donnée personnelle n'est demandée. Le mot de passe
transite en HTTPS jusqu'à Cognito, qui le conserve haché ; il n'est jamais écrit dans un journal.

Activation : variables `EAGLE_COGNITO_GROUPE` (groupe d'utilisateurs) et `EAGLE_COGNITO_CLIENT`
(client d'application), posées par `deploiement/deployer.py`. Sans elles (serveur local), les comptes
sont inactifs et toutes les routes restent ouvertes, comme avant.

    POST /compte/creer      {"identifiant": "...", "mot_de_passe": "..."}  -> compte créé et connecté
    POST /compte/connexion  {"identifiant": "...", "mot_de_passe": "..."}  -> {"jeton", "expire_dans", "identifiant"}
    GET  /compte            en-tête Authorization: Bearer <jeton>           -> {"identifiant"}

Quand les comptes sont actifs, /analyse, /scenarios et /actif exigent ce jeton : l'analyse, qui
appelle Bedrock, n'est plus ouverte à tous.
"""

from __future__ import annotations

import os
import re
from typing import Any

REGION = "us-east-1"
FORME_IDENTIFIANT = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
REGLE_IDENTIFIANT = "3 à 32 caractères : lettres sans accent, chiffres, point, tiret ou tiret bas"
REGLE_MOT_DE_PASSE = "au moins 8 caractères, dont une minuscule et un chiffre"
ROUTES_PROTEGEES = {("POST", "/analyse"), ("POST", "/scenarios"), ("GET", "/actif")}


class RefusCompte(Exception):
    """Demande de compte refusée, avec le code HTTP à renvoyer (400, 401 ou 409)."""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


def actifs() -> bool:
    return bool(os.environ.get("EAGLE_COGNITO_GROUPE") and os.environ.get("EAGLE_COGNITO_CLIENT"))


def _client() -> Any:
    import boto3

    return boto3.client("cognito-idp", region_name=REGION)


def _lire(corps: dict[str, Any]) -> tuple[str, str]:
    identifiant = str(corps.get("identifiant") or "").strip().lower()
    mot_de_passe = str(corps.get("mot_de_passe") or "")
    if not FORME_IDENTIFIANT.match(identifiant):
        raise RefusCompte(f"Identifiant invalide. Attendu : {REGLE_IDENTIFIANT}.")
    if not mot_de_passe:
        raise RefusCompte("Mot de passe manquant.")
    return identifiant, mot_de_passe


def _code(erreur: Exception) -> str:
    return getattr(erreur, "response", {}).get("Error", {}).get("Code", type(erreur).__name__)


def connecter(corps: dict[str, Any], client: Any = None) -> dict[str, Any]:
    """Vérifie l'identifiant et le mot de passe auprès de Cognito et renvoie un jeton d'accès."""
    identifiant, mot_de_passe = _lire(corps)
    client = client or _client()
    try:
        r = client.admin_initiate_auth(
            UserPoolId=os.environ["EAGLE_COGNITO_GROUPE"], ClientId=os.environ["EAGLE_COGNITO_CLIENT"],
            AuthFlow="ADMIN_USER_PASSWORD_AUTH", AuthParameters={"USERNAME": identifiant, "PASSWORD": mot_de_passe})
    except Exception as e:  # noqa: BLE001 - on traduit les refus de Cognito, le reste remonte
        code = _code(e)
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            # Même phrase dans les deux cas : on ne révèle pas si l'identifiant existe.
            raise RefusCompte("Identifiant ou mot de passe incorrect.", 401) from None
        if code in ("TooManyRequestsException", "LimitExceededException"):
            raise RefusCompte("Trop de tentatives. Réessayez dans quelques minutes.", 429) from None
        raise
    resultat = r["AuthenticationResult"]
    return {"jeton": resultat["AccessToken"], "expire_dans": resultat["ExpiresIn"], "identifiant": identifiant}


def creer(corps: dict[str, Any], client: Any = None) -> dict[str, Any]:
    """Crée le compte dans Cognito, fixe son mot de passe, puis connecte la personne."""
    identifiant, mot_de_passe = _lire(corps)
    client = client or _client()
    groupe = os.environ["EAGLE_COGNITO_GROUPE"]
    try:
        client.admin_create_user(UserPoolId=groupe, Username=identifiant, MessageAction="SUPPRESS")
    except Exception as e:  # noqa: BLE001
        if _code(e) == "UsernameExistsException":
            raise RefusCompte("Cet identifiant est déjà pris. Choisissez-en un autre, ou connectez-vous.", 409) from None
        raise
    try:
        client.admin_set_user_password(UserPoolId=groupe, Username=identifiant, Password=mot_de_passe, Permanent=True)
    except Exception as e:  # noqa: BLE001
        # Mot de passe refusé : le compte à moitié créé est retiré, l'identifiant reste libre.
        client.admin_delete_user(UserPoolId=groupe, Username=identifiant)
        if _code(e) in ("InvalidPasswordException", "InvalidParameterException"):
            raise RefusCompte(f"Mot de passe trop faible. Attendu : {REGLE_MOT_DE_PASSE}.") from None
        raise
    return connecter({"identifiant": identifiant, "mot_de_passe": mot_de_passe}, client)


def identifier(entetes: dict[str, str] | None, client: Any = None) -> str:
    """Identifiant du compte à qui appartient le jeton de l'en-tête Authorization. 401 sinon."""
    valeur = next((v for k, v in (entetes or {}).items() if k.lower() == "authorization"), "")
    jeton = valeur[7:].strip() if valeur.lower().startswith("bearer ") else ""
    if not jeton:
        raise RefusCompte("Connexion requise : connectez-vous ou créez un compte.", 401)
    try:
        return str((client or _client()).get_user(AccessToken=jeton)["Username"])
    except Exception as e:  # noqa: BLE001
        if _code(e) in ("NotAuthorizedException", "UserNotFoundException", "InvalidParameterException"):
            raise RefusCompte("Session expirée : reconnectez-vous.", 401) from None
        raise


def obligatoire() -> bool:
    """Le compte est-il exigé ? Non par défaut : le site propose « Continuer sans compte ».

    Eagle est un outil de démonstration pour le datathon : on peut l'essayer sans s'inscrire.
    `EAGLE_COMPTE_OBLIGATOIRE=1` rétablit l'accès réservé aux personnes connectées."""
    return os.environ.get("EAGLE_COMPTE_OBLIGATOIRE", "").strip() == "1"


def exiger(methode: str, chemin: str, entetes: dict[str, str] | None) -> str | None:
    """Sur une route protégée, quand les comptes sont actifs : vérifie le jeton présenté.

    Sans jeton, la requête passe en invité (None), sauf si le compte est obligatoire. Un jeton
    présenté est toujours vérifié : expiré ou faux, il est refusé (401)."""
    if actifs() and (methode, chemin) in ROUTES_PROTEGEES:
        porte_un_jeton = any(k.lower() == "authorization" and str(v).strip() for k, v in (entetes or {}).items())
        if porte_un_jeton or obligatoire():
            return identifier(entetes)
    return None
