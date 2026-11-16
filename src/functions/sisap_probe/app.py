"""Optional network probe for running in AWS us-east-1 without storing data."""
from src.functions.ingest_worker.app import lambda_handler as ingest_handler

def lambda_handler(event, context):
    return ingest_handler({"action": "fetch", "source_id": "sisap_mananero"}, context)
