"""Exercise the deployment guard with a local AWS CLI stub, never live credentials."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_guard(tmp_path, overrides=None):
    stub = tmp_path / "aws"
    stub.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$AWS_STUB_LOG"\nprintf "%s\\n" "$AWS_STUB_ACCOUNT"\n'
    )
    stub.chmod(0o700)
    log = tmp_path / "calls.log"
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GITHUB_ACTIONS": "true",
        "DEPLOY_ENV": "dev",
        "AWS_ACCESS_KEY_ID": "test-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
        "AWS_REGION": "us-east-2",
        "AWS_CLOUDFORMATION_ROLE_ARN": (
            "arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation"
        ),
        "AWS_STUB_ACCOUNT": "786638967830",
        "AWS_STUB_LOG": str(log),
        **(overrides or {}),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/check-deploy-target.sh")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    assert "test-key" not in result.stdout + result.stderr
    assert "test-secret" not in result.stdout + result.stderr
    return result, calls


def test_target_account_is_checked_read_only(tmp_path):
    result, calls = run_guard(tmp_path)
    assert result.returncode == 0
    assert calls == ["sts get-caller-identity --query Account --output text --region us-east-2"]


def test_credentials_for_another_account_are_refused(tmp_path):
    result, calls = run_guard(tmp_path, {"AWS_STUB_ACCOUNT": "111111111111"})
    assert result.returncode == 1
    assert "different AWS account" in result.stderr
    assert len(calls) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"GITHUB_ACTIONS": ""},
        {"AWS_ACCESS_KEY_ID": ""},
        {"AWS_SECRET_ACCESS_KEY": ""},
        {"AWS_REGION": "us-east-1"},
        {"DEPLOY_ENV": "unknown"},
        {"AWS_CLOUDFORMATION_ROLE_ARN": "arn:aws:iam::111111111111:role/tambooh-dev-role"},
        {"AWS_CLOUDFORMATION_ROLE_ARN": "arn:aws:iam::786638967830:role/tambooh-prod-role"},
    ],
)
def test_invalid_context_stops_before_any_aws_call(tmp_path, overrides):
    result, calls = run_guard(tmp_path, overrides)
    assert result.returncode != 0
    assert calls == []


def test_key_bootstrap_separates_permissions_and_never_generates_a_secret():
    template = json.loads((ROOT / "infrastructure/bootstrap/console-access-keys.json").read_text())
    resources = template["Resources"]
    assert {r["Type"] for r in resources.values()} == {
        "AWS::IAM::User",
        "AWS::IAM::Role",
        "AWS::S3::Bucket",
    }
    user = resources["GitHubDeploymentUser"]["Properties"]
    assert "LoginProfile" not in user
    statements = user["Policies"][0]["PolicyDocument"]["Statement"]
    iam = [s for s in statements if s["Action"] == "iam:PassRole"]
    assert len(iam) == 1
    assert iam[0]["Resource"] == {"Fn::GetAtt": ["CloudFormationRole", "Arn"]}
    assert iam[0]["Condition"]["StringEquals"] == {
        "iam:PassedToService": "cloudformation.amazonaws.com"
    }
    assert resources["CloudFormationRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][
        0
    ]["Principal"] == {"Service": "cloudformation.amazonaws.com"}
    assert template["Conditions"]["CorrectAccountAndRegion"] == {
        "Fn::And": [
            {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "786638967830"]},
            {"Fn::Equals": [{"Ref": "AWS::Region"}, "us-east-2"]},
        ]
    }
    assert "AdministratorAccess" not in json.dumps(template)
    assert "AccessKey" not in json.dumps(template["Outputs"])
