#!/usr/bin/env python3
"""Build and publish the frontend from verified GitHub Actions credentials only."""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-2"
ACCOUNT = "786638967830"


def frontend_targets(outputs, environment):
    if environment not in {"dev", "prod"}:
        raise ValueError("Environment must be dev or prod")
    values = {entry["OutputKey"]: entry["OutputValue"] for entry in outputs}
    bucket = values.get("FrontendBucketName", "")
    api = values.get("ApiUrl", "")
    domain = values.get("FrontendDistributionDomain", "")
    if not re.fullmatch(rf"tambooh-{environment}-frontendbucket-[a-z0-9-]+", bucket):
        raise ValueError("Unexpected frontend bucket; refusing to upload")
    if not re.fullmatch(
        rf"https://[a-z0-9]+\.execute-api\.us-east-2\.amazonaws\.com/{environment}", api
    ):
        raise ValueError("Unexpected API URL or stage")
    if not re.fullmatch(r"[a-z0-9]+\.cloudfront\.net", domain):
        raise ValueError("Unexpected frontend distribution domain")
    return {"bucket": bucket, "api": api, "site": f"https://{domain}"}


def aws(args):
    result = subprocess.run(
        ["aws", "--region", REGION, "--no-cli-pager", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "AWS CLI command failed")
    return result.stdout


def verify_job(environment):
    if os.getenv("GITHUB_ACTIONS") != "true":
        raise ValueError("Publish through GitHub Actions; local default profiles are forbidden")
    if os.getenv("AWS_REGION") != REGION or os.getenv("DEPLOY_ENV") != environment:
        raise ValueError("Unexpected deployment region or environment")
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        raise ValueError("Explicit job credentials are required")
    identity = json.loads(aws(["sts", "get-caller-identity", "--output", "json"]))
    if identity.get("Account") != ACCOUNT:
        raise ValueError("STOP: credentials belong to another AWS account; no upload attempted")


def upload(targets, dist):
    if not (dist / "index.html").is_file() or not (dist / "assets").is_dir():
        raise ValueError("Frontend build is missing index.html or assets")
    # Hashed assets are uploaded first; previous versions are preserved for open browser tabs.
    aws(
        [
            "s3",
            "sync",
            str(dist / "assets"),
            f"s3://{targets['bucket']}/assets/",
            "--cache-control",
            "public,max-age=31536000,immutable",
            "--only-show-errors",
            "--no-follow-symlinks",
        ]
    )
    aws(
        [
            "s3",
            "cp",
            str(dist / "index.html"),
            f"s3://{targets['bucket']}/index.html",
            "--content-type",
            "text/html; charset=utf-8",
            "--cache-control",
            "no-cache,no-store,must-revalidate",
            "--only-show-errors",
        ]
    )


def smoke_check(site, expected):
    # Bounded retries cover propagation/error caching; no cookies or AWS credentials are sent.
    last_error = "different HTML served"
    for attempt in range(4):
        try:
            request = Request(f"{site}/", headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=15) as response:
                if response.read(512000) == expected:
                    return
        except (URLError, OSError) as exc:
            last_error = type(exc).__name__
        if attempt < 3:
            time.sleep(4)
    raise RuntimeError(
        f"Frontend uploaded but new HTML was not verified: {last_error}; inspect CloudFront"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["dev", "prod"])
    args = parser.parse_args()
    try:
        verify_job(args.environment)
        outputs = json.loads(
            aws(
                [
                    "cloudformation",
                    "describe-stacks",
                    "--stack-name",
                    f"tambooh-{args.environment}",
                    "--query",
                    "Stacks[0].Outputs",
                    "--output",
                    "json",
                ]
            )
        )
        targets = frontend_targets(outputs, args.environment)
        subprocess.run(["npm", "ci"], cwd=ROOT / "frontend", check=True)
        for task in ["lint", "test", "build"]:
            subprocess.run(
                ["npm", "run", task],
                cwd=ROOT / "frontend",
                check=True,
                env={**os.environ, "VITE_API_BASE_URL": targets["api"]},
            )
        dist = ROOT / "frontend/dist"
        upload(targets, dist)
        smoke_check(targets["site"], (dist / "index.html").read_bytes())
        print(f"Frontend published and HTML verified: {targets['site']}")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a") as file:
                file.write(
                    f"\n## Frontend\n\nPublished HTML verified: {targets['site']}\n\nAPI: {targets['api']}\n"
                )
    except (ValueError, KeyError, RuntimeError, subprocess.SubprocessError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
