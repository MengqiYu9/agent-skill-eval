# -*- coding: utf-8 -*-
"""Runners: how a skill gets executed against one task.

`LLMRunner` talks to any OpenAI-compatible chat-completions endpoint over
stdlib urllib (no SDK dependency). `MockRunner` replays recorded outputs so the
suite can run in CI without a key and without spending money.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    latency_s: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    error: str | None = None
    finish_reason: str = ""
    reasoning_chars: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class RunnerError(RuntimeError):
    pass


def empty_content_error(finish_reason: str, reasoning_chars: int, max_tokens: int) -> str:
    """Explain an empty content field instead of silently scoring it as a bad answer."""
    if finish_reason == "length":
        return ("empty content: the model spent all %d tokens before writing an answer "
                "(finish_reason=length, %d reasoning chars) — raise --max-tokens"
                % (max_tokens, reasoning_chars))
    return ("empty content: finish_reason=%s, %d reasoning chars, max_tokens=%d"
            % (finish_reason or "?", reasoning_chars, max_tokens))


class LLMRunner:
    kind = "llm"

    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.0,
                 max_tokens: int = 4096, timeout: int = 180):
        if not api_key:
            raise RunnerError("no API key: pass --api-key, set SKILLEVAL_API_KEY/DEEPSEEK_API_KEY, "
                              "or point --env-file at a .env that has one")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, system: str, user: str) -> Completion:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.api_key},
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            return Completion("", time.time() - started, model=self.model,
                              error="HTTP %s: %s" % (exc.code, detail))
        except Exception as exc:
            return Completion("", time.time() - started, model=self.model,
                              error="%s: %s" % (type(exc).__name__, exc))

        latency = time.time() - started
        try:
            choice = payload["choices"][0]
            message = choice.get("message") or {}
            text = message.get("content") or ""
            reasoning = message.get("reasoning_content") or choice.get("reasoning_content") or ""
            finish = choice.get("finish_reason") or ""
        except Exception:
            return Completion("", latency, model=self.model,
                              error="unexpected response shape: %s" % json.dumps(payload)[:400])
        usage = payload.get("usage") or {}
        completion = Completion(text, latency, usage.get("prompt_tokens", 0),
                                usage.get("completion_tokens", 0), payload.get("model", self.model),
                                finish_reason=finish, reasoning_chars=len(reasoning))
        # An empty answer is a result, not a crash — but it must never look like "the model said nothing
        # useful" without a reason. The usual cause is a token cap consumed by reasoning tokens.
        if not text.strip():
            completion.error = empty_content_error(finish, completion.reasoning_chars, self.max_tokens)
        return completion


class MockRunner:
    """Replays fixtures keyed by '<skill_id>::<task_id>' (or '<task_id>')."""

    kind = "mock"

    def __init__(self, fixtures_path: str | None):
        self.fixtures = {}
        if fixtures_path and os.path.exists(fixtures_path):
            with open(fixtures_path, encoding="utf-8") as fh:
                self.fixtures = json.load(fh)

    def complete(self, system: str, user: str, key: str = "") -> Completion:
        text = self.fixtures.get(key)
        if text is None:
            return Completion("", 0.0, error="no fixture for key %r (mock runner)" % key)
        return Completion(text, 0.0, prompt_tokens=len(system) // 4, completion_tokens=len(text) // 4,
                          model="mock")


def make_runner(options, api_key: str | None):
    if options.runner == "mock":
        return MockRunner(options.mock_outputs)
    return LLMRunner(options.base_url, api_key or "", options.model, options.temperature,
                     options.max_tokens, options.timeout)
