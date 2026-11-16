#!/usr/bin/env python3
"""Render or apply TamBooh access in one verified AWS account. Never use a local default profile."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ACCOUNT = "786638967830"
REGION = "us-east-2"
ROOT = Path(__file__).resolve().parents[1]
SUBJECT = re.compile(r"repo:sagoyanfisic(?:@[0-9]+)?/aws-tambooh(?:@[0-9]+)?:environment:dev")


def build_plan(subject):
    if not SUBJECT.fullmatch(subject):
        raise ValueError("Use the exact verified repo subject for environment dev; no wildcards")
    provider = f"arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"
    bucket = f"tambooh-dev-artifacts-{ACCOUNT}"
    roles = {
        "CloudFormationRole": "tambooh-dev-cloudformation",
        "GitHubDeploymentRole": "tambooh-dev-github-deploy",
    }
    values = {
        "AWS::Partition": "aws",
        "AWS::Region": REGION,
        "AWS::AccountId": ACCOUNT,
        "Environment": "dev",
        "GitHubOidcSubject": subject,
        "ArtifactBucket": bucket,
        "ArtifactBucket.Arn": f"arn:aws:s3:::{bucket}",
        "GitHubOidcProvider": provider,
        "ExistingOidcProviderArn": provider,
    }
    for logical, name in roles.items():
        values[logical] = name
        values[f"{logical}.Arn"] = f"arn:aws:iam::{ACCOUNT}:role/{name}"

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "Ref" in value:
            return values[value["Ref"]]
        if "Fn::Sub" in value:
            return re.sub(r"\$\{([^}]+)\}", lambda match: values[match[1]], value["Fn::Sub"])
        if "Fn::GetAtt" in value:
            return values[".".join(value["Fn::GetAtt"])]
        if "Fn::If" in value:
            return resolve(value["Fn::If"][2])
        return {key: resolve(item) for key, item in value.items()}

    template = json.loads((ROOT / "infrastructure/bootstrap/template.json").read_text())
    return {
        "account_id": ACCOUNT,
        "region": REGION,
        "provider_arn": provider,
        "bucket": bucket,
        "subject": subject,
        "roles": {
            name: resolve(template["Resources"][logical]["Properties"])
            for logical, name in roles.items()
        },
    }


class AwsCli:
    def __init__(self, profile=None, cloudshell=False):
        if not profile and not cloudshell:
            raise ValueError("Choose --profile NAME or --cloudshell; default profile is forbidden")
        if profile and cloudshell:
            raise ValueError("Choose a single credential source")
        if profile == "default":
            raise ValueError("The default profile is forbidden")
        if cloudshell and (os.getenv("AWS_PROFILE") or os.getenv("AWS_DEFAULT_PROFILE")):
            raise ValueError("CloudShell mode must not have an AWS profile override")
        self.prefix = ["aws", "--region", REGION, "--no-cli-pager", "--output", "json"]
        if profile:
            self.prefix.extend(["--profile", profile])
        self.environment = os.environ.copy()
        self.environment["AWS_MAX_ATTEMPTS"] = "2"
        self.environment["AWS_EC2_METADATA_DISABLED"] = "true"
        if profile:
            # Explicit profiles must not be shadowed by another account's environment keys.
            for key in (
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
                "AWS_SECURITY_TOKEN",
                "AWS_WEB_IDENTITY_TOKEN_FILE",
                "AWS_ROLE_ARN",
            ):
                self.environment.pop(key, None)
        self.verified = False

    def _call(self, args, missing_ok=False):
        result = subprocess.run(
            self.prefix + args,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode:
            if missing_ok and "NoSuchEntity" in result.stderr:
                return None
            raise RuntimeError(result.stderr.strip() or "AWS CLI failed")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def verify_account(self):
        identity = self._call(["sts", "get-caller-identity", "--output", "json"])
        if identity.get("Account") != ACCOUNT:
            raise ValueError(
                f"STOP: expected account {ACCOUNT}, got {identity.get('Account')}; no changes made"
            )
        self.verified = True

    def call(self, args, missing_ok=False):
        if not self.verified:
            raise ValueError("Account must be verified before IAM/S3 access")
        return self._call(args, missing_ok)


def apply_plan(plan, client):
    client.verify_account()
    provider = client.call(
        [
            "iam",
            "get-open-id-connect-provider",
            "--open-id-connect-provider-arn",
            plan["provider_arn"],
        ],
        missing_ok=True,
    )
    if provider is None:
        client.call(
            [
                "iam",
                "create-open-id-connect-provider",
                "--url",
                "https://token.actions.githubusercontent.com",
                "--client-id-list",
                "sts.amazonaws.com",
            ]
        )
    else:
        if (
            provider.get("Url", "").removeprefix("https://").rstrip("/")
            != "token.actions.githubusercontent.com"
        ):
            raise ValueError("Existing provider has an unexpected issuer")
        if "sts.amazonaws.com" not in provider.get("ClientIDList", []):
            client.call(
                [
                    "iam",
                    "add-client-id-to-open-id-connect-provider",
                    "--open-id-connect-provider-arn",
                    plan["provider_arn"],
                    "--client-id",
                    "sts.amazonaws.com",
                ]
            )
    with tempfile.TemporaryDirectory(prefix="tambooh-bootstrap-") as temp:
        for name, role in plan["roles"].items():
            existing = client.call(["iam", "get-role", "--role-name", name], missing_ok=True)
            trust = Path(temp) / f"{name}-trust.json"
            trust.write_text(json.dumps(role["AssumeRolePolicyDocument"]))
            operation = "update-assume-role-policy" if existing else "create-role"
            client.call(
                [
                    "iam",
                    operation,
                    "--role-name",
                    name,
                    "--assume-role-policy-document",
                    f"file://{trust}",
                ]
            )
            for policy in role["Policies"]:
                policy_file = Path(temp) / f"{name}-policy.json"
                policy_file.write_text(json.dumps(policy["PolicyDocument"]))
                client.call(
                    [
                        "iam",
                        "put-role-policy",
                        "--role-name",
                        name,
                        "--policy-name",
                        policy["PolicyName"],
                        "--policy-document",
                        f"file://{policy_file}",
                    ]
                )
    # The artifact bucket is deliberately separate: operators may already have created it.
    # Do not change or delete an existing bucket or unrelated IAM policy.
    return {
        "AWS_REGION": REGION,
        "AWS_ARTIFACTS_BUCKET": plan["bucket"],
        "AWS_DEPLOY_ROLE_ARN": f"arn:aws:iam::{ACCOUNT}:role/tambooh-dev-github-deploy",
        "AWS_CLOUDFORMATION_ROLE_ARN": f"arn:aws:iam::{ACCOUNT}:role/tambooh-dev-cloudformation",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, help="Exact sub emitted by Inspect OIDC")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply only the two dedicated roles and GitHub provider",
    )
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--profile", help="Explicit AWS CLI profile; never default")
    auth.add_argument(
        "--cloudshell", action="store_true", help="Run only inside target account CloudShell"
    )
    args = parser.parse_args()
    try:
        plan = build_plan(args.subject)
        if not args.apply:
            print(json.dumps(plan, indent=2))
            return 0
        client = AwsCli(args.profile, args.cloudshell)
        print(json.dumps(apply_plan(plan, client), indent=2))
    except (ValueError, RuntimeError, subprocess.SubprocessError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
