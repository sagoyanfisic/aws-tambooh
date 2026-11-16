"""Header-driven extraction. Unknown layouts fail closed instead of guessing columns."""

import io
import math
import unicodedata
from datetime import UTC, datetime

from .dates import parse_spanish_date
from .models import PriceRecord, dynamo_keys
from .units import normalized_price, parse_unit

PARSER_VERSION = "2.1.0"


class DatasetQualityError(ValueError):
    pass


def clean(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(value.lower().split())


def number(value):
    text = str(value or "").strip().replace("S/", "").replace(",", ".")
    if text in {"", ":"}:
        return None
    try:
        result = float(text)
    except ValueError as exc:
        raise DatasetQualityError(f"Invalid numeric cell: {text!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise DatasetQualityError("Prices must be finite nonnegative numbers")
    return result


def column_name(value):
    text = clean(value)
    if text.startswith("mercado"):
        return "market"
    if text.startswith("producto"):
        return "product"
    if text.startswith(("categoria",)):
        return "category"
    if text.startswith(("variedad", "marca")):
        return "variety_or_brand"
    if "equivalencia" in text and "kg" in text:
        return "equivalence"
    if text.startswith("unidad"):
        return "unit"
    if "ingreso" in text or "volumen" in text:
        return "volume_t" if "hoy" in text else None
    if "prom" in text and ("7" in text or "siete" in text):
        return "avg_7d"
    if "prom" in text and "mes" in text:
        return "avg_prev_month"
    if "ayer" in text:
        return "price_prev_day"
    if "hoy" in text:
        return "price_pen_per_unit"
    return None


def sisap_header_rows(rows, observed):
    """Flatten the verified Mañanero two-row header; leave unknown layouts untouched."""
    from .dates import MONTHS

    result = []
    index = 0
    while index < len(rows):
        row = rows[index]
        header = [clean(cell) for cell in row]
        if (
            len(header) == 7
            and header[:4] == ["mercado", "producto", "hoy", "ayer"]
            and "diferencia" in header[4]
            and "promedio" in header[5]
            and not header[6]
            and index + 1 < len(rows)
        ):
            units = [clean(cell) for cell in rows[index + 1]]
            if (
                len(units) != 7
                or units[:2] != ["", ""]
                or units[2:4] != ["s/ por kg", "s/ por kg"]
                or "7 dias" not in units[6]
            ):
                raise DatasetQualityError("Unrecognized SISAP two-row price header")
            previous_month = (observed.month - 2) % 12 + 1
            names = [name for name, number in MONTHS.items() if number == previous_month]
            if not any(units[5] == f"mes de {name}" for name in names):
                raise DatasetQualityError(
                    "SISAP average month is not the previous observation month"
                )
            result.append(
                [
                    "Mercado",
                    "Producto",
                    "Precio hoy",
                    "Precio ayer",
                    "Diferencia",
                    "Promedio mes anterior",
                    "Promedio ultimos 7 dias",
                ]
            )
            index += 2
        else:
            result.append(row)
            index += 1
    return result


def parse_rows(
    rows, observed, source_id, market, source_url, institution, raw_s3_key, retrieved_at=None
):
    if source_id == "sisap_mananero":
        rows = sisap_header_rows(rows, observed)
    columns = None
    records = []
    seen = set()
    for row in rows:
        cells = [" ".join(str(c or "").split()) for c in row]
        header = [column_name(c) for c in cells]
        if "product" in header and "price_pen_per_unit" in header:
            columns = header
            if len([x for x in header if x]) != len(set(x for x in header if x)):
                raise DatasetQualityError("Ambiguous or repeated table columns")
            continue
        if columns is None or not any(cells):
            continue
        if len(cells) != len(columns):
            raise DatasetQualityError("Row width differs from header")
        item = {key: value for key, value in zip(columns, cells) if key}
        if not item.get("product"):
            raise DatasetQualityError("Missing product; merged cells need a source adapter")
        unit_text = item.get("unit") or ("kg" if source_id == "sisap_mananero" else "")
        if not unit_text:
            raise DatasetQualityError("Missing original unit")
        unit = parse_unit(unit_text)
        if item.get("equivalence") not in {None, "", ":"}:
            qty = number(item["equivalence"])
            if not qty:
                raise DatasetQualityError("Invalid explicit kilogram equivalence")
            unit = {"unit_qty_kg": qty}
        price = number(item["price_pen_per_unit"])
        if price is not None and price <= 0:
            raise DatasetQualityError("Today's price must be positive or explicitly missing")
        avg = number(item.get("avg_7d"))
        flags = list(unit.get("quality_flags", []))
        if price is not None and avg and abs(price / avg - 1) > 3:
            flags.append("outlier")
        record = PriceRecord(
            observation_date=observed,
            retrieved_at=retrieved_at or datetime.now(UTC),
            source_id=source_id,
            source_url=source_url,
            institution=institution,
            transport="http_insecure" if source_url.startswith("http://") else "https",
            market=item.get("market") or market,
            product=item["product"],
            category=item.get("category"),
            variety_or_brand=item.get("variety_or_brand"),
            unit_original=unit_text,
            unit_qty_kg=unit.get("unit_qty_kg"),
            unit_qty_l=unit.get("unit_qty_l"),
            price_pen_per_unit=price,
            price_pen_per_kg=normalized_price(price, unit.get("unit_qty_kg")),
            price_pen_per_l=normalized_price(price, unit.get("unit_qty_l")),
            price_prev_day=number(item.get("price_prev_day")),
            avg_7d=avg,
            avg_prev_month=number(item.get("avg_prev_month")),
            volume_t=number(item.get("volume_t")),
            is_missing=price is None,
            quality_flags=flags,
            raw_s3_key=raw_s3_key,
            parser_version=PARSER_VERSION,
        )
        key = tuple(dynamo_keys(record).values())
        if key in seen:
            raise DatasetQualityError("Duplicate product/market/unit/variety row")
        seen.add(key)
        records.append(record)
    if not records:
        raise DatasetQualityError("No supported price table found; publication rejected")
    return records


def parse_delimited(
    text, source_id, market, source_url, institution, raw_s3_key, retrieved_at=None
):
    """Local extracted-text fixtures only; production PDF extraction uses table cells."""
    observed = parse_spanish_date(text)
    rows = [line.split("|") for line in text.splitlines() if "|" in line]
    return parse_rows(
        rows, observed, source_id, market, source_url, institution, raw_s3_key, retrieved_at
    )


def parse_pdf(
    payload,
    source_id,
    market,
    source_url,
    institution,
    raw_s3_key,
    retrieved_at=None,
    expected_date=None,
):
    import pdfplumber

    if not payload.startswith(b"%PDF"):
        raise DatasetQualityError("Response is not a PDF")
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        if len(pdf.pages) > 30:
            raise DatasetQualityError("PDF exceeds 30 pages")
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        observed = parse_spanish_date(text)
        if expected_date is not None and observed != expected_date:
            raise DatasetQualityError(
                f"Report date {observed} differs from expected {expected_date}"
            )
        rows = []
        for page in pdf.pages:
            tables = page.extract_tables() or page.extract_tables(
                {"vertical_strategy": "text", "horizontal_strategy": "text"}
            )
            for table in tables:
                rows.extend(table)
    return parse_rows(
        rows, observed, source_id, market, source_url, institution, raw_s3_key, retrieved_at
    )
