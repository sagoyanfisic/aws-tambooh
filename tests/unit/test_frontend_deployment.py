import json
from unittest.mock import Mock

import pytest

from scripts import deploy_frontend as deploy


def outputs():
    return [
        {"OutputKey": "FrontendBucketName", "OutputValue": "tambooh-dev-frontendbucket-example"},
        {
            "OutputKey": "ApiUrl",
            "OutputValue": "https://example.execute-api.us-east-2.amazonaws.com/dev",
        },
        {"OutputKey": "FrontendDistributionDomain", "OutputValue": "example.cloudfront.net"},
    ]


@pytest.mark.parametrize(
    "key,value",
    [
        ("FrontendBucketName", "tambooh-dev-rawdatabucket-example"),
        ("ApiUrl", "https://example.execute-api.us-east-1.amazonaws.com/dev"),
        ("ApiUrl", "https://example.execute-api.us-east-2.amazonaws.com/prod"),
        ("FrontendDistributionDomain", "untrusted.example.com"),
    ],
)
def test_publisher_refuses_wrong_outputs(key, value):
    values = outputs()
    next(row for row in values if row["OutputKey"] == key)["OutputValue"] = value
    with pytest.raises(ValueError):
        deploy.frontend_targets(values, "dev")


def test_local_default_profile_is_never_used(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    aws = Mock()
    monkeypatch.setattr(deploy, "aws", aws)
    with pytest.raises(ValueError, match="default profiles"):
        deploy.verify_job("dev")
    aws.assert_not_called()


def test_wrong_aws_account_stops_before_any_upload(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    monkeypatch.setenv("DEPLOY_ENV", "dev")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    aws = Mock(return_value=json.dumps({"Account": "111111111111"}))
    monkeypatch.setattr(deploy, "aws", aws)
    with pytest.raises(ValueError, match="another AWS account"):
        deploy.verify_job("dev")
    assert aws.call_count == 1
    assert aws.call_args.args[0][0] == "sts"


def test_publisher_uploads_hashed_assets_before_html_and_never_deletes(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app-example.js").write_text("console.log('test')")
    (tmp_path / "index.html").write_text("<html>test</html>")
    aws = Mock()
    monkeypatch.setattr(deploy, "aws", aws)
    deploy.upload(deploy.frontend_targets(outputs(), "dev"), tmp_path)
    calls = [call.args[0] for call in aws.call_args_list]
    assert calls[0][:2] == ["s3", "sync"]
    assert calls[1][:2] == ["s3", "cp"]
    assert "public,max-age=31536000,immutable" in calls[0]
    assert "no-cache,no-store,must-revalidate" in calls[1]
    assert all("--delete" not in call and "public-read" not in call for call in calls)
    assert all("rawdatabucket" not in str(call) for call in calls)


def test_deployment_policy_allows_only_frontend_namespace_for_publishing():
    from pathlib import Path

    template = json.loads(
        (
            Path(__file__).parents[2] / "infrastructure/bootstrap/console-access-keys.json"
        ).read_text()
    )
    policy = template["Resources"]["GitHubDeploymentUser"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]
    statements = policy["Statement"]
    publish = next(s for s in statements if s["Action"] == "s3:PutObject")
    assert publish["Resource"] == {
        "Fn::Sub": "arn:${AWS::Partition}:s3:::tambooh-${Environment}-frontendbucket-*/*"
    }
    assert len(json.dumps(policy, separators=(",", ":"))) < 2048


def test_public_html_smoke_check_does_not_accept_an_old_page(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"old html"
    get = Mock(return_value=response)
    monkeypatch.setattr(deploy, "urlopen", get)
    pause = Mock()
    monkeypatch.setattr(deploy.time, "sleep", pause)
    with pytest.raises(RuntimeError, match="new HTML was not verified"):
        deploy.smoke_check("https://example.cloudfront.net", b"new html")
    assert get.call_count == 4
    assert pause.call_count == 3


def test_public_html_smoke_check_accepts_exact_uploaded_html(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b"new html"
    get = Mock(return_value=response)
    monkeypatch.setattr(deploy, "urlopen", get)
    deploy.smoke_check("https://example.cloudfront.net", b"new html")
    request = get.call_args.args[0]
    assert request.full_url == "https://example.cloudfront.net/"
    assert "Authorization" not in request.headers
