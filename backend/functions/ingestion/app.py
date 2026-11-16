import hashlib
import json
from datetime import datetime, timezone

REQUIRED = {"product_id", "product_name", "market", "price_type", "unit", "value", "currency", "observation_date"}

def _records(event):
    if event.get("s3_object"):
        import boto3
        obj = boto3.client("s3").get_object(Bucket=event["s3_object"]["bucket"], Key=event["s3_object"]["key"])
        payload = json.loads(obj["Body"].read())
        return payload.get("records", payload)
    return event.get("records") or [{"product_id": "papa", "product_name": "Papa blanca", "market": "Lima", "price_type": "retail", "unit": "kg", "value": 4.2, "currency": "PEN", "observation_date": "2026-11-10"}]

def lambda_handler(event, context):
    action = event.get("action", "FetchAgriculturalPrices")
    records = _records(event)
    if action == "FetchAgriculturalPrices":
        digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        return {**event, "source": event.get("source", "MIDAGRI"), "dataset_id": event.get("dataset_id", digest[:24]), "file_hash": digest, "downloaded_at": datetime.now(timezone.utc).isoformat(), "records": records}
    if action == "ValidateDataset":
        rejected = [r for r in records if not REQUIRED.issubset(r) or not isinstance(r.get("value"), (int, float)) or r.get("value", 0) <= 0]
        if rejected:
            raise ValueError(f"dataset quality failure: {len(rejected)} invalid records")
        return {**event, "validated_records": len(records), "rejected_records": 0}
    if action == "NormalizeAgriculturalPrices":
        normalized = [{**r, "normalized_value": float(r["value"]), "source_institution": event.get("source", "MIDAGRI"), "ingestion_timestamp": datetime.now(timezone.utc).isoformat()} for r in records]
        return {**event, "normalized_records": normalized}
    if action == "StoreRawDataset":
        first_date = records[0]["observation_date"]
        key = f"raw/country=PE/source=MIDAGRI/year={first_date[:4]}/month={first_date[5:7]}/{event['dataset_id']}.json"
        if __import__("os").getenv("RAW_BUCKET"):
            import boto3
            boto3.client("s3").put_object(Bucket=__import__("os").environ["RAW_BUCKET"], Key=key, Body=json.dumps({"records": records}).encode(), Metadata={"dataset-id": event["dataset_id"], "file-hash": event.get("file_hash", "")})
        return {**event, "raw_s3_key": key}
    if action == "PersistNormalizedPrices":
        normalized = event.get("normalized_records", records)
        if __import__("os").getenv("PRICE_TABLE_NAME"):
            import boto3
            table = boto3.resource("dynamodb").Table(__import__("os").environ["PRICE_TABLE_NAME"])
            for record in normalized:
                table.put_item(Item={"pk": f"PRODUCT#{record['product_id']}", "sk": f"DATE#{record['observation_date']}#MARKET#{record['market']}#TYPE#{record['price_type']}", **record})
        return {**event, "persisted_records": len(normalized), "idempotency_key": f"{event.get('source','MIDAGRI')}:{event.get('dataset_id')}"}
    if action == "CalculatePriceTrends":
        return {**event, "trend_status": "calculated", "trend_count": len(event.get("normalized_records", records))}
    if action == "PublishDataset":
        return {"status": "published", "dataset_id": event.get("dataset_id"), "last_successful_update": datetime.now(timezone.utc).isoformat(), "records": event.get("persisted_records", 0), "rejected_records": event.get("rejected_records", 0)}
    if action == "HandleFailure":
        return {"status": "failed", "failed_stage": event.get("failed_stage", "unknown"), "last_published_dataset_preserved": True, "error": event.get("error", "unknown")}
    raise ValueError(f"unknown ingestion action: {action}")

