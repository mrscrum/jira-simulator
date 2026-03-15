## [2026-03-15] Stage 0 — Swap LLM provider from Anthropic to OpenAI
- Assumed the `ai_content.py` integration module (listed in AGENTS.md repo structure) will use OpenAI SDK instead of Anthropic SDK — user confirmed OpenAI as the provider
- Assumed `httpx` remains in the stack for Jira API calls; OpenAI calls may use the `openai` Python SDK directly — to be confirmed during Stage 1 implementation
