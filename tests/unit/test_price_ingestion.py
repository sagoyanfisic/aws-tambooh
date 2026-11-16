from pathlib import Path
from src.common.parsers import parse_delimited
from src.common.units import parse_unit

FIXTURES = Path(__file__).parents[1] / "fixtures"

def parse(name, source):
    return parse_delimited((FIXTURES / name).read_text(), source, "Lima", "http://example.test", "MIDAGRI-DGESEP-DEIA", "raw/test")

def test_sisap_columns_date_and_missing_value():
    records = parse("sisap_sample.txt", "sisap_mananero")
    assert records[0].observation_date.isoformat() == "2026-11-14"
    assert records[0].price_pen_per_kg == 1.8
    assert records[1].is_missing is True

def test_units_and_price_conversion():
    record = parse("gmml_sample.txt", "gmml_ingreso")[0]
    assert record.unit_qty_kg == 50
    assert record.price_pen_per_kg == 1.8

def test_outlier_flag():
    records = parse("sisap_sample.txt", "sisap_mananero")
    assert "outlier" not in records[0].quality_flags
    assert parse_unit("caja de 12 Bot.")["quality_flags"] == ["unit_unparsed"]

