"""Validated ingestion tasks. AWS payloads contain S3 references, never PDF bytes."""
import base64
import hashlib
import logging
import os
from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from src.common.models import SourceId
from src.common.parsers import PARSER_VERSION, DatasetQualityError, parse_delimited, parse_pdf
from src.common.sources import MAX_BYTES, OfficialClient, resolve_and_download
from src.common.storage import TransientStorageError, active_dataset, snapshot_id, store_records

try:
    from aws_lambda_powertools import Logger, Metrics
    logger = Logger(service="tambooh-ingestion")
    metrics = Metrics(namespace="TamBooh/Ingestion", service="ingestion")
except ImportError:
    # Local tooling can run before Powertools is installed; production must package it.
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        raise
    logger = logging.getLogger("tambooh-ingestion")
    metrics = None


class IngestEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["fetch", "parse"] = "fetch"
    source_id: SourceId
    source_url: str | None = None
    market: str = "Lima"
    institution: str = "MIDAGRI-DGESEP-DEIA"
    expected_observation_date: date | None = None
    raw_s3_key: str | None = None
    retrieved_at: datetime | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: str | None = None
    http_status: int | None = None
    last_modified: str | None = None
    transport: str | None = None
    fixture_text: str | None = None
    body_b64: str | None = None
    body: str | None = None


def local_only():
    return not any(os.getenv(key) for key in (
        "AWS_LAMBDA_FUNCTION_NAME", "RAW_BUCKET", "PRICE_TABLE_NAME"))


def fetch(event: IngestEvent):
    now = datetime.now(timezone.utc)
    expected = event.expected_observation_date or now.astimezone(ZoneInfo("America/Lima")).date()
    last_modified = None
    if event.fixture_text is not None:
        payload = event.fixture_text.encode()
        status, url = 200, event.source_url or "http://fixture.local/report.pdf"
    else:
        client = OfficialClient()
        try:
            status, headers, payload, url = resolve_and_download(
                client, event.source_id, expected, event.source_url)
            last_modified = headers.get("last-modified")
        finally:
            client.close()
    result = event.model_dump(mode="json", exclude_none=True)
    result.pop("fixture_text", None)
    result.update(source_url=url, http_status=status, retrieved_at=now.isoformat(),
                  expected_observation_date=expected.isoformat(), last_modified=last_modified,
                  transport="http_insecure" if url.startswith("http://") else "https")
    if status == 404:
        return {**result, "status": "no_publication"}
    if len(payload) > MAX_BYTES:
        raise DatasetQualityError("File exceeds 12 MiB")
    if event.fixture_text is None and not payload.startswith(b"%PDF"):
        raise DatasetQualityError("Official response is not a PDF")
    digest = hashlib.sha256(payload).hexdigest()
    day = expected.strftime("%Y/%m/%d")
    key = f"raw/{event.source_id}/{day}/{digest}.pdf"
    result.update(status="downloaded", sha256=digest, raw_s3_key=key)
    if local_only():
        result.update(body_b64=base64.b64encode(payload).decode())
        if event.fixture_text is not None:
            result["body"] = event.fixture_text
            result.pop("expected_observation_date", None)
        return result
    import boto3
    bucket = os.environ["RAW_BUCKET"]
    s3 = boto3.client("s3")
    from botocore.exceptions import ClientError
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/pdf",
                      IfNoneMatch="*", Metadata={"url": url, "sha256": digest,
                      "http-status": str(status), "retrieved-at": now.isoformat(),
                      "transport": result["transport"], "last-modified": last_modified or ""})
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
            raise
    table = boto3.resource("dynamodb").Table(os.environ["PRICE_TABLE_NAME"])
    published = active_dataset(table, event.source_id)
    if published and published["dataset_id"] == snapshot_id(digest):
        result["status"] = "unchanged"
    return result


def parse(event: IngestEvent):
    if event.status in {"no_publication", "unchanged"}:
        return {"source_id": event.source_id, "status": event.status, "rows": 0, "missing": 0}
    if local_only():
        payload = base64.b64decode(event.body_b64, validate=True) if event.body_b64 else (
            event.body or "").encode()
    else:
        import boto3
        prefix = f"raw/{event.source_id}/"
        if not event.raw_s3_key or not event.raw_s3_key.startswith(prefix):
            raise ValueError("Invalid source S3 reference")
        obj = boto3.client("s3").get_object(Bucket=os.environ["RAW_BUCKET"], Key=event.raw_s3_key)
        payload = obj["Body"].read(MAX_BYTES + 1)
    if not payload or len(payload) > MAX_BYTES:
        raise DatasetQualityError("Empty or oversized input")
    digest = hashlib.sha256(payload).hexdigest()
    if event.sha256 and digest != event.sha256:
        raise DatasetQualityError("S3 object hash differs from download reference")
    kwargs = dict(source_id=event.source_id, market=event.market, source_url=event.source_url or "",
                  institution=event.institution, raw_s3_key=event.raw_s3_key or "",
                  retrieved_at=event.retrieved_at)
    if payload.startswith(b"%PDF"):
        records = parse_pdf(payload, **kwargs, expected_date=event.expected_observation_date)
    elif local_only():
        records = parse_delimited(payload.decode(), **kwargs)
    else:
        raise DatasetQualityError("Stored object is not a PDF")
    result = store_records(records, sha256=digest)
    response = {"source_id": event.source_id, "status": "ok", **result,
                "retrieved_at": records[0].retrieved_at.isoformat(), "sha256": digest,
                "parser_version": PARSER_VERSION}
    if local_only():
        response["records"] = [record.model_dump(mode="json") for record in records]
    return response


def lambda_handler(event, context):
    source = event.get("source_id", "unknown")
    try:
        request = IngestEvent.model_validate(event)
        if not local_only() and any(value is not None for value in (
                request.fixture_text, request.body, request.body_b64)):
            raise ValueError("Inline inputs are supported only in the local runner")
        result = fetch(request) if request.action == "fetch" else parse(request)
        if metrics and request.action == "parse":
            metrics.add_dimension(name="Source", value=source)
            metrics.add_metric(name="RowsParsed", unit="Count", value=result["rows"])
            metrics.add_metric(name="RowsMissing", unit="Count", value=result["missing"])
        logger.info("ingestion_task", extra={"source_id": source, "action": request.action,
                                            "status": result["status"],
                                            "request_id": getattr(context, "aws_request_id", None)})
        return result
    except Exception as exc:
        logger.error("ingestion_failed", extra={"source_id": source,
                                               "error_type": type(exc).__name__,
                                               "request_id": getattr(context, "aws_request_id", None)})
        if metrics:
            metrics.add_dimension(name="Source", value=source)
            metrics.add_metric(name="SourceFailed", unit="Count", value=1)
        from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError
        if event.get("action") == "parse":
            transient_codes = {"ThrottlingException", "ProvisionedThroughputExceededException",
                               "RequestLimitExceeded", "InternalServerError", "SlowDown",
                               "ServiceUnavailable", "InternalError"}
            if ((isinstance(exc, ClientError) and exc.response["Error"]["Code"] in transient_codes)
                    or isinstance(exc, (EndpointConnectionError, ConnectionClosedError))):
                raise TransientStorageError("Retryable AWS storage failure") from exc
        raise
    finally:
        if metrics:
            metrics.flush_metrics()
