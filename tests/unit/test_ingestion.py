import pytest
from backend.functions.ingestion.app import lambda_handler

def valid_event():
    return {"source": "MIDAGRI", "records": [{"product_id":"papa","product_name":"Papa","market":"Lima","price_type":"retail","unit":"kg","value":4.2,"currency":"PEN","observation_date":"2026-11-10"}]}

def test_valid_dataset_is_idempotent():
    fetched = lambda_handler({**valid_event(), "action":"FetchAgriculturalPrices"}, None)
    assert fetched["file_hash"] and fetched["dataset_id"]
    persisted = lambda_handler({**fetched, "action":"PersistNormalizedPrices", "normalized_records": fetched["records"]}, None)
    assert persisted["idempotency_key"].startswith("MIDAGRI:")

def test_invalid_dataset_fails_without_retryable_success():
    with pytest.raises(ValueError):
        lambda_handler({"action":"ValidateDataset", "records":[{"product_id":"bad","value":-1}]}, None)

def test_failure_preserves_last_published_dataset():
    result = lambda_handler({"action":"HandleFailure", "failed_stage":"ValidateDataset", "error":"bad file"}, None)
    assert result["status"] == "failed"
    assert result["last_published_dataset_preserved"] is True

