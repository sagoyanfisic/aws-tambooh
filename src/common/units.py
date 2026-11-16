"""Only convert package units with an explicit mass/volume equivalence."""
import re
from decimal import Decimal, ROUND_HALF_UP


def parse_unit(text: str) -> dict:
    value = " ".join(text.lower().split())
    number = r"(\d+(?:[.,]\d+)?)"
    patterns = [
        (rf"{number}\s*pqtes?\.?\s*(?:de\s*)?{number}\s*kg", "packs"),
        (rf"(?:saco\s*(?:de\s*)?)?{number}\s*kg", "kg"),
        (rf"(?:lata\s*(?:de\s*)?)?{number}\s*(?:litros?|l)\b", "l"),
    ]
    for pattern, kind in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            nums = [Decimal(n.replace(",", ".")) for n in match.groups()]
            qty = nums[0] * nums[1] if kind == "packs" else nums[0]
            if qty > 0:
                return {"unit_qty_l" if kind == "l" else "unit_qty_kg": float(qty)}
    if value in {"kg", "kilogramo", "kilogramos"}:
        return {"unit_qty_kg": 1.0}
    if value in {"l", "litro", "litros"}:
        return {"unit_qty_l": 1.0}
    return {"quality_flags": ["unit_unparsed"]}


def normalized_price(price, quantity):
    if price is None or not quantity:
        return None
    return float((Decimal(str(price)) / Decimal(str(quantity))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP))


def price_per_kg(price, unit):
    return normalized_price(price, unit.get("unit_qty_kg"))
