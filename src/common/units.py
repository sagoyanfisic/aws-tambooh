import re

def parse_unit(text: str) -> dict:
    value = " ".join(text.strip().lower().split())
    patterns = [
        (r"(?:saco de )?(\d+(?:[.,]\d+)?)\s*kg", "kg"),
        (r"lata de (\d+(?:[.,]\d+)?)\s*l", "l"),
        (r"caja de (\d+(?:[.,]\d+)?)\s*bot", "bot"),
        (r"(\d+(?:[.,]\d+)?)\s*pqtes?\.?(?: de)?\s*(\d+(?:[.,]\d+)?)\s*kg", "packs"),
        (r"docena", "count12"), (r"ciento", "count100"), (r"atado", "count1"), (r"kg|kilogramo", "kg"),
    ]
    for pattern, kind in patterns:
        match = re.search(pattern, value)
        if not match:
            continue
        nums = [float(x.replace(",", ".")) for x in match.groups() if x]
        if kind == "kg": return {"unit_qty_kg": nums[-1] if nums else 1.0}
        if kind == "l": return {"unit_qty_l": nums[-1]}
        if kind == "packs": return {"unit_qty_kg": nums[0] * nums[1]}
        if kind == "bot": return {"quality_flags": ["unit_unparsed"]}
        if kind == "count12": return {"quality_flags": ["unit_unparsed"]}
        if kind == "count100": return {"quality_flags": ["unit_unparsed"]}
        return {"quality_flags": ["unit_unparsed"]}
    return {"quality_flags": ["unit_unparsed"]}

def price_per_kg(price: float | None, unit: dict) -> float | None:
    qty = unit.get("unit_qty_kg")
    return round(price / qty, 4) if price is not None and qty else None

