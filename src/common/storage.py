import csv
import io
import json
import os
from .models import PriceRecord, dynamo_keys

def store_records(records: list[PriceRecord], dynamodb=None, s3=None) -> dict:
    table_name, curated_bucket = os.getenv("PRICE_TABLE_NAME"), os.getenv("RAW_BUCKET")
    dynamodb = dynamodb or __import__("boto3").resource("dynamodb") if table_name else dynamodb
    s3 = s3 or __import__("boto3").client("s3") if curated_bucket else s3
    for record in records:
        if dynamodb:
            item = {**dynamo_keys(record), **record.model_dump(mode="json")}
            dynamodb.Table(table_name).put_item(Item=item)
    if s3 and records:
        day = records[0].observation_date.isoformat()
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=list(records[0].model_dump(mode="json").keys())); writer.writeheader()
        for record in records: writer.writerow(record.model_dump(mode="json"))
        s3.put_object(Bucket=curated_bucket, Key=f"curated/prices/source={records[0].source_id}/date={day}/part.csv", Body=output.getvalue().encode(), ContentType="text/csv")
    return {"rows": len(records), "missing": sum(record.is_missing for record in records)}

def report(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, sort_keys=True)

