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

