from datetime import datetime, timezone
from src.common.models import PriceRecord
from src.common.storage import store_records

def lambda_handler(event, context):
    records = [PriceRecord.model_validate(item) for item in event.get("records", [])]
    return {"status": "validated", **store_records(records), "validated_at": datetime.now(timezone.utc).isoformat()}

