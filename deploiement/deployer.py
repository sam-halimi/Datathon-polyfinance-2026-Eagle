"""Déploiement d'Eagle sur AWS (us-east-1), relançable sans rien dupliquer.

    python -m deploiement.deployer api     # API : agents/serveur.py sur Lambda, adresse de fonction HTTPS
    python -m deploiement.deployer site    # site : export statique Next.js, S3 + CloudFront (HTTPS)
    python -m deploiement.deployer tout

- API : la fonction `eagle-api` (Python 3.13) sert les routes de `agents/serveur.py` par
  `agents/lambda_eagle.py`. Bedrock est appelé avec le rôle IAM de la fonction : aucune clé.
  La concurrence est plafonnée pour limiter le coût d'appels répétés à /analyse.
- Site : `web/` exporté en pages statiques (EAGLE_EXPORT=1), avec NEXT_PUBLIC_API_URL pointant vers
  l'API, déposé dans un compartiment S3 privé et servi par CloudFront (adresse *.cloudfront.net).
  Aucun nom de domaine n'est acheté : Route 53 est exclu du compte de l'atelier.

Identifiants : ceux de l'environnement (AWS_ACCESS_KEY_ID…), rôle de l'atelier. Simulation uniquement.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import boto3
import botocore

REGION = "us-east-1"
RACINE = Path(__file__).resolve().parents[1]
CONSTRUCTION = RACINE / "deploiement" / "construction"
FONCTION = "eagle-api"
ROLE = "eagle-lambda"
CONCURRENCE_MAX = 5
DEPENDANCES = ["strands-agents==1.65.0", "pandas==3.0.5", "numpy==2.5.3"]
POLITIQUE_CACHE_OPTIMISEE = "658327ea-f89d-4fab-a63d-7e88639e58f6"  # politique gérée « CachingOptimized »
COMMENTAIRE_SITE = "eagle-site"
# Agent vocal Eagle (ElevenLabs Agents, docs/agent-elevenlabs.md). Identifiant public, pas une clé :
# il figure dans le code du site. NEXT_PUBLIC_ELEVENLABS_AGENT_ID le remplace si l'agent est recréé.
AGENT_VOCAL = "agent_1201m7gj8np7fmnvcgfq6a5gqt68"
# Le même agent en anglais (option « English » du site) : NEXT_PUBLIC_ELEVENLABS_AGENT_ID_EN le remplace.
AGENT_VOCAL_EN = "agent_7901m7h53m9ze8sv0hv8b3bmy5kn"

# Code et données embarqués dans la fonction.
A_EMBARQUER = ["agents", "tools", "data", "tests/scenarios"]
A_EXCLURE = {"__pycache__", "brut", "depot", "construction", ".pytest_cache"}


def _client(service: str):
    return boto3.client(service, region_name=REGION)


def _compte() -> str:
    return boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


def _dire(message: str) -> None:
    print(f"[déploiement] {message}", flush=True)


# --- API ---------------------------------------------------------------------------------------

def construire_paquet() -> Path:
    """Dépendances (roues Linux x86_64 pour Python 3.13) + code et données, dans un zip."""
    dossier = CONSTRUCTION / "paquet"
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    _dire("installation des dépendances pour Lambda (Python 3.13, x86_64)")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", str(dossier),
                    "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux2014_x86_64",
                    "--implementation", "cp", "--python-version", "3.13", "--only-binary=:all:", *DEPENDANCES],
                   check=True)
    for motif in ("tests", "test", "__pycache__"):
        for d in list(dossier.rglob(motif)):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
    for f in dossier.rglob("*.pyi"):
        f.unlink()
    for nom in A_EMBARQUER:
        source = RACINE / nom
        shutil.copytree(source, dossier / nom, ignore=shutil.ignore_patterns(*A_EXCLURE, "*.pyc", ".env*"))
    archive = CONSTRUCTION / "eagle-api.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(dossier.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(dossier))
    taille = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())
    _dire(f"paquet : {archive.stat().st_size / 1e6:.0f} Mo compressé, {taille / 1e6:.0f} Mo décompressé (limite 250)")
    return archive


def _compartiment(nom: str) -> None:
    s3 = _client("s3")
    try:
        s3.head_bucket(Bucket=nom)
    except botocore.exceptions.ClientError:
        s3.create_bucket(Bucket=nom)
        s3.put_public_access_block(Bucket=nom, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
        _dire(f"compartiment S3 créé : {nom}")


def _role(arn_comptes: str | None = None, seau_progression: str | None = None) -> str:
    iam = boto3.client("iam")
    confiance = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole",
                                                          "Principal": {"Service": "lambda.amazonaws.com"}}]}
    try:
        arn = iam.get_role(RoleName=ROLE)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(confiance),
                              Description="Eagle : fonction Lambda de l'API, appels Bedrock")["Role"]["Arn"]
        _dire(f"rôle IAM créé : {ROLE}")
        time.sleep(10)  # le temps que le rôle soit visible par Lambda
    iam.attach_role_policy(RoleName=ROLE, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    iam.put_role_policy(RoleName=ROLE, PolicyName="eagle-bedrock", PolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Resource": "*", "Action": [
            "bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse",
            "bedrock:ConverseStream"]}]}))
    if arn_comptes:
        # Comptes : créer, fixer le mot de passe, connecter, retirer un compte à moitié créé. Rien d'autre.
        iam.put_role_policy(RoleName=ROLE, PolicyName="eagle-comptes", PolicyDocument=json.dumps({
            "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Resource": arn_comptes, "Action": [
                "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword", "cognito-idp:AdminInitiateAuth",
                "cognito-idp:AdminDeleteUser"]}]}))
    if seau_progression:
        # Écran d'attente : la fonction écrit et relit l'avancement d'une analyse (agents/progression.py),
        # dans le seul préfixe progression/ du compartiment de déploiement.
        iam.put_role_policy(RoleName=ROLE, PolicyName="eagle-progression", PolicyDocument=json.dumps({
            "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"],
                                                    "Resource": f"arn:aws:s3:::{seau_progression}/progression/*"}]}))
    return arn


GROUPE_COMPTES = "eagle-comptes"
CLIENT_COMPTES = "eagle-site"


def _comptes() -> tuple[str, str, str]:
    """Groupe d'utilisateurs Cognito des comptes Eagle et son client : (identifiant, ARN, client).

    Identifiant et mot de passe seulement : aucune adresse courriel, aucun message envoyé. Les comptes
    sont créés par l'API (agents/comptes.py), pas en libre-service auprès de Cognito."""
    cog = _client("cognito-idp")
    groupe = next((g["Id"] for page in cog.get_paginator("list_user_pools").paginate(MaxResults=60)
                   for g in page["UserPools"] if g["Name"] == GROUPE_COMPTES), None)
    if groupe is None:
        groupe = cog.create_user_pool(
            PoolName=GROUPE_COMPTES,
            Policies={"PasswordPolicy": {"MinimumLength": 8, "RequireLowercase": True, "RequireNumbers": True,
                                         "RequireUppercase": False, "RequireSymbols": False}},
            UsernameConfiguration={"CaseSensitive": False},
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
        )["UserPool"]["Id"]
        _dire(f"groupe d'utilisateurs Cognito créé : {GROUPE_COMPTES}")
    arn = cog.describe_user_pool(UserPoolId=groupe)["UserPool"]["Arn"]
    client = next((c["ClientId"] for page in cog.get_paginator("list_user_pool_clients").paginate(UserPoolId=groupe, MaxResults=60)
                   for c in page["UserPoolClients"] if c["ClientName"] == CLIENT_COMPTES), None)
    if client is None:
        client = cog.create_user_pool_client(
            UserPoolId=groupe, ClientName=CLIENT_COMPTES, GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_ADMIN_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            AccessTokenValidity=8, TokenValidityUnits={"AccessToken": "hours"},
        )["UserPoolClient"]["ClientId"]
        _dire(f"client Cognito créé : {CLIENT_COMPTES} (jeton d'accès valable 8 heures)")
    return groupe, arn, client


def deployer_api() -> str:
    compte = _compte()
    archive = construire_paquet()
    compartiment = f"eagle-deploiement-{compte}"
    _compartiment(compartiment)
    cle = f"lambda/eagle-api-{hashlib.sha256(archive.read_bytes()).hexdigest()[:12]}.zip"
    _client("s3").upload_file(str(archive), compartiment, cle)
    groupe, arn_comptes, client_comptes = _comptes()
    arn_role = _role(arn_comptes, compartiment)
    # Les états d'avancement sont de petits fichiers sans valeur après l'analyse : effacés au bout d'un jour.
    _client("s3").put_bucket_lifecycle_configuration(Bucket=compartiment, LifecycleConfiguration={"Rules": [{
        "ID": "eagle-progression", "Status": "Enabled", "Filter": {"Prefix": "progression/"}, "Expiration": {"Days": 1}}]})
    lam = _client("lambda")
    reglages = dict(Runtime="python3.13", Handler="agents.lambda_eagle.gestionnaire", Role=arn_role,
                    Timeout=900, MemorySize=2048,
                    Environment={"Variables": {"BEDROCK_AUTH": "identifiants", "PYTHONUTF8": "1",
                                               "EAGLE_COGNITO_GROUPE": groupe, "EAGLE_COGNITO_CLIENT": client_comptes,
                                               "EAGLE_PROGRESSION_SEAU": compartiment}},
                    Description="Eagle : pipeline d'agents (portefeuilles simulés) et routes de agents/serveur.py")
    try:
        lam.get_function(FunctionName=FONCTION)
        lam.update_function_code(FunctionName=FONCTION, S3Bucket=compartiment, S3Key=cle)
        lam.get_waiter("function_updated_v2").wait(FunctionName=FONCTION)
        lam.update_function_configuration(FunctionName=FONCTION, **reglages)
        _dire("fonction mise à jour")
    except lam.exceptions.ResourceNotFoundException:
        for essai in range(6):  # un rôle tout neuf peut mettre quelques secondes à être accepté
            try:
                lam.create_function(FunctionName=FONCTION, Code={"S3Bucket": compartiment, "S3Key": cle}, **reglages)
                break
            except lam.exceptions.InvalidParameterValueException:
                time.sleep(10)
        _dire("fonction créée")
    lam.get_waiter("function_active_v2").wait(FunctionName=FONCTION)
    lam.get_waiter("function_updated_v2").wait(FunctionName=FONCTION)
    try:
        lam.put_function_concurrency(FunctionName=FONCTION, ReservedConcurrentExecutions=CONCURRENCE_MAX)
    except botocore.exceptions.ClientError as e:
        _dire(f"concurrence non plafonnée ({e.response['Error']['Code']}) : quota du compte trop bas")
    cors = {"AllowOrigins": ["*"], "AllowMethods": ["GET", "POST"], "AllowHeaders": ["content-type", "authorization"], "MaxAge": 3600}
    try:
        url = lam.get_function_url_config(FunctionName=FONCTION)["FunctionUrl"]
        lam.update_function_url_config(FunctionName=FONCTION, AuthType="NONE", Cors=cors)
    except lam.exceptions.ResourceNotFoundException:
        url = lam.create_function_url_config(FunctionName=FONCTION, AuthType="NONE", Cors=cors)["FunctionUrl"]
    for sid, action, extra in (("eagle-url-publique", "lambda:InvokeFunctionUrl", {"FunctionUrlAuthType": "NONE"}),
                               ("eagle-url-invoke", "lambda:InvokeFunction", {"InvokedViaFunctionUrl": True})):
        try:
            lam.add_permission(FunctionName=FONCTION, StatementId=sid, Action=action, Principal="*", **extra)
        except lam.exceptions.ResourceConflictException:
            pass
        except botocore.exceptions.ParamValidationError:
            pass  # boto3 trop ancien pour InvokedViaFunctionUrl
    url = url.rstrip("/")
    (CONSTRUCTION / "api_url.txt").write_text(url + "\n", encoding="utf-8")
    _dire(f"API : {url}")
    return url


# --- Site --------------------------------------------------------------------------------------

def construire_site(url_api: str) -> Path:
    web = RACINE / "web"
    if not (web / "node_modules").exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=web, check=True)
    # Les tables du site (secteur, zone, cours, éventails des démonstrations) sont recalculées
    # depuis data/ et agents/sorties/ : le site déployé ne peut pas être en retard sur les données.
    _dire("tables du site : python web/scripts/graphiques.py")
    subprocess.run([sys.executable, str(web / "scripts" / "graphiques.py")], cwd=RACINE, check=True)
    # NEXT_PUBLIC_COMPTES=1 : l'API déployée exige un compte (agents/comptes.py), le site montre la connexion.
    env = {**os.environ, "EAGLE_EXPORT": "1", "NEXT_PUBLIC_API_URL": url_api, "NEXT_PUBLIC_COMPTES": "1",
           "NEXT_PUBLIC_ELEVENLABS_AGENT_ID": os.environ.get("NEXT_PUBLIC_ELEVENLABS_AGENT_ID") or AGENT_VOCAL,
           "NEXT_PUBLIC_ELEVENLABS_AGENT_ID_EN": os.environ.get("NEXT_PUBLIC_ELEVENLABS_AGENT_ID_EN") or AGENT_VOCAL_EN}
    _dire(f"export statique de web/ (API {url_api}, agent vocal {env['NEXT_PUBLIC_ELEVENLABS_AGENT_ID']})")
    subprocess.run(["npx", "next", "build"], cwd=web, env=env, check=True)
    return web / "out"


FONCTION_INDEX = """function handler(event) {
  var r = event.request;
  if (r.uri.endsWith('/')) { r.uri += 'index.html'; }
  else if (!r.uri.split('/').pop().includes('.')) { r.uri += '/index.html'; }
  return r;
}"""


def _fonction_cloudfront(cf) -> str:
    nom = "eagle-index"
    config = {"Comment": "Eagle : /rapport/ -> /rapport/index.html", "Runtime": "cloudfront-js-2.0"}
    try:
        desc = cf.describe_function(Name=nom, Stage="LIVE")
        return desc["FunctionSummary"]["FunctionMetadata"]["FunctionARN"]
    except cf.exceptions.NoSuchFunctionExists:
        cree = cf.create_function(Name=nom, FunctionConfig=config, FunctionCode=FONCTION_INDEX.encode())
        cf.publish_function(Name=nom, IfMatch=cree["ETag"])
        return cree["FunctionSummary"]["FunctionMetadata"]["FunctionARN"]


def _oac(cf) -> str:
    for oac in cf.list_origin_access_controls().get("OriginAccessControlList", {}).get("Items", []):
        if oac["Name"] == "eagle-site-oac":
            return oac["Id"]
    return cf.create_origin_access_control(OriginAccessControlConfig={
        "Name": "eagle-site-oac", "Description": "Eagle : CloudFront lit le compartiment privé du site",
        "SigningProtocol": "sigv4", "SigningBehavior": "always", "OriginAccessControlOriginType": "s3"})[
        "OriginAccessControl"]["Id"]


def _distribution(cf, compartiment: str) -> dict:
    for d in cf.list_distributions().get("DistributionList", {}).get("Items", []) or []:
        if d.get("Comment") == COMMENTAIRE_SITE:
            return d
    origine = f"{compartiment}.s3.{REGION}.amazonaws.com"
    config = {
        "CallerReference": f"eagle-{int(time.time())}", "Comment": COMMENTAIRE_SITE, "Enabled": True,
        "DefaultRootObject": "index.html", "PriceClass": "PriceClass_100", "HttpVersion": "http2and3",
        "Origins": {"Quantity": 1, "Items": [{
            "Id": "site", "DomainName": origine, "S3OriginConfig": {"OriginAccessIdentity": ""},
            "OriginAccessControlId": _oac(cf)}]},
        "DefaultCacheBehavior": {
            "TargetOriginId": "site", "ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
            "CachePolicyId": POLITIQUE_CACHE_OPTIMISEE,
            "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"],
                               "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
            "FunctionAssociations": {"Quantity": 1, "Items": [
                {"FunctionARN": _fonction_cloudfront(cf), "EventType": "viewer-request"}]}},
        "CustomErrorResponses": {"Quantity": 2, "Items": [
            {"ErrorCode": 403, "ResponsePagePath": "/404.html", "ResponseCode": "404", "ErrorCachingMinTTL": 10},
            {"ErrorCode": 404, "ResponsePagePath": "/404.html", "ResponseCode": "404", "ErrorCachingMinTTL": 10}]},
    }
    d = cf.create_distribution(DistributionConfig=config)["Distribution"]
    _dire("distribution CloudFront créée (mise en service en quelques minutes)")
    return {"Id": d["Id"], "ARN": d["ARN"], "DomainName": d["DomainName"]}


def deployer_site(url_api: str | None = None) -> str:
    compte = _compte()
    url_api = url_api or (CONSTRUCTION / "api_url.txt").read_text(encoding="utf-8").strip()
    sortie = construire_site(url_api)
    compartiment = f"eagle-site-{compte}"
    _compartiment(compartiment)
    s3 = _client("s3")
    fichiers = [f for f in sortie.rglob("*") if f.is_file()]
    for f in fichiers:
        cle = str(f.relative_to(sortie))
        type_, _ = mimetypes.guess_type(cle)
        cache = "public, max-age=31536000, immutable" if cle.startswith("_next/static/") else "public, max-age=60"
        s3.upload_file(str(f), compartiment, cle, ExtraArgs={"ContentType": (type_ or "application/octet-stream")
                                                             + ("; charset=utf-8" if (type_ or "").startswith("text/") else ""),
                                                             "CacheControl": cache})
    _dire(f"{len(fichiers)} fichiers déposés dans s3://{compartiment}")
    cf = boto3.client("cloudfront")
    d = _distribution(cf, compartiment)
    s3.put_bucket_policy(Bucket=compartiment, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "CloudFrontLitLeSite", "Effect": "Allow", "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject", "Resource": f"arn:aws:s3:::{compartiment}/*",
        "Condition": {"StringEquals": {"AWS:SourceArn": d["ARN"]}}}]}))
    cf.create_invalidation(DistributionId=d["Id"], InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": f"eagle-{int(time.time())}"})
    url = f"https://{d['DomainName']}"
    (CONSTRUCTION / "site_url.txt").write_text(url + "\n", encoding="utf-8")
    _dire(f"site : {url}")
    return url


def main(argv: list[str]) -> int:
    quoi = argv[0] if argv else "tout"
    url_api = deployer_api() if quoi in ("api", "tout") else None
    if quoi in ("site", "tout"):
        deployer_site(url_api)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
