from datetime import datetime, timezone
from .dates import parse_spanish_date
from .models import PriceRecord
from .units import parse_unit, price_per_kg

def number(value: str) -> float | None:
    value = value.strip().replace("S/", "").replace(",", ".")
    if not value or value == ":": return None
    try: return float(value)
    except ValueError: return None

def parse_delimited(text: str, source_id: str, market: str, source_url: str, institution: str, raw_s3_key: str) -> list[PriceRecord]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    observed = parse_spanish_date(" ".join(lines[:4]))
    records = []
    for line in lines:
        if line.lower().startswith(("fecha", "mercado", "producto", "categoría", "categoria")): continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3: continue
        if source_id == "sisap_mananero" and len(parts) >= 3:
            row_market, product, price_text = parts[0], parts[1], parts[2]
            unit_text = "kg"
            market = row_market or market
        else:
            product, unit_text, price_text = parts[0], parts[1], parts[2]
        price = number(price_text)
        unit = parse_unit(unit_text)
        flags = list(unit.get("quality_flags", []))
        avg7 = number(parts[3]) if len(parts) > 3 else None
        if avg7 and price and avg7 > 0 and abs(price / avg7 - 1) > 3: flags.append("outlier")
        records.append(PriceRecord(observation_date=observed, retrieved_at=datetime.now(timezone.utc), source_id=source_id, source_url=source_url, institution=institution, transport="http_insecure" if source_url.startswith("http://") else "https", market=market, product=product, unit_original=unit_text, unit_qty_kg=unit.get("unit_qty_kg"), unit_qty_l=unit.get("unit_qty_l"), price_pen_per_unit=price, price_pen_per_kg=price_per_kg(price, unit), avg_7d=avg7, is_missing=price is None, quality_flags=flags, raw_s3_key=raw_s3_key))
    return records

