"""The multi-provider client: request settings, prompt caps and cost (no API calls)."""

import pytest

from auditor import config, llm


def test_reasoning_settings_per_provider(monkeypatch):
    assert llm.Backend("groq", "openai/gpt-oss-120b", api_key="k", effort="low").extra_body() == {"reasoning_effort": "low"}
    assert llm.Backend("groq", "qwen/qwen3.8-27b", api_key="k").extra_body() == {"reasoning_format": "hidden"}
    assert llm.Backend("openrouter", "openai/gpt-oss-120b", api_key="k", effort="high").extra_body() == {
        "reasoning": {"effort": "high"}
    }
    assert llm.Backend("openai", "gpt-5-mini", api_key="k").extra_body() == {"reasoning_effort": "medium"}
    assert llm.Backend("openai", "gpt-4.1-mini", api_key="k").extra_body() == {}


def test_missing_key_names_the_env_var(monkeypatch):
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TOGETHER_API_KEY"):
        llm.Backend("together", "openai/gpt-oss-120b")


def test_prompt_cap_defaults_per_provider(monkeypatch):
    monkeypatch.setattr(config, "MAX_PROMPT_TOKENS", None)
    assert llm.Backend("groq", "openai/gpt-oss-120b", api_key="k").max_prompt_tokens == 6500
    assert llm.Backend("openai", "gpt-5-mini", api_key="k").max_prompt_tokens == 0
    monkeypatch.setattr(config, "MAX_PROMPT_TOKENS", 0)
    assert llm.Backend("groq", "openai/gpt-oss-120b", api_key="k").max_prompt_tokens == 0


def test_usage_cost_uses_model_prices():
    u = llm.Usage(calls=1, input_tokens=1_000_000, output_tokens=100_000)
    assert u.cost("openai/gpt-oss-120b") == pytest.approx(0.15 + 0.06)
    assert u.cost("unknown/model") == 0.0
    assert u.to_dict("gpt-5-mini")["cost_usd"] == pytest.approx(0.25 + 0.2)


def test_strict_function_tool_shape():
    tool = llm.function_tool("submit", "Submit.", {"type": "object", "properties": {}, "required": [],
                                                    "additionalProperties": False})
    assert tool["function"]["strict"] is True and tool["function"]["name"] == "submit"
    assert llm.force("submit") == {"type": "function", "function": {"name": "submit"}}
