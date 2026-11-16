"""Behavioral regressions: no network or AWS credentials required."""
import copy
import hashlib
import io
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from boto3.dynamodb.types import TypeSerializer

from src.common.models import dynamo_keys
from src.common.parsers import DatasetQualityError, parse_delimited, parse_pdf
from src.common.storage import load_published, store_records
from src.common.units import parse_unit
from src.functions.ingest_worker import app as worker
from src.functions.report.app import lambda_handler as report_handler

ROOT = Path(__file__).resolve().parents[2]


def records():
    text = (ROOT / "tests/fixtures/gmml_sample.txt").read_text()
    return parse_delimited(text, "gmml_ingreso", "Lima", "https://siea.midagri.gob.pe/test.pdf",
                           "MIDAGRI", "raw/gmml_ingreso/test.pdf",
                           datetime(2026, 11, 14, 12, tzinfo=timezone.utc))


@pytest.fixture(autouse=True)
def no_aws_environment(monkeypatch):
    for key in ("AWS_LAMBDA_FUNCTION_NAME", "RAW_BUCKET", "PRICE_TABLE_NAME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.mark.parametrize("unit,expected", [
    ("10 pqtes. de 1kg", {"unit_qty_kg": 10.0}),
    ("Saco de 49 kg", {"unit_qty_kg": 49.0}),
    ("Lata de 18 L", {"unit_qty_l": 18.0}),
    ("caja de 12 Bot.", {"quality_flags": ["unit_unparsed"]}),
])
def test_units(unit, expected):
    assert parse_unit(unit) == expected


def test_unknown_layout_cannot_publish_zero_rows():
    with pytest.raises(DatasetQualityError):
        parse_delimited("Fecha: 14 de noviembre del 2026\nPapa kg 1.80", "gmml_ingreso",
                        "Lima", "https://example.test", "MIDAGRI", "raw/test")


def test_correct_columns_missing_and_outliers():
    text = ("Fecha: 14 de noviembre del 2026\n"
            "Mercado|Producto|Hoy S/ por kg|Ayer S/ por kg|Diferencia|Promedio mes anterior|Promedio ultimos 7 dias\n"
            "Lima|Papa|10|2|8|2|1\nLima|Cebolla|:|2|:|2|2")
    result = parse_delimited(text, "sisap_mananero", "Lima", "http://example.test", "MIDAGRI", "raw/test")
    assert result[0].price_prev_day == 2
    assert result[0].avg_7d == 1
    assert result[0].avg_prev_month == 2
    assert "outlier" in result[0].quality_flags
    assert result[1].is_missing


@pytest.mark.parametrize("value", ["abc", "nan", "-3", "inf", "0"])
def test_invalid_number_is_not_a_missing_price(value):
    text = f"Fecha: 14 de noviembre del 2026\nProducto|Unidad|Precio hoy\nPapa|kg|{value}"
    with pytest.raises(DatasetQualityError):
        parse_delimited(text, "gmml_ingreso", "Lima", "https://example.test", "MIDAGRI", "raw/test")


def test_duplicate_identity_rejected():
    text = "Fecha: 14 de noviembre del 2026\nProducto|Unidad|Precio hoy\nPapa|kg|2\nPapa|kg|3"
    with pytest.raises(DatasetQualityError, match="Duplicate"):
        parse_delimited(text, "gmml_ingreso", "Lima", "https://example.test", "MIDAGRI", "raw/test")


def test_pdf_table_cells_not_pipe_text(monkeypatch):
    page = Mock()
    page.extract_text.return_value = "Fecha: 14 de noviembre del 2026\nPapa  kg  2.00"
    page.extract_tables.return_value = [[['Producto', 'Unidad', 'Precio hoy'], ['Papa', 'kg', '2.00']]]
    mock_pdf = Mock()
    mock_pdf.__enter__ = Mock(return_value=SimpleNamespace(pages=[page]))
    mock_pdf.__exit__ = Mock(return_value=False)
    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=Mock(return_value=mock_pdf)))
    args = dict(source_id="gmml_ingreso", market="Lima", source_url="https://example.test/a.pdf",
                institution="MIDAGRI", raw_s3_key="raw/test")
    assert parse_pdf(b"%PDF-test", **args, expected_date=date(2026, 11, 14))[0].price_pen_per_kg == 2
    with pytest.raises(DatasetQualityError, match="differs"):
        parse_pdf(b"%PDF-test", **args, expected_date=date(2026, 11, 15))


class MemoryTable:
    def __init__(self):
        self.items = {}
        self.writes = 0
        self.fail_on_write = None

    def get_item(self, Key, **kwargs):
        return {"Item": copy.deepcopy(self.items[tuple(Key.values())])} if tuple(Key.values()) in self.items else {}

    def put_item(self, Item, **kwargs):
        TypeSerializer().serialize(Item)
        self.writes += 1
        if self.writes == self.fail_on_write:
            raise RuntimeError("DynamoDB temporary failure")
        current = self.items.get((Item["pk"], Item["sk"]))
        condition = kwargs.get("ConditionExpression")
        conflict = (condition == "attribute_not_exists(dataset_id)" and current is not None)
        if condition == "dataset_id = :previous":
            conflict = not current or current["dataset_id"] != kwargs["ExpressionAttributeValues"][":previous"]
        if conflict:
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[(Item["pk"], Item["sk"])] = copy.deepcopy(Item)

    def query(self, **kwargs):
        assert kwargs["ConsistentRead"]
        return {"Items": [i for (pk, _), i in self.items.items() if pk == "DATASETS"]}


class MemoryS3:
    def __init__(self):
        self.items = {}
        self.fail = False

    def put_object(self, Bucket, Key, Body, **kwargs):
        if self.fail:
            raise RuntimeError("S3 storage failure")
        self.items[Key] = Body

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.items[Key])}


def aws_storage(monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", "test-bucket")
    monkeypatch.setenv("PRICE_TABLE_NAME", "test-table")
    table, s3 = MemoryTable(), MemoryS3()
    db = SimpleNamespace(Table=lambda name: table)
    return table, s3, db


def test_decimal_keys_publication_and_idempotency(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    row = records()[0]
    assert {"pk", "sk"} <= dynamo_keys(row).keys()
    assert store_records([row], db, s3, "a" * 64)["publication"] == "published"
    writes = table.writes
    assert store_records([row], db, s3, "a" * 64)["publication"] == "unchanged"
    assert table.writes == writes
    assert load_published(table, s3, "test-bucket")[0] == row


@pytest.mark.parametrize("failure", ["s3", "dynamodb"])
def test_failed_publication_preserves_active_dataset(monkeypatch, failure):
    table, s3, db = aws_storage(monkeypatch)
    rows = records()
    store_records(rows, db, s3, "a" * 64)
    original = copy.deepcopy(table.items[("DATASETS", "SOURCE#gmml_ingreso")])
    if failure == "s3":
        s3.fail = True
    else:
        table.fail_on_write = table.writes + 2
    with pytest.raises(RuntimeError):
        store_records(rows, db, s3, "b" * 64)
    assert table.items[("DATASETS", "SOURCE#gmml_ingreso")] == original
    assert load_published(table, s3, "test-bucket") == rows


def test_versions_do_not_overwrite_old_rows(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    rows = records()
    store_records(rows, db, s3, "a" * 64)
    old = set(table.items)
    store_records(rows, db, s3, "b" * 64)
    assert old <= set(table.items)
    assert len([pk for pk, sk in table.items if pk.startswith("PRODUCT#")]) == 4


def test_historical_backfill_does_not_replace_active_manifest(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    rows = records()
    store_records(rows, db, s3, "a" * 64)
    before = copy.deepcopy(table.items[("DATASETS", "SOURCE#gmml_ingreso")])
    old_rows = [row.model_copy(update={"observation_date": date(2026, 11, 13)}) for row in rows]
    assert store_records(old_rows, db, s3, "b" * 64)["publication"] == "historical_only"
    assert table.items[("DATASETS", "SOURCE#gmml_ingreso")] == before
    assert any("date=2026-11-13" in key for key in s3.items)


def test_concurrent_publication_does_not_overwrite_winner(monkeypatch):
    from botocore.exceptions import ClientError
    table, s3, db = aws_storage(monkeypatch)
    rows = records()
    store_records(rows, db, s3, "a" * 64)
    put_object = s3.put_object
    def competing_publisher(**kwargs):
        put_object(**kwargs)
        if kwargs["Key"].endswith("records.json"):
            table.items[("DATASETS", "SOURCE#gmml_ingreso")]["dataset_id"] = "winning-version"
    monkeypatch.setattr(s3, "put_object", competing_publisher)
    with pytest.raises(ClientError):
        store_records(rows, db, s3, "b" * 64)
    assert table.items[("DATASETS", "SOURCE#gmml_ingreso")]["dataset_id"] == "winning-version"


def test_s3_hash_mismatch_blocks_parse(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    import boto3
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    key = "raw/gmml_ingreso/test.pdf"
    s3.items[key] = b"%PDF-tampered"
    with pytest.raises(DatasetQualityError, match="hash differs"):
        worker.lambda_handler({"action": "parse", "source_id": "gmml_ingreso",
                               "raw_s3_key": key, "sha256": "0" * 64}, None)
    assert not table.items


def test_storage_throttling_is_retryable_but_validation_is_not(monkeypatch):
    from botocore.exceptions import ClientError
    from src.common.storage import TransientStorageError
    event = {"action": "parse", "source_id": "gmml_ingreso", "source_url": "https://example.test",
             "body": (ROOT / "tests/fixtures/gmml_sample.txt").read_text()}
    def throttle(*args, **kwargs):
        raise ClientError({"Error": {"Code": "ThrottlingException"}}, "PutItem")
    monkeypatch.setattr(worker, "store_records", throttle)
    with pytest.raises(TransientStorageError):
        worker.lambda_handler(event, None)
    with pytest.raises(DatasetQualityError):
        worker.lambda_handler({**event, "body": "Fecha: 14 de noviembre del 2026"}, None)


def test_api_reads_the_published_ingestion_contract(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    store_records(records(), db, s3, "a" * 64)
    import boto3
    monkeypatch.setattr(boto3, "resource", lambda service: db)
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    from backend.functions.api.app import lambda_handler
    result = lambda_handler({"rawPath": "/api/v1/prices"}, None)
    assert result["statusCode"] == 200
    item = json.loads(result["body"])["items"][0]
    assert item["product_name"] == "Papa blanca"
    assert item["normalized_value"] == 1.8
    assert item["original_value"] == 90
    assert item["price_type"] == "wholesale"


def test_download_s3_read_pipeline_keeps_context(monkeypatch):
    table, s3, db = aws_storage(monkeypatch)
    import boto3
    monkeypatch.setattr(boto3, "resource", lambda service: db)
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    monkeypatch.setattr(worker, "OfficialClient", lambda: SimpleNamespace(close=lambda: None))
    payload = b"%PDF-synthetic-test"
    monkeypatch.setattr(worker, "resolve_and_download", lambda *args: (
        200, {}, payload, "http://sistemas.midagri.gob.pe/test.pdf"))
    event = {"action": "fetch", "source_id": "gmml_ingreso", "market": "Lima",
             "institution": "MIDAGRI", "expected_observation_date": "2026-11-14"}
    download = worker.lambda_handler(event, None)
    assert "body_b64" not in download and "body" not in download
    assert hashlib.sha256(payload).hexdigest() in download["raw_s3_key"]
    monkeypatch.setattr(worker, "parse_pdf", lambda payload, **kwargs: records())
    result = worker.lambda_handler({**download, "action": "parse"}, None)
    assert result["publication"] == "published"
    assert result["rows"] == 2


def test_invalid_action_and_aws_inline_inputs_rejected(monkeypatch):
    with pytest.raises(ValueError):
        worker.lambda_handler({"action": "whatever", "source_id": "sisap_mananero"}, None)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test")
    with pytest.raises(ValueError, match="Inline"):
        worker.lambda_handler({"source_id": "sisap_mananero", "fixture_text": "fake"}, None)


def test_report_sums_and_does_not_hide_failures():
    result = report_handler({"sources": [{"status": "ok", "rows": 12, "missing": 2},
                                         {"status": "failed"}]}, None)
    assert result["status"] == "partial_failure"
    assert result["rows"] == 12 and result["missing"] == 2
    assert report_handler({"sources": [{"status": "failed"}]}, None)["status"] == "failed"


def test_asl_context_skips_and_failure_path():
    flow = json.loads((ROOT / "statemachine/ingest.asl.json").read_text())
    states = flow["States"]["IngestSources"]["Iterator"]["States"]
    assert states["Fetch"]["ResultPath"] == "$.download"
    assert states["Fetch"]["Next"] == "Downloaded"
    assert {choice["StringEquals"] for choice in states["Downloaded"]["Choices"]} == {"no_publication", "unchanged"}
    assert states["Parse"]["Parameters"]["raw_s3_key.$"] == "$.download.raw_s3_key"
    assert all("body" not in key for key in states["Parse"]["Parameters"])
    assert flow["States"]["RunStatus"]["Choices"][0]["Next"] == "IngestionFailed"


def test_http_client_robots_pacing_retries_and_tls(monkeypatch):
    from src.common import sources
    calls, waits = [], []
    def respond(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        count = sum(url.endswith("/report.pdf") for url in calls)
        return httpx.Response(503 if count < 3 else 200, content=b"%PDF-test")
    client = httpx.Client(transport=httpx.MockTransport(respond))
    factory = Mock(return_value=client)
    monkeypatch.setattr(sources.httpx, "Client", factory)
    monkeypatch.setattr(sources.time, "sleep", waits.append)
    official = sources.OfficialClient()
    assert official.get("https://siea.midagri.gob.pe/report.pdf")[0] == 200
    assert factory.call_args.kwargs["verify"] is True
    assert sum(url.endswith("/report.pdf") for url in calls) == 3
    assert any(delay >= 2.9 for delay in waits)
    official.close()
