from backend.common.models.domain import Ingredient, PriceRecord

PRICES = [
    PriceRecord(product_id="papa", product_name="Papa blanca", market="Lima", observation_date="2026-11-10", source_institution="MIDAGRI", source_url="sample://midagri", price_type="retail", unit="kg", original_value=4.2, normalized_value=4.2),
    PriceRecord(product_id="arroz", product_name="Arroz corriente", market="Lima", observation_date="2026-11-10", source_institution="MIDAGRI", source_url="sample://midagri", price_type="retail", unit="kg", original_value=4.8, normalized_value=4.8),
    PriceRecord(product_id="lenteja", product_name="Lenteja", market="Lima", observation_date="2026-11-10", source_institution="MIDAGRI", source_url="sample://midagri", price_type="retail", unit="kg", original_value=7.5, normalized_value=7.5),
    PriceRecord(product_id="pollo", product_name="Pollo", market="Lima", observation_date="2026-11-10", source_institution="MIDAGRI", source_url="sample://midagri", price_type="retail", unit="kg", original_value=12.5, normalized_value=12.5),
    PriceRecord(product_id="zanahoria", product_name="Zanahoria", market="Lima", observation_date="2026-11-10", source_institution="MIDAGRI", source_url="sample://midagri", price_type="retail", unit="kg", original_value=3.0, normalized_value=3.0),
]

def ingredients() -> list[Ingredient]:
    nutrition = {"papa": (77, 2), "arroz": (360, 7), "lenteja": (352, 24), "pollo": (239, 27), "zanahoria": (41, 1)}
    return [Ingredient(product_id=p.product_id, name=p.product_name, quantity_kg=1.0, price_pen_per_kg=p.normalized_value, calories_per_100g=nutrition[p.product_id][0], protein_g_per_100g=nutrition[p.product_id][1]) for p in PRICES]

