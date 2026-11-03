"""Explicit cloud workflow. No command runs at import; account is checked before every write.

Terraform owns Cognito/S3/CloudFront/SQS/Scheduler; Syndicate owns API/Lambda/IAM/DynamoDB.
Generated configuration and deployment state stay under syndicate/.generated (git-ignored).
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
GENERATED = BACKEND / "syndicate" / ".generated"
TF = ROOT / "terraform"


def run(*args: str, cwd: Path = ROOT, capture: bool = False) -> str:
    result = subprocess.run(args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def tf(*args: str, capture: bool = False) -> str:
    return run("terraform", f"-chdir={TF}", *args, capture=capture)


def context() -> tuple[boto3.Session, str, str]:
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-north-1"
    session = boto3.Session(region_name=region)
    account = session.client("sts").get_caller_identity()["Account"]
    return session, account, region


def config() -> dict:
    path = GENERATED / "context.json"
    if not path.exists():
        raise SystemExit("Run make aws-configure first.")
    saved = json.loads(path.read_text())
    _, account, region = context()
    if saved["account"] != account or saved["region"] != region:
        raise SystemExit(
            "AWS identity differs from the configured account/region. Select the correct AWS_PROFILE/AWS_REGION."
        )
    return saved


def outputs() -> dict:
    return {key: value["value"] for key, value in json.loads(tf("output", "-json", capture=True)).items()}


def write_aliases(values: dict) -> None:
    aliases = (BACKEND / "syndicate" / "syndicate_aliases.yml").read_text()
    for key, value in values.items():
        line = f"{key}: {json.dumps(value)}"
        aliases, count = re.subn(
            rf"^{re.escape(key)}:.*$", lambda _, replacement=line: replacement, aliases, flags=re.MULTILINE
        )
        if not count:
            aliases += "\n" + line + "\n"
    (GENERATED / "syndicate_aliases.yml").write_text(aliases)


def configure() -> None:
    _, account, region = context()
    GENERATED.mkdir(parents=True, exist_ok=True)
    data = {
        "account": account,
        "region": region,
        "state_bucket": f"restaurant-terraform-state-{account}-{region}",
        "artifacts_bucket": f"restaurant-artifacts-{account}-{region}",
    }
    existing = GENERATED / "context.json"
    if existing.exists() and json.loads(existing.read_text()) != data:
        raise SystemExit(
            "Existing deployment config belongs to another account/region. Preserve it before configuring another environment."
        )
    existing.write_text(json.dumps(data, indent=2) + "\n")
    # JSON is valid YAML and safely quotes paths with spaces.
    (GENERATED / "syndicate.yml").write_text(
        json.dumps(
            {
                "account_id": account,
                "region": region,
                "project_path": str(BACKEND),
                "deploy_target_bucket": data["artifacts_bucket"],
            },
            indent=2,
        )
        + "\n"
    )
    write_aliases(
        {
            "account_id": account,
            "region": region,
            "images_bucket_name": f"restaurant-backend-dev-images-{account}",
            "profile_images_bucket_name": f"restaurant-backend-dev-profile-images-{account}",
            "restaurant_timezone": os.environ.get("RESTAURANT_TIMEZONE", "Asia/Tbilisi"),
            "email_from": os.environ.get("EMAIL_FROM", ""),
        }
    )
    (TF / "terraform.tfvars").write_text(f'account_id = "{account}"\naws_region = "{region}"\n')
    (TF / "backend.local.hcl").write_text(
        f'bucket = "{data["state_bucket"]}"\nkey = "restaurant/terraform.tfstate"\n'
        f'region = "{region}"\nuse_lockfile = true\nencrypt = true\n'
    )
    print(f"Configured AWS account {account}, region {region}. No resources created.")


def ensure_bucket(session: boto3.Session, name: str, region: str) -> None:
    s3 = session.client("s3")
    try:
        s3.head_bucket(Bucket=name)
    except s3.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        kwargs = {"Bucket": name}
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**kwargs)
    s3.put_public_access_block(
        Bucket=name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_versioning(Bucket=name, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_encryption(
        Bucket=name,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )


def initialize() -> None:
    saved = config()
    print(f"Create infrastructure in account {saved['account']} / {saved['region']}.")
    if input("Type CREATE to continue: ").strip() != "CREATE":
        raise SystemExit("Cancelled before creating resources.")
    session, _, region = context()
    for key in ("state_bucket", "artifacts_bucket"):
        ensure_bucket(session, saved[key], region)
    tf("init", "-backend-config=backend.local.hcl")
    tf("validate")
    tf("apply")


def syndicate(command: str, *options: str) -> None:
    config()
    os.environ["SDCT_CONF"] = str(GENERATED)
    run("syndicate", command, *options, cwd=BACKEND)


def configure_binary_cors(api, api_id: str) -> None:
    """Keep preflight responses textual when the API accepts binary downloads.

    AWS requires CONVERT_TO_TEXT on both OPTIONS integration and response when
    binaryMediaTypes includes */*. Syndicate generates these MOCK methods.
    """
    patch = [{"op": "replace", "path": "/contentHandling", "value": "CONVERT_TO_TEXT"}]
    for page in api.get_paginator("get_resources").paginate(restApiId=api_id, limit=500):
        for resource in page["items"]:
            if "OPTIONS" not in resource.get("resourceMethods", {}):
                continue
            target = {"restApiId": api_id, "resourceId": resource["id"], "httpMethod": "OPTIONS"}
            api.update_integration(**target, patchOperations=patch)
            api.update_integration_response(**target, statusCode="200", patchOperations=patch)
    api.create_deployment(restApiId=api_id, stageName="develop")


def demo_password() -> str:
    password = os.environ.get("DEMO_PASSWORD", "")
    if not password or password == "GreenTasty#2026":
        raise SystemExit(
            "Set a unique DEMO_PASSWORD before AWS deploy/update; the local default is not allowed on AWS."
        )
    return password


def fix_lambda_zips() -> None:
    """Flatten nested lambda_path directories inside built zip archives.

    Syndicate places entry-point files (main.py, routes.py …) at the zip root
    but keeps sub-packages under their ``lambda_path`` prefix, e.g.
    ``lambdas/api_handler/core/``.  The Lambda runtime cannot find them there
    because ``sys.path`` only contains ``/var/task``.  This post-build step
    moves every such sub-package to the zip root so imports work.
    """
    bundles = sorted((GENERATED / "bundles").glob("backend_*"))
    if not bundles:
        return
    latest = bundles[-1]
    src_root = BACKEND / "src"
    for zp in latest.glob("*.zip"):
        _flatten_zip(zp, src_root)


def _flatten_zip(zip_path: Path, src_root: Path) -> None:
    """Re-pack *zip_path* so that nested lambda sub-packages sit at the root."""
    # Derive the lambda_path by inspecting the corresponding lambda_config.
    # E.g. api-handler-1.0.zip → look for lambdas/*/lambda_config.json whose
    # ``name`` matches "api-handler".
    stem = zip_path.stem.rsplit("-", 1)[0]  # "api-handler-1.0" → "api-handler"
    lambda_path: str | None = None
    for cfg in src_root.rglob("lambda_config.json"):
        try:
            data = json.loads(cfg.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("name") == stem and data.get("lambda_path"):
            lambda_path = data["lambda_path"]  # e.g. "lambdas/api_handler"
            break
    if not lambda_path:
        return  # nothing to fix

    prefix = lambda_path.rstrip("/") + "/"  # "lambdas/api_handler/"

    with zipfile.ZipFile(zip_path, "r") as zin:
        names = zin.namelist()
        needs_fix = any(n.startswith(prefix) for n in names)
        if not needs_fix:
            return
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=zip_path.parent)
        os.close(tmp_fd)
        try:
            with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    if info.filename.startswith(prefix):
                        info.filename = info.filename[len(prefix) :]
                        if not info.filename:
                            continue  # skip the directory entry itself
                    zout.writestr(info, data)
            Path(tmp_path).replace(zip_path)
            print(f"  Fixed zip structure: {zip_path.name} (flattened {prefix})")
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise


def deploy(command: str) -> None:
    config()
    demo_password()
    out = outputs()
    path = GENERATED / "syndicate_aliases.yml"
    aliases = path.read_text()
    aliases = re.sub(
        r"^user_pool_id:.*$", f'user_pool_id: "{out["cognito_user_pool_id"]}"', aliases, flags=re.MULTILINE
    )
    aliases = re.sub(
        r"^user_pool_client_id:.*$",
        f'user_pool_client_id: "{out["cognito_user_pool_client_id"]}"',
        aliases,
        flags=re.MULTILINE,
    )
    path.write_text(aliases)
    # Lambda Python 3.12 runs on Amazon Linux 2023 x86_64. Never package host macOS/ARM wheels.
    wheel_environment = {
        "PIP_PLATFORM": "manylinux_2_34_x86_64 manylinux_2_28_x86_64 manylinux2014_x86_64",
        "PIP_PYTHON_VERSION": "3.12",
        "PIP_IMPLEMENTATION": "cp",
        "PIP_ABI": "cp312",
        "PIP_ONLY_BINARY": ":all:",
    }
    previous = {key: os.environ.get(key) for key in wheel_environment}
    try:
        os.environ.update(wheel_environment)
        # make aws-deploy/update already runs the isolated backend test suite.
        syndicate("build", "--skip-tests", "--refresh-cache")
    finally:
        # Always restore env even if fix_lambda_zips fails separately.
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    fix_lambda_zips()
    syndicate(command)
    session, _, region = context()
    gateway = session.client("apigateway")
    apis = gateway.get_rest_apis(limit=500)["items"]
    api = next((item for item in apis if item["name"] == "restaurant-backend-api"), None)
    if not api:
        raise SystemExit("Backend deployment did not create the expected API Gateway.")
    configure_binary_cors(gateway, api["id"])
    api_url = f"https://{api['id']}.execute-api.{region}.amazonaws.com/develop"
    seed(api_url=api_url, confirm=False)
    print(f"API_URL={api_url}")


def admin() -> None:
    config()
    session, _, _ = context()
    cognito = session.client("cognito-idp")
    pool = outputs()["cognito_user_pool_id"]
    email = input("First administrator email: ").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Enter a valid email address.")
    password = getpass.getpass("New administrator password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords differ.")
    if not (
        8 <= len(password) <= 16
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
        and re.search(r"[^A-Za-z0-9\s]", password)
    ):
        raise SystemExit("Password needs 8–16 characters, uppercase, lowercase, a number and a symbol.")
    try:
        cognito.admin_create_user(
            UserPoolId=pool,
            Username=email,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "given_name", "Value": "Restaurant"},
                {"Name": "family_name", "Value": "Admin"},
            ],
        )
    except cognito.exceptions.UsernameExistsException:
        raise SystemExit("User already exists. Password and role were not changed.") from None
    cognito.admin_set_user_password(UserPoolId=pool, Username=email, Password=password, Permanent=True)
    for group in ("Admin", "Customer"):
        with contextlib.suppress(cognito.exceptions.GroupExistsException):
            cognito.create_group(UserPoolId=pool, GroupName=group)
        cognito.admin_add_user_to_group(UserPoolId=pool, Username=email, GroupName=group)
    print("Administrator created. Sign in through the website.")


def require_api_url() -> str:
    value = os.environ.get("API_URL", "").rstrip("/")
    if not value.startswith("https://"):
        raise SystemExit("Set API_URL to the https://.../develop URL printed by make aws-deploy.")
    return value


def seed(*, api_url: str | None = None, confirm: bool = True) -> None:
    config()
    demo_password()
    if confirm and input("Create DEMO accounts on AWS? Type DEMO: ").strip() != "DEMO":
        raise SystemExit("Cancelled.")
    _, _, region = context()
    run(
        sys.executable,
        str(BACKEND / "scripts" / "seed.py"),
        "--api-url",
        api_url or require_api_url(),
        "--region",
        region,
        "--user-pool-id",
        outputs()["cognito_user_pool_id"],
        "--demo",
    )


def frontend() -> None:
    config()
    out = outputs()
    os.environ["BACKEND_URL"] = require_api_url()
    os.environ["VITE_RESTAURANT_TIMEZONE"] = os.environ.get("RESTAURANT_TIMEZONE", "Asia/Tbilisi")
    run("npm", "ci", cwd=ROOT / "frontend")
    run("npm", "run", "build", cwd=ROOT / "frontend")
    run("aws", "s3", "sync", str(ROOT / "frontend" / "dist"), f"s3://{out['s3_frontend_bucket_name']}/", "--delete")
    run(
        "aws",
        "cloudfront",
        "create-invalidation",
        "--distribution-id",
        out["cloudfront_distribution_id"],
        "--paths",
        "/*",
    )
    print("Website: https://" + out["cloudfront_distribution_domain_name"])


def destroy() -> None:
    saved = config()
    out = outputs()
    phrase = "DELETE " + saved["account"]
    print("Permanently delete this restaurant's users, reservations, photos and infrastructure.")
    print("Deployment/state buckets are retained for recovery/audit and may incur small storage costs.")
    if input(f"Type {phrase} to confirm: ").strip() != phrase:
        raise SystemExit("Cancelled. No resources were changed.")
    # Clean Syndicate first so Lambda event sources disappear before Terraform deletes their queue.
    syndicate("clean")
    session, _, _ = context()
    s3 = session.resource("s3")
    for key in ("s3_frontend_bucket_name", "s3_images_bucket_name", "s3_profile_images_bucket_name"):
        bucket = s3.Bucket(out[key])
        bucket.object_versions.delete()
        bucket.objects.delete()
    tf("destroy", "-auto-approve")
    print("Application deleted. State and artifact buckets retained:", saved["state_bucket"], saved["artifacts_bucket"])


def main() -> None:
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("configure", "init", "deploy", "update", "admin", "seed", "frontend", "destroy")
    )
    command = parser.parse_args().command
    actions = {
        "configure": configure,
        "init": initialize,
        "admin": admin,
        "seed": seed,
        "frontend": frontend,
        "destroy": destroy,
    }
    if command in ("deploy", "update"):
        deploy(command)
    else:
        actions[command]()


if __name__ == "__main__":
    main()
