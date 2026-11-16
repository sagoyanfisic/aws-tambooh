import hashlib
import os
import base64
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx
from src.common.parsers import parse_delimited
from src.common.storage import store_records, report
try:
    from aws_lambda_powertools import Logger, Metrics
    from aws_lambda_powertools.metrics import MetricUnit
    logger, metrics = Logger(service="tambooh-ingestion"), Metrics(namespace="TamBooh/Ingestion")
except ImportError:
    class _Noop:
        def __getattr__(self, name): return lambda *args, **kwargs: None
    logger = metrics = _Noop(); MetricUnit = type("MetricUnit", (), {"Count": "Count"})

SOURCE_URLS = {
    "sisap_mananero": "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
    "gmml_ingreso": "https://siea.midagri.gob.pe/files/datos_estadisticas/diarias/mml/",
    "papa_boletin": "https://www.gob.pe/institucion/midagri/colecciones/5-boletin-diario-de-abastecimiento-y-precio-de-papa",
    "productores": "https://www.gob.pe/institucion/midagri/colecciones/18-reporte-de-ingreso-y-precios-en-el-mercado-mayorista-de-productores",
}

def _validate_pdf(body: bytes, source_id: str, fixture: bool) -> None:
    if fixture:
        return
    if not body.startswith(b"%PDF"):
        raise ValueError(f"{source_id} response is not a PDF; first bytes={body[:12]!r}")

def _validate_observation_date(body: bytes, fixture: bool) -> None:
    if fixture:
        return
    import io
    import pdfplumber
    from src.common.dates import parse_spanish_date
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    observed = parse_spanish_date(text)
    lima_today = datetime.now(ZoneInfo("America/Lima")).date()
    if observed != lima_today:
        raise ValueError(f"stale or future report: observation_date={observed.isoformat()} expected={lima_today.isoformat()}")

def fetch(event):
    source_id = event["source_id"]; url = event.get("source_url", SOURCE_URLS[source_id])
    is_fixture = event.get("fixture_text") is not None
    if is_fixture:
        body = event["fixture_text"].encode(); status = 200
    else:
        last_error = None
        for attempt in range(1, 4):
            try:
                with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "TamBooh-ingest/0.1 (+contacto)", "Accept": "application/pdf,*/*"}, verify=True) as client:
                    result = client.get(url); status = result.status_code
                    if status == 404:
                        return {**event, "source_url": url, "status": "no_publication", "http_status": status, "retrieved_at": datetime.now(timezone.utc).isoformat()}
                    result.raise_for_status(); body = result.content; last_modified = result.headers.get("Last-Modified")
                break
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
                if attempt < 3: time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"source unavailable after 3 attempts: {last_error}") from last_error
    _validate_pdf(body, source_id, is_fixture)
    _validate_observation_date(body, is_fixture)
    digest = hashlib.sha256(body).hexdigest(); retrieved = datetime.now(timezone.utc).isoformat(); day = retrieved[:10]
    raw_key = f"raw/{source_id}/{day.replace('-', '/')}/source.pdf"
    if os.getenv("RAW_BUCKET"):
        import boto3
        boto3.client("s3").put_object(Bucket=os.environ["RAW_BUCKET"], Key=raw_key, Body=body, Metadata={"url": url, "sha256": digest, "http-status": str(status), "retrieved-at": retrieved})
    result = {**event, "source_url": url, "http_status": status, "last_modified": locals().get("last_modified"), "retrieved_at": retrieved, "sha256": digest, "raw_s3_key": raw_key}
    if not os.getenv("RAW_BUCKET") or event.get("include_body"):
        result.update({"body": body.decode("utf-8", errors="ignore"), "body_b64": base64.b64encode(body).decode()})
    return result

def lambda_handler(event, context):
    if event.get("action", "fetch") == "fetch": return fetch(event)
    if event.get("status") == "no_publication": return {"source_id": event["source_id"], "status": "no_publication", "rows": 0, "missing": 0}
    if event.get("raw_s3_key") and os.getenv("RAW_BUCKET") and not event.get("body_b64"):
        import boto3
        payload = boto3.client("s3").get_object(Bucket=os.environ["RAW_BUCKET"], Key=event["raw_s3_key"])["Body"].read()
    else:
        payload = base64.b64decode(event["body_b64"]) if event.get("body_b64") else event["body"].encode()
    if payload.startswith(b"%PDF"):
        _validate_observation_date(payload, fixture=False)
    text = event.get("body", "")
    if payload.startswith(b"%PDF"):
        import io, pdfplumber
        with pdfplumber.open(io.BytesIO(payload)) as pdf: text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    records = parse_delimited(text, event["source_id"], event.get("market", "Lima"), event["source_url"], event.get("institution", "MIDAGRI-DGESEP-DEIA"), event.get("raw_s3_key", ""))
    metrics.add_metric(name="RowsParsed", unit=MetricUnit.Count, value=len(records)); metrics.add_dimension(name="Source", value=event["source_id"])
    result = store_records(records)
    return {"source_id": event["source_id"], "status": "ok", "rows": len(records), "missing": result["missing"], "retrieved_at": event.get("retrieved_at")}

