import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from backend.common.services import claude_service


class SDKError(Exception):
    def __init__(self, status_code=None):
        self.status_code = status_code


class ConnectionFailure(SDKError):
    pass


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setenv("ENABLE_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("CLAUDE_MODEL_ID", "configured-model")
    monkeypatch.setattr(claude_service, "_api_key", lambda: "test-only-value")
    monkeypatch.setattr(claude_service.time, "sleep", Mock())
    client = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        SimpleNamespace(Anthropic=factory, APIError=SDKError, APIConnectionError=ConnectionFailure),
    )
    return client, factory


def test_claude_success_and_client_cleanup(sdk):
    client, factory = sdk
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="Use the supplied ingredients.")]
    )
    result = claude_service.explain("Why?", {"total_usd": 10})
    assert result["provider"] == "anthropic"
    assert result["cited_facts"] == ["total_usd"]
    assert factory.call_args.kwargs["max_retries"] == 0
    assert client.messages.create.call_args.kwargs["max_tokens"] == 350
    factory.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("error", [ConnectionFailure(), SDKError(429), SDKError(503)])
def test_transient_errors_have_bounded_attempts_and_fallback(sdk, error):
    client, _factory = sdk
    client.messages.create.side_effect = error
    result = claude_service.explain("Why?", {"total_usd": 10})
    assert result["provider"] == "deterministic-fallback"
    assert client.messages.create.call_count == 3
    assert claude_service.time.sleep.call_count == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_permanent_api_errors_do_not_retry(sdk, status):
    client, _factory = sdk
    client.messages.create.side_effect = SDKError(status)
    assert claude_service.explain("Why?", {})["provider"] == "deterministic-fallback"
    assert client.messages.create.call_count == 1
    claude_service.time.sleep.assert_not_called()


def test_empty_response_falls_back_without_retry(sdk):
    client, _factory = sdk
    client.messages.create.return_value = SimpleNamespace(content=[])
    assert claude_service.explain("Why?", {})["provider"] == "deterministic-fallback"
    assert client.messages.create.call_count == 1


def test_malformed_secret_does_not_log_its_value(monkeypatch, caplog):
    import boto3

    monkeypatch.setattr(claude_service, "_secret_cache", None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_SECRET_ID", "test-secret-id")
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": '["sensitive-test-value"]'}
    monkeypatch.setattr(boto3, "client", Mock(return_value=client))
    assert claude_service._api_key() is None
    assert "anthropic_secret_unavailable" in caplog.text
    assert "sensitive-test-value" not in caplog.text


def test_disabled_ai_falls_back(monkeypatch):
    monkeypatch.setenv("ENABLE_AI", "false")
    from backend.common.services.claude_service import explain

    result = explain("Why?", {"total_usd": 10})
    assert result["provider"] == "deterministic-fallback"
    assert "$10.00" in result["answer"]


def test_missing_secret_falls_back(monkeypatch):
    monkeypatch.setenv("ENABLE_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_SECRET_ID", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL_ID", "claude-haiku-4-5-20251001")
    from backend.common.services.claude_service import explain

    assert explain("Why?", {})["provider"] == "deterministic-fallback"
