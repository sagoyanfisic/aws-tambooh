# Claude API integration

The dedicated AI Lambda uses Anthropic's official Python SDK and the Messages API. The recommended economical model configured in this repository is `claude-haiku-4-5-20251001`; confirm its current account availability before enabling it. Anthropic documents this model as active at the time of this implementation. [Model lifecycle documentation](https://docs.anthropic.com/en/docs/about-claude/model-deprecations).

Set `ENABLE_AI=true`, `AI_PROVIDER=anthropic`, `CLAUDE_MODEL_ID`, and `ANTHROPIC_SECRET_ID`. Local development may use `ANTHROPIC_API_KEY` from an ignored `.env`; AWS reads the JSON secret through the AI Lambda role. The key never reaches React, API responses, or logs. The adapter caches it per Lambda environment, uses an 8-second timeout, three bounded retries, a 350-token cap, and a deterministic fallback.

