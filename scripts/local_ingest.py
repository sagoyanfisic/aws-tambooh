#!/usr/bin/env python3
"""Run one TamBooh ingestion source locally without Lambda, AWS, or deployment."""

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from botocore.exceptions import BotoCoreError, ClientError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures"
SOURCES = {
    "sisap_mananero": (
        "sisap_sample.txt",
        "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
        "Gran Mercado Mayorista de Lima",
        "MIDAGRI-DGESEP-DEIA",
    ),
    "gmml_ingreso": (
        "gmml_sample.txt",
        "https://siea.midagri.gob.pe/files/datos_estadisticas/diarias/mml/",
        "Gran Mercado Mayorista de Lima",
        "MIDAGRI-DGESEP-DEIA",
    ),
    "papa_boletin": (
        "papa_sample.txt",
        "https://www.gob.pe/institucion/midagri/colecciones/5-boletin-diario-de-abastecimiento-y-precio-de-papa",
        "Lima",
        "MIDAGRI-DGESEP-DEIA",
    ),
    "productores": (
        "productores_sample.txt",
        "https://www.gob.pe/institucion/midagri/colecciones/18-reporte-de-ingreso-y-precios-en-el-mercado-mayorista-de-productores",
        "Santa Anita",
        "EMMSA",
    ),
}


def main():
    from src.common.sources import TransientSourceError
    from src.functions.ingest_worker.app import lambda_handler

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument(
        "--live",
        action="store_true",
        help="download the configured source instead of using a fixture",
    )
    parser.add_argument(
        "--file", type=Path, help="read a downloaded PDF or extracted text file locally"
    )
    parser.add_argument("--url", help="override the source URL, useful for a dated SIEA PDF")
    parser.add_argument("--date", help="expected observation date YYYY-MM-DD, including backfill")
    parser.add_argument("--output", type=Path, help="write normalized records to a local JSON file")
    args = parser.parse_args()
    if any(
        os.getenv(key) for key in ("RAW_BUCKET", "PRICE_TABLE_NAME", "AWS_LAMBDA_FUNCTION_NAME")
    ):
        parser.error(
            "Local runner requires RAW_BUCKET and PRICE_TABLE_NAME unset; AWS writes are disabled"
        )
    fixture, default_url, market, institution = SOURCES[args.source]
    if args.live and args.file:
        parser.error("use either --live or --file, not both")
    event = {
        "action": "fetch",
        "source_id": args.source,
        "source_url": args.url or default_url,
        "market": market,
        "institution": institution,
    }
    if args.date:
        event["expected_observation_date"] = args.date
    if args.file:
        payload = args.file.read_bytes()
        if payload.startswith(b"%PDF") and not args.date:
            event["expected_observation_date"] = (
                datetime.now(ZoneInfo("America/Lima")).date().isoformat()
            )
        event = {
            **event,
            "action": "parse",
            "body_b64": base64.b64encode(payload).decode(),
            "body": payload.decode("utf-8", errors="ignore"),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "raw_s3_key": f"local/{args.file.name}",
        }
    elif not args.live:
        event["fixture_text"] = (FIXTURES / fixture).read_text(encoding="utf-8")
    source_metadata = event
    try:
        fetched = lambda_handler(event, None)
        parsed = fetched if args.file else lambda_handler({**fetched, "action": "parse"}, None)
    except (BotoCoreError, ClientError, OSError, ValueError, TransientSourceError) as exc:
        print(
            json.dumps(
                {
                    "source": args.source,
                    "mode": "live",
                    "status": "source_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2
    if fetched.get("status") == "no_publication":
        print(
            json.dumps(
                {
                    "source": args.source,
                    "status": "no_publication",
                    "http_status": fetched.get("http_status"),
                },
                indent=2,
            )
        )
        return 0
    mode = "file" if args.file else ("live" if args.live else "fixture")
    print(
        json.dumps(
            {
                "source": args.source,
                "mode": mode,
                "status": parsed["status"],
                "rows": parsed["rows"],
                "missing": parsed["missing"],
                "sha256": fetched.get("sha256") or source_metadata.get("sha256"),
                "raw_s3_key": fetched.get("raw_s3_key") or source_metadata.get("raw_s3_key"),
            },
            indent=2,
        )
    )
    if args.output:
        args.output.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
