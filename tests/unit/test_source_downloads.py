"""Source failures, bounded discovery and manual imports; no network or AWS calls."""

import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from src.common import sources
from src.common.parsers import DatasetQualityError
from src.functions.ingest_worker import app as worker

ROOT = Path(__file__).resolve().parents[2]


def mock_client(monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    factory = Mock(return_value=client)
    monkeypatch.setattr(sources.httpx, "Client", factory)
    monkeypatch.setattr(sources.time, "sleep", lambda delay: None)
    result = sources.OfficialClient()
    assert factory.call_args.kwargs["verify"] is True
    return result


def test_retry_error_identifies_the_robots_url_and_http_status(monkeypatch):
    urls = []

    def respond(request):
        urls.append(str(request.url))
        return httpx.Response(503)

    client = mock_client(monkeypatch, respond)
    with pytest.raises(sources.TransientSourceError, match=r"robots.txt.*HTTP 503"):
        client.get("https://siea.midagri.gob.pe/report.pdf")
    assert len(urls) == 3
    assert all(url.endswith("/robots.txt") for url in urls)
    client.close()


def test_tls_errors_are_reported_without_disabling_certificate_validation(monkeypatch):
    def respond(request):
        raise httpx.ConnectError("CERTIFICATE_VERIFY_FAILED: certificate expired", request=request)

    client = mock_client(monkeypatch, respond)
    with pytest.raises(sources.TransientSourceError, match="CERTIFICATE_VERIFY_FAILED"):
        client.get("https://siea.midagri.gob.pe/report.pdf")
    client.close()


def test_robots_redirect_is_followed_before_downloading(monkeypatch):
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(301, headers={"Location": "/policy/robots.txt"})
        if request.url.path == "/policy/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, content=b"%PDF-synthetic-test-only")

    client = mock_client(monkeypatch, respond)
    assert client.get("https://www.gob.pe/report.pdf")[0] == 200
    assert paths == ["/robots.txt", "/policy/robots.txt", "/report.pdf"]
    client.close()


@pytest.mark.parametrize(
    "target", ["https://untrusted.test/robots.txt", "http://www.gob.pe/robots.txt"]
)
def test_robots_redirect_cannot_escape_hosts_or_downgrade_tls(monkeypatch, target):
    handler = Mock(return_value=httpx.Response(302, headers={"Location": target}))
    client = mock_client(monkeypatch, handler)
    with pytest.raises(sources.SourceConfigurationError):
        client.get("https://www.gob.pe/report.pdf")
    assert handler.call_count == 1
    client.close()


def test_robots_disallow_is_not_bypassed(monkeypatch):
    handler = Mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /"))
    client = mock_client(monkeypatch, handler)
    with pytest.raises(sources.SourceConfigurationError, match="disallows"):
        client.get("https://www.gob.pe/report.pdf")
    assert handler.call_count == 1
    client.close()


@pytest.mark.parametrize("query", ["sheet=", "order=desc&sheet=2", "Sheet=1"])
def test_pagination_is_refused_even_for_blank_or_non_first_query_parameter(query):
    with pytest.raises(sources.SourceConfigurationError, match="pagination"):
        sources.validate_source_url(f"https://www.gob.pe/institucion/midagri/colecciones/5?{query}")


@pytest.mark.parametrize(
    "source,keyword", [("papa_boletin", "papa"), ("productores", "productores")]
)
def test_collection_year_month_and_dated_pdf_label(monkeypatch, source, keyword):
    # Synthetic HTML and PDF bytes model the official collection structure, not live data.
    root = sources.SOURCE_URLS[source]
    year = f"https://www.gob.pe/institucion/midagri/colecciones/999-{keyword}-2026"
    month = f"https://www.gob.pe/institucion/midagri/informes-publicaciones/999-{keyword}-noviembre-2026"
    pdf = "https://cdn.www.gob.pe/uploads/document/file/999/report.pdf?v=1"
    bodies = {
        root: f'<a href="{root}?order=desc&sheet=2">Next</a><a href="{year}">2026</a>',
        year: f'<a href="{month}">Noviembre 2026</a>',
        month: f'<a href="{pdf}"><span>Reporte 16/11/2026</span></a>',
        pdf: "%PDF-synthetic-test-only",
    }
    calls = []

    def get(url):
        calls.append(url)
        return 200, {}, bodies[url].encode(), url

    result = sources.resolve_and_download(Mock(get=get), source, date(2026, 11, 16))
    assert result[3] == pdf
    assert calls == [root, year, month, pdf]


@pytest.mark.parametrize(
    "text", ["16-11-2026.pdf", "16_11_2026.pdf", "2026-11-16.pdf", "16%2F11%2F2026"]
)
def test_dated_pdf_matches_exact_requested_day(text):
    assert sources.date_matches(text, date(2026, 11, 16))
    assert not sources.date_matches(text, date(2026, 11, 15))


def test_absent_publication_explains_requested_date_and_discovery_limit():
    client = Mock()
    url = sources.SOURCE_URLS["papa_boletin"]
    client.get.return_value = (200, {}, b"<html>No matching publication</html>", url)
    with pytest.raises(sources.SourceConfigurationError, match="2026-11-16.*1 official pages"):
        sources.resolve_and_download(client, "papa_boletin", date(2026, 11, 16))
    client.get.assert_called_once_with(url)


def test_state_machine_preserves_optional_source_date_and_s3_reference():
    flow = json.loads((ROOT / "statemachine/ingest.asl.json").read_text())
    # Map's default passes each source object intact rather than dropping optional import fields.
    assert "Parameters" not in flow["States"]["IngestSources"]
    assert "ItemSelector" not in flow["States"]["IngestSources"]


def test_manual_s3_import_preserves_provenance_without_contacting_source(monkeypatch):
    import boto3

    monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
    monkeypatch.setenv("PRICE_TABLE_NAME", "test-prices")
    payload = b"%PDF-synthetic-test-only"
    s3 = Mock()
    s3.get_object.return_value = {"Body": io.BytesIO(payload)}
    db = Mock()
    db.Table.return_value.get_item.return_value = {}
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    monkeypatch.setattr(boto3, "resource", lambda service: db)
    external = Mock(side_effect=AssertionError("Manual import must not call the source"))
    monkeypatch.setattr(worker, "OfficialClient", external)
    request = {
        "source_id": "sisap_mananero",
        "source_url": sources.SOURCE_URLS["sisap_mananero"],
        "import_s3_key": "imports/sisap_mananero/report.pdf",
        "expected_observation_date": "2026-11-14",
    }
    result = worker.fetch(worker.IngestEvent(**request))
    assert result["status"] == "downloaded"
    assert result["expected_observation_date"] == "2026-11-14"
    assert result["http_status"] is None
    assert result["source_url"] == request["source_url"]
    assert result["transport"] == "http_insecure"
    assert "body_b64" not in result
    metadata = s3.put_object.call_args.kwargs["Metadata"]
    assert metadata["acquisition"] == "manual_s3_import"
    assert metadata["http-status"] == "not-requested"
    external.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"import_s3_key": "curated/prices/report.pdf"},
        {"import_s3_key": "imports/productores/report.pdf"},
        {"source_url": "https://untrusted.test/report.pdf"},
        {"expected_observation_date": None},
    ],
)
def test_invalid_manual_import_is_rejected_before_s3_access(monkeypatch, overrides):
    import boto3

    monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
    monkeypatch.setenv("PRICE_TABLE_NAME", "test-prices")
    client = Mock(side_effect=AssertionError("No S3 access for invalid input"))
    monkeypatch.setattr(boto3, "client", client)
    event = {
        "source_id": "sisap_mananero",
        "source_url": sources.SOURCE_URLS["sisap_mananero"],
        "import_s3_key": "imports/sisap_mananero/report.pdf",
        "expected_observation_date": "2026-11-14",
        **overrides,
    }
    with pytest.raises(ValueError):
        worker.fetch(worker.IngestEvent(**event))
    client.assert_not_called()


def test_manual_import_rejects_non_pdf_before_raw_storage(monkeypatch):
    import boto3

    monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
    monkeypatch.setenv("PRICE_TABLE_NAME", "test-prices")
    s3 = Mock()
    s3.get_object.return_value = {"Body": io.BytesIO(b"<html>not a PDF</html>")}
    monkeypatch.setattr(boto3, "client", lambda service: s3)
    with pytest.raises(DatasetQualityError, match="not a PDF"):
        worker.fetch(
            worker.IngestEvent(
                source_id="sisap_mananero",
                source_url=sources.SOURCE_URLS["sisap_mananero"],
                expected_observation_date=date(2026, 11, 14),
                import_s3_key="imports/sisap_mananero/report.pdf",
            )
        )
    s3.put_object.assert_not_called()
