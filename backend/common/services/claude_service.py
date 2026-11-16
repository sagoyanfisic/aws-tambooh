"""Small, bounded Anthropic Messages API adapter with a deterministic fallback."""

import json
import logging
import os
import time
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, Field

_secret_cache: str | None = None
logger = logging.getLogger(__name__)


class ClaudeExplanation(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    provider: str
    grounded: bool = True
    cited_facts: list[str] = []


def _api_key() -> str | None:
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    local_key = os.getenv("ANTHROPIC_API_KEY")
    if local_key:
        _secret_cache = local_key
        return local_key
    secret_id = os.getenv("ANTHROPIC_SECRET_ID")
    if not secret_id:
        return None
    try:
        import boto3

        raw = boto3.client(
            "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-2")
        ).get_secret_value(SecretId=secret_id)["SecretString"]
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("ANTHROPIC_API_KEY"), str):
            raise ValueError("Invalid secret format")
        _secret_cache = parsed["ANTHROPIC_API_KEY"].strip() or None
        return _secret_cache
    except (BotoCoreError, ClientError, ValueError, KeyError, TypeError) as exc:
        logger.warning("anthropic_secret_unavailable", extra={"error_type": type(exc).__name__})
        return None


def explain(question: str, facts: dict[str, Any]) -> dict[str, Any]:
    if (
        os.getenv("ENABLE_AI", "false").lower() != "true"
        or os.getenv("AI_PROVIDER", "anthropic") != "anthropic"
    ):
        return fallback_explanation(facts)
    key = _api_key()
    model = os.getenv("CLAUDE_MODEL_ID")
    if not key or not model:
        return fallback_explanation(facts)
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic_sdk_unavailable")
        return fallback_explanation(facts)
    prompt = {
        "question": question[:2000],
        "verified_facts": facts,
        "rules": [
            "Use only supplied facts",
            "Never invent prices, nutrition, exchange rates, inventories, or forecasts",
            "Do not add ingredients to a shopping list",
            "Call simulations hypothetical",
        ],
    }
    try:
        content = json.dumps(prompt, allow_nan=False)
        with anthropic.Anthropic(api_key=key, timeout=8.0, max_retries=0) as client:
            for attempt in range(3):
                try:
                    result = client.messages.create(
                        model=model,
                        max_tokens=350,
                        temperature=0.2,
                        system="You are TamBooh's grounded food-planning explainer. Return plain text only.",
                        messages=[{"role": "user", "content": content}],
                    )
                    text = "".join(getattr(block, "text", "") for block in result.content).strip()
                    return ClaudeExplanation(
                        answer=text, provider="anthropic", cited_facts=list(facts)
                    ).model_dump()
                except anthropic.APIError as exc:
                    status = getattr(exc, "status_code", None)
                    logger.warning(
                        "anthropic_request_failed",
                        extra={"error_type": type(exc).__name__, "status_code": status},
                    )
                    retryable = (
                        isinstance(exc, anthropic.APIConnectionError)
                        or status == 429
                        or (isinstance(status, int) and status >= 500)
                    )
                    if not retryable or attempt == 2:
                        break
                    time.sleep(0.15 * (2**attempt))
    except (ValueError, TypeError, AttributeError) as exc:
        logger.warning(
            "anthropic_invalid_response_or_configuration", extra={"error_type": type(exc).__name__}
        )
    return fallback_explanation(facts)


def fallback_explanation(facts: dict[str, Any]) -> dict[str, Any]:
    total = facts.get("total_usd")
    amount = f"${total:.2f}" if isinstance(total, (int, float)) else "the validated total"
    return ClaudeExplanation(
        answer=f"This plan uses validated application data and totals {amount}. Simulated changes are not forecasts; prices and quantities remain determined by TamBooh's source data and calculation services.",
        provider="deterministic-fallback",
        cited_facts=list(facts.keys()),
    ).model_dump()
