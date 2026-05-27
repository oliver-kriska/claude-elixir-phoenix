"""Tests for the multi-model routing-judge dispatch in trigger_scorer.py.

All network/subprocess calls are mocked, so these run without API keys or the
`claude` CLI present (CI-safe). Issue #48, T1.3 Phase 2.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from lab.eval.trigger_scorer import (
    _ask_openai_compatible,
    _parse_skill_lines,
    ask_model,
    provider_for_model,
)


def test_provider_classification():
    # Anthropic CLI path
    assert provider_for_model("claude-haiku-4-5") == "anthropic"
    assert provider_for_model("haiku") == "anthropic"  # alias resolves first
    assert provider_for_model("sonnet") == "anthropic"
    assert provider_for_model("opus") == "anthropic"
    # OpenAI-compatible HTTP path
    assert provider_for_model("gpt-4o-mini") == "openai"
    assert provider_for_model("o3-mini") == "openai"
    assert provider_for_model("qwen2.5-coder") == "openai"
    assert provider_for_model("llama-3.3-70b") == "openai"
    # Unknown ids default to the CLI so existing behavior is preserved
    assert provider_for_model("some-unknown-model") == "anthropic"


def test_parse_skill_lines():
    assert _parse_skill_lines("plan\nwork") == ["plan", "work"]
    assert _parse_skill_lines("- `plan` — best fit\n2) work (maybe)") == ["plan", "work"]
    assert _parse_skill_lines("none") == []
    assert _parse_skill_lines("No skill applies") == []


def test_openai_noop_without_key(monkeypatch):
    """No OPENAI_API_KEY → graceful no-op (so keyless CI just skips)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _ask_openai_compatible("prompt", "gpt-4o-mini") == []


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_openai_parses_mocked_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    body = json.dumps({"choices": [{"message": {"content": "plan\nwork"}}]}).encode()
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResp(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = _ask_openai_compatible("the prompt", "gpt-4o-mini")
    assert out == ["plan", "work"]
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"


def test_openai_honors_custom_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://my-host/v1")
    body = json.dumps({"choices": [{"message": {"content": "none"}}]}).encode()
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResp(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    _ask_openai_compatible("p", "qwen2.5-coder")
    assert captured["url"] == "https://my-host/v1/chat/completions"


def test_openai_swallows_errors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    def boom(req, timeout=None):
        raise RuntimeError("network down")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert _ask_openai_compatible("p", "gpt-4o-mini") == []


def test_ask_model_dispatch(monkeypatch):
    monkeypatch.setattr("lab.eval.trigger_scorer._ask_openai_compatible", lambda sp, m: ["OPENAI"])
    monkeypatch.setattr("lab.eval.trigger_scorer._ask_anthropic_cli", lambda sp, m: ["ANTHROPIC"])
    descs = {"plan": "Plan features"}
    assert ask_model(descs, "x", "gpt-4o-mini") == ["OPENAI"]
    assert ask_model(descs, "x", "claude-haiku-4-5") == ["ANTHROPIC"]
    assert ask_model(descs, "x", "haiku") == ["ANTHROPIC"]
