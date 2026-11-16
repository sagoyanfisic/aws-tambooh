"""Small, bounded Anthropic Messages API adapter with a deterministic fallback."""
import json
import os
import time
from typing import Any
from pydantic import BaseModel, Field

_secret_cache: str | None = None

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
        raw = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-2")).get_secret_value(SecretId=secret_id)["SecretString"]
        parsed = json.loads(raw)
        _secret_cache = parsed.get("ANTHROPIC_API_KEY", raw)
        return _secret_cache
    except Exception:
        return None

def explain(question: str, facts: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("ENABLE_AI", "false").lower() != "true" or os.getenv("AI_PROVIDER", "anthropic") != "anthropic":
        return fallback_explanation(facts)
    key = _api_key()
    model = os.getenv("CLAUDE_MODEL_ID")
    if not key or not model:
        return fallback_explanation(facts)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=8.0, max_retries=0)
        prompt = {"question": question[:2000], "verified_facts": facts, "rules": ["Use only supplied facts", "Never invent prices, nutrition, exchange rates, inventories, or forecasts", "Do not add ingredients to a shopping list", "Call simulations hypothetical"]}
        for attempt in range(3):
            try:
                result = client.messages.create(model=model, max_tokens=350, temperature=0.2, system="You are TamBooh's grounded food-planning explainer. Return plain text only.", messages=[{"role": "user", "content": json.dumps(prompt)}])
                text = "".join(getattr(block, "text", "") for block in result.content).strip()
                return ClaudeExplanation(answer=text, provider="anthropic", cited_facts=[str(k) for k in facts.keys()]).model_dump()
            except Exception:
                if attempt < 2:
                    time.sleep(0.15 * (2 ** attempt))
    except Exception:
        pass
    return fallback_explanation(facts)

def fallback_explanation(facts: dict[str, Any]) -> dict[str, Any]:
    total = facts.get("total_usd")
    amount = f"${total:.2f}" if isinstance(total, (int, float)) else "the validated total"
    return ClaudeExplanation(answer=f"This plan uses validated application data and totals {amount}. Simulated changes are not forecasts; prices and quantities remain determined by TamBooh's source data and calculation services.", provider="deterministic-fallback", cited_facts=list(facts.keys())).model_dump()

