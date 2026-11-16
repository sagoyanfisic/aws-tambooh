"""Immutable dataset snapshots followed by one atomic active-pointer update."""
import csv
import hashlib
import io
import json
import os
from decimal import Decimal
from datetime import datetime, timezone

from .models import PriceRecord, dynamo_keys
from .parsers import PARSER_VERSION


class TransientStorageError(RuntimeError):
    """Retryable AWS storage failure; validation errors use a different exception."""


def decimal_item(item):
    return json.loads(json.dumps(item), parse_float=Decimal)


def snapshot_id(sha256):
    return hashlib.sha256(f"{sha256}:{PARSER_VERSION}".encode()).hexdigest()


def active_dataset(table, source_id):
    return table.get_item(Key={"pk": "DATASETS", "sk": f"SOURCE#{source_id}"},
                          ConsistentRead=True).get("Item")


def store_records(records: list[PriceRecord], dynamodb=None, s3=None, sha256=None) -> dict:
    if not records:
        raise ValueError("Cannot publish an empty dataset")
    source, day = records[0].source_id, records[0].observation_date.isoformat()
    if any(r.source_id != source or r.observation_date.isoformat() != day for r in records):
        raise ValueError("A publication must contain one source and one observation date")
    keys = [tuple(dynamo_keys(r).values()) for r in records]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate record identity")
    result = {"rows": len(records), "missing": sum(r.is_missing for r in records)}
    table_name, bucket = os.getenv("PRICE_TABLE_NAME"), os.getenv("RAW_BUCKET")
    if not table_name and not bucket:
        return {**result, "publication": "local_only"}
    if not table_name or not bucket:
        raise ValueError("Both PRICE_TABLE_NAME and RAW_BUCKET are required for publication")
    import boto3
    table = (dynamodb or boto3.resource("dynamodb")).Table(table_name)
    s3 = s3 or boto3.client("s3")
    if not sha256:
        raise ValueError("Source hash required for publication")
    version = snapshot_id(sha256)
    previous = active_dataset(table, source)
    if previous and previous["dataset_id"] == version:
        return {**result, "publication": "unchanged", "dataset_id": version}
    retrieved = records[0].retrieved_at.isoformat()
    historical = previous and (day < previous["observation_date"] or
                              (day == previous["observation_date"] and retrieved < previous["retrieved_at"]))
    # Historical versions have distinct keys. Failed writes never change the active pointer.
    for record in records:
        item = {**dynamo_keys(record, version), **record.model_dump(mode="json"),
                "dataset_id": version}
        table.put_item(Item=decimal_item(item))
    prefix = f"curated/prices/source={source}/date={day}/version={version}"
    values = [record.model_dump(mode="json") for record in records]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(values[0]))
    writer.writeheader()
    writer.writerows(values)
    s3.put_object(Bucket=bucket, Key=f"{prefix}/part.csv", Body=output.getvalue().encode(),
                  ContentType="text/csv")
    snapshot_key = f"{prefix}/records.json"
    s3.put_object(Bucket=bucket, Key=snapshot_key, Body=json.dumps(values).encode(),
                  ContentType="application/json")
    if historical:
        return {**result, "publication": "historical_only", "dataset_id": version}
    manifest = {"pk": "DATASETS", "sk": f"SOURCE#{source}", "source_id": source,
                "dataset_id": version, "sha256": sha256, "parser_version": PARSER_VERSION,
                "observation_date": day, "retrieved_at": retrieved,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "snapshot_key": snapshot_key, **result}
    # Compare-and-swap: another execution cannot silently replace a newer publication.
    kwargs = {"ConditionExpression": "attribute_not_exists(dataset_id)"}
    if previous:
        kwargs = {"ConditionExpression": "dataset_id = :previous",
                  "ExpressionAttributeValues": {":previous": previous["dataset_id"]}}
    table.put_item(Item=manifest, **kwargs)
    return {**result, "publication": "published", "dataset_id": version}


def load_published(table, s3, bucket):
    """Strongly consistent pointers + complete S3 snapshots; no scan of staged rows."""
    from boto3.dynamodb.conditions import Key
    manifests = []
    kwargs = {"KeyConditionExpression": Key("pk").eq("DATASETS"), "ConsistentRead": True}
    while True:
        page = table.query(**kwargs)
        manifests.extend(page.get("Items", []))
        if not page.get("LastEvaluatedKey"):
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    records = []
    for manifest in manifests:
        key = manifest["snapshot_key"]
        if not key.startswith("curated/prices/"):
            raise ValueError("Invalid published snapshot reference")
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        records.extend(PriceRecord.model_validate(item) for item in json.loads(body))
    return records
