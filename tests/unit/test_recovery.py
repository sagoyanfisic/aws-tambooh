"""Validate data preservation and deployment arguments without contacting AWS."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_recovery_imports_only_retained_data_with_no_new_compute_resources():
    template = json.loads((ROOT / "infrastructure/recovery/import-retained-data.json").read_text())
    assert "Transform" not in template
    assert set(template["Resources"]) == {"PricesTable", "RawDataBucket"}
    assert "Default" not in template["Parameters"]["RawDataBucketName"]
    for resource in template["Resources"].values():
        assert resource["DeletionPolicy"] == "Retain"
        assert resource["UpdateReplacePolicy"] == "Retain"
        assert resource["Condition"] == "CorrectAccountAndRegion"
    table = template["Resources"]["PricesTable"]["Properties"]
    assert table["TableName"] == {"Fn::Sub": "tambooh-${Environment}-prices"}
    assert table["KeySchema"] == [
        {"AttributeName": "pk", "KeyType": "HASH"},
        {"AttributeName": "sk", "KeyType": "RANGE"},
    ]
    bucket = template["Resources"]["RawDataBucket"]["Properties"]
    assert bucket["BucketName"] == {"Ref": "RawDataBucketName"}
    assert all(bucket["PublicAccessBlockConfiguration"].values())


@pytest.mark.parametrize("bucket", ["", "tambooh-dev-rawdatabucket-example"])
@pytest.mark.parametrize("execute", ["true", "false"])
def test_deploy_preserves_imported_bucket_and_supports_review_only(tmp_path, bucket, execute):
    # This stub replaces SAM entirely: no packaging, SDK calls, or deployment can run.
    stub = tmp_path / "sam"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SAM_STUB_LOG"\n')
    stub.chmod(0o700)
    log = tmp_path / "sam.log"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "SAM_STUB_LOG": str(log),
        "SAM_EXECUTE_CHANGESET": execute,
        "AWS_RAW_DATA_BUCKET_NAME": bucket,
        "AWS_REGION": "us-east-2",
        "AWS_CLOUDFORMATION_ROLE_ARN": (
            "arn:aws:iam::786638967830:role/tambooh-dev-keys-cloudformation"
        ),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "dev"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 3
    deploy = calls[-1]
    assert deploy.startswith("deploy --stack-name tambooh-dev")
    assert "Environment=dev EnableAI=false" in deploy
    assert ("--no-execute-changeset" in deploy) == (execute == "false")
    if bucket:
        assert f"RawDataBucketName={bucket}" in deploy
    else:
        assert "RawDataBucketName" not in deploy
