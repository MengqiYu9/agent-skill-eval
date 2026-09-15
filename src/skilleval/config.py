# -*- coding: utf-8 -*-
"""Configuration, env/key resolution and pricing table handling."""
from __future__ import annotations

import json
import os
import math
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"

KEY_ENV_NAMES = ("SKILLEVAL_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")


def load_dotenv_key(path: str | None, names=KEY_ENV_NAMES) -> str | None:
    """Read a single key from a .env file without printing or exposing it."""
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in names:
                return v.strip().strip('"').strip("'")
    return None


def resolve_api_key(explicit: str | None = None, env_file: str | None = None):
    """Return (key, where_it_came_from). Never logs the key itself."""
    if explicit:
        return explicit, "--api-key"
    for name in KEY_ENV_NAMES:
        if os.environ.get(name):
            return os.environ[name], "env:%s" % name
    key = load_dotenv_key(env_file)
    if key:
        return key, "env_file:%s" % os.path.basename(env_file or "")
    return None, None


@dataclass
class Prices:
    """USD per 1M tokens. Empty by default: token counts are measured, prices are not assumed."""

    input_per_mtok: float | None = None
    output_per_mtok: float | None = None

    @classmethod
    def load(cls, path: str | None, model: str | None = None) -> "Prices":
        if not path:
            return cls()
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        entry = data.get(model or "", data.get("default", data))
        values = [entry.get("input_per_mtok"), entry.get("output_per_mtok")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("prices require finite nonnegative input_per_mtok and output_per_mtok")
        return cls(*values)

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float | None:
        if self.input_per_mtok is None or self.output_per_mtok is None:
            return None
        return (prompt_tokens * self.input_per_mtok + completion_tokens * self.output_per_mtok) / 1e6


@dataclass
class RunOptions:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 180
    runner: str = "llm"          # llm | mock
    judge: bool = True
    judge_model: str | None = None
    judge_fail_under: float | None = None
    mock_outputs: str | None = None
    api_key: str | None = None
    env_file: str | None = None
    prices_file: str | None = None
    repeats: int = 1
    fail_under: float | None = None
    max_regression: float = 0.0
    baseline: str | None = None
    save_baseline: str | None = None
    out_dir: str = "reports"
    quiet: bool = False
    tags: list[str] = field(default_factory=list)
    baseline_skill: str | None = None
    allow_legacy_baseline: bool = False
    compare_first: bool = False
    no_skill: bool = False
    agent_command: str | None = None
    agent_args: list[str] = field(default_factory=list)
    invocation: str = "explicit"
    max_cost: float | None = None
    max_latency: float | None = None
