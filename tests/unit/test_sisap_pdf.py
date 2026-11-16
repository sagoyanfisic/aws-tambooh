"""Regression for the real downloaded Mañanero layout; no AWS/network required."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from src.common.parsers import DatasetQualityError, parse_pdf, parse_rows

FIXTURES = Path(__file__).parents[1] / "fixtures"
URL = "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf"


def test_sisap_two_row_header_preserves_distinct_average_columns():
    rows = [
        [
            "Mercado",
            "Producto",
            "Hoy",
            "Ayer",
            "Diferencia Soles",
            "Precio Promedio S/ por Kg",
            None,
        ],
        ["", "", "S/ por Kg", "S/ por Kg", "Hoy - Ayer", "Mes de Octubre", "Últimos 7 días"],
        ["Lima", "Papa canchan", "2.93", "2.90", "0.03", "2.16", "2.97"],
    ]
    records = parse_rows(
        rows, date(2026, 11, 16), "sisap_mananero", "Lima", URL, "MIDAGRI", "raw/report.pdf"
    )
    assert len(records) == 1
    assert records[0].price_pen_per_kg == 2.93
    assert records[0].price_prev_day == 2.90
    assert records[0].avg_prev_month == 2.16
    assert records[0].avg_7d == 2.97
    rows[1][5] = "Mes de Setiembre"
    with pytest.raises(DatasetQualityError, match="previous observation month"):
        parse_rows(
            rows, date(2026, 11, 16), "sisap_mananero", "Lima", URL, "MIDAGRI", "raw/report.pdf"
        )


def test_real_sisap_pdf_has_18_rows_three_markets_and_verifiable_hash():
    pytest.importorskip("pdfplumber", reason="Install project dependencies for real PDF extraction")
    path = FIXTURES / "sisap_mananero_2026-11-16.pdf"
    provenance = json.loads(path.with_suffix(".provenance.json").read_text())
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == provenance["sha256"]
    records = parse_pdf(
        payload,
        source_id="sisap_mananero",
        market="Lima",
        source_url=URL,
        institution="MIDAGRI",
        raw_s3_key="raw/sisap_mananero/report.pdf",
        expected_date=date(2026, 11, 16),
    )
    assert len(records) == 18
    assert len({r.market for r in records}) == 3
    assert all(r.observation_date == date(2026, 11, 16) for r in records)
    assert all(r.price_type == "wholesale" and r.currency == "PEN" for r in records)
    assert all(r.transport == "http_insecure" for r in records)
    papa = next(r for r in records if r.product == "PAPA CANCHAN")
    assert papa.price_pen_per_kg == 2.93
    assert papa.avg_prev_month == 2.16
    assert papa.avg_7d == 2.97
