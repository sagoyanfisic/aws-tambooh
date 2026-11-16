import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.bootstrap_access import ACCOUNT, AwsCli, apply_plan, build_plan


@pytest.mark.parametrize(
    ("filename", "deployer"),
    [
        ("template.json", "GitHubDeploymentRole"),
        ("console-access-keys.json", "GitHubDeploymentUser"),
    ],
)
def test_bootstrap_grants_only_the_required_sam_transform(filename, deployer):
    path = Path(__file__).resolve().parents[2] / "infrastructure/bootstrap" / filename
    template = json.loads(path.read_text())
    for identity in ["CloudFormationRole", deployer]:
        policies = template["Resources"][identity]["Properties"]["Policies"]
        statements = [s for p in policies for s in p["PolicyDocument"]["Statement"]]
        grants = [s for s in statements if s.get("Sid") == "UseSamTransform"]
        assert grants == [
            {
                "Sid": "UseSamTransform",
                "Effect": "Allow",
                "Action": "cloudformation:CreateChangeSet",
                "Resource": {
                    "Fn::Sub": (
                        "arn:${AWS::Partition}:cloudformation:${AWS::Region}"
                        ":aws:transform/Serverless-2016-10-31"
                    )
                },
            }
        ]


def test_offline_plan_resolves_aws_owned_transform_not_application_account():
    plan = build_plan("repo:sagoyanfisic/aws-tambooh:environment:dev")
    for role in plan["roles"].values():
        statements = role["Policies"][0]["PolicyDocument"]["Statement"]
        grant = next(s for s in statements if s.get("Sid") == "UseSamTransform")
        assert grant["Resource"] == (
            "arn:aws:cloudformation:us-east-2:aws:transform/Serverless-2016-10-31"
        )


@pytest.mark.parametrize("filename", ["template.json", "console-access-keys.json"])
def test_api_gateway_tag_permissions_cover_the_failed_stage_resource(filename):
    path = Path(__file__).resolve().parents[2] / "infrastructure/bootstrap" / filename
    template = json.loads(path.read_text())
    statements = template["Resources"]["CloudFormationRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"]
    tags = [s for s in statements if "apigateway:TagResource" in s["Action"]]
    assert len(tags) == 1
    assert "apigateway:UntagResource" in tags[0]["Action"]
    assert tags[0]["Effect"] == "Allow"
    assert {"Fn::Sub": "arn:${AWS::Partition}:apigateway:${AWS::Region}::/apis/*"} in tags[0][
        "Resource"
    ]
    assert "*" not in tags[0]["Resource"]


@pytest.mark.parametrize(
    "subject",
    [
        "repo:sagoyanfisic/aws-tambooh:environment:dev",
        "repo:sagoyanfisic@123/aws-tambooh@456:environment:dev",
    ],
)
def test_plan_has_exact_trust_and_separate_roles(subject):
    plan = build_plan(subject)
    github = plan["roles"]["tambooh-dev-github-deploy"]
    trust = github["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"] == subject
    assert (
        trust["Condition"]["StringEquals"]["token.actions.githubusercontent.com:aud"]
        == "sts.amazonaws.com"
    )
    assert trust["Principal"]["Federated"] == plan["provider_arn"]
    assert "${" not in json.dumps(plan)
    assert "AdministratorAccess" not in json.dumps(plan)
    statements = github["Policies"][0]["PolicyDocument"]["Statement"]
    pass_role = next(item for item in statements if item["Action"] == "iam:PassRole")
    assert pass_role["Resource"] == f"arn:aws:iam::{ACCOUNT}:role/tambooh-dev-cloudformation"


@pytest.mark.parametrize(
    "subject",
    [
        "repo:*/aws-tambooh:environment:dev",
        "repo:sagoyanfisic/aws-tambooh:environment:production",
        "repo:other/aws-tambooh:environment:dev",
        "repo:123/456:environment:dev",
    ],
)
def test_subject_cannot_broaden_repository_scope(subject):
    with pytest.raises(ValueError):
        build_plan(subject)


def test_default_profile_is_never_used(monkeypatch):
    run = Mock()
    monkeypatch.setattr("scripts.bootstrap_access.subprocess.run", run)
    with pytest.raises(ValueError, match="default profile"):
        AwsCli()
    with pytest.raises(ValueError, match="default profile"):
        AwsCli(profile="default")
    run.assert_not_called()


def test_wrong_account_stops_before_iam_or_s3(monkeypatch):
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"Account":"111111111111"}'))
    monkeypatch.setattr("scripts.bootstrap_access.subprocess.run", run)
    plan = build_plan("repo:sagoyanfisic/aws-tambooh:environment:dev")
    with pytest.raises(ValueError, match="STOP"):
        apply_plan(plan, AwsCli(profile="tambooh-new"))
    assert run.call_count == 1
    command = run.call_args.args[0]
    assert command[command.index("--profile") + 1] == "tambooh-new"
    assert "get-caller-identity" in command
    assert "iam" not in command and "s3api" not in command


def test_profile_cannot_be_shadowed_by_default_account_environment(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "old-account-value")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "old-account-value")
    client = AwsCli(profile="tambooh-new")
    assert "AWS_ACCESS_KEY_ID" not in client.environment
    assert "AWS_SECRET_ACCESS_KEY" not in client.environment
    assert "--profile" in client.prefix
    with pytest.raises(ValueError, match="verified"):
        client.call(["iam", "list-roles"])


def test_bootstrap_reuses_provider_and_updates_only_dedicated_roles():
    class FakeCli:
        def __init__(self):
            self.calls = []

        def verify_account(self):
            self.calls.append(["verified"])

        def call(self, args, missing_ok=False):
            assert self.calls[0] == ["verified"]
            self.calls.append(args)
            if "get-open-id-connect-provider" in args:
                return {"Url": "token.actions.githubusercontent.com", "ClientIDList": []}
            if "get-role" in args:
                return {"Role": {"RoleName": args[-1]}}
            return {}

    cli = FakeCli()
    result = apply_plan(build_plan("repo:sagoyanfisic/aws-tambooh:environment:dev"), cli)
    assert any("add-client-id-to-open-id-connect-provider" in call for call in cli.calls)
    assert not any("create-open-id-connect-provider" in call for call in cli.calls)
    assert not any("delete-role" in call for call in cli.calls)
    changed_roles = {
        call[call.index("--role-name") + 1] for call in cli.calls if "--role-name" in call
    }
    assert changed_roles == {"tambooh-dev-cloudformation", "tambooh-dev-github-deploy"}
    assert result["AWS_ARTIFACTS_BUCKET"] == f"tambooh-dev-artifacts-{ACCOUNT}"
