import re
from datetime import date

MONTHS = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,"agosto":8,"setiembre":9,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}

def parse_spanish_date(text: str) -> date:
    match = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:del|de)\s+(\d{4})", text.lower())
    if not match:
        raise ValueError(f"Spanish date not found: {text[:80]}")
    month = MONTHS.get(match.group(2).replace("í", "i"))
    if not month: raise ValueError(f"Unknown month: {match.group(2)}")
    return date(int(match.group(3)), month, int(match.group(1)))

