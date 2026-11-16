from pathlib import Path

from src.functions.ingest_worker.app import lambda_handler

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sisap_sample.txt"


def test_worker_fetches_and_parses_fixture_without_aws():
    fetched = lambda_handler(
        {
            "action": "fetch",
            "source_id": "sisap_mananero",
            "source_url": "http://example.test/report.pdf",
            "fixture_text": FIXTURE.read_text(),
        },
        None,
    )
    parsed = lambda_handler(
        {
            **fetched,
            "action": "parse",
            "market": "Gran Mercado Mayorista de Lima",
            "institution": "MIDAGRI-DGESEP-DEIA",
        },
        None,
    )
    assert parsed["status"] == "ok"
    assert parsed["rows"] == 2
    assert parsed["missing"] == 1
