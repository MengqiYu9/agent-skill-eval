"""Native CLI adapters. Each attempt receives a fresh workspace and skill package.

The temporary workspace is not an OS security sandbox. Run untrusted suites in
an isolated CI container with platform permissions configured by the operator.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .runner import Completion, RunnerError
from .suite import safe_relative


def parse_native(platform, stdout, latency, model=""):
    try:
        events = [json.loads(stdout)] if platform == "gemini" else [json.loads(line) for line in stdout.splitlines() if line.strip()]
        if not events or any(not isinstance(e, dict) for e in events):
            raise ValueError("expected JSON event objects")
        terminal = None
        text = ""
        usage = {}
        error = None
        actual_model = model
        if platform == "codex":
            for event in events:
                if event.get("type") in ("error", "turn.failed"):
                    error = str(event.get("error") or event.get("message") or event)
                item = event.get("item", {})
                if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                    text = item.get("text", "")
                if event.get("type") == "turn.completed":
                    terminal = event
                    usage = event.get("usage") or {}
            pt, ct = usage.get("input_tokens"), usage.get("output_tokens")
        elif platform == "gemini":
            # JSON mode is a single object; stats vary across CLI versions.
            terminal = events[-1] if "response" in events[-1] or "error" in events[-1] else None
            if terminal:
                text = terminal.get("response", "")
                error = str(terminal["error"]) if terminal.get("error") else None
                models = terminal.get("stats", {}).get("models", {})
                if models:
                    actual_model = ",".join(sorted(models))
                    tokens = [m.get("tokens", {}) for m in models.values()]
                    if all("prompt" in t and "candidates" in t for t in tokens):
                        usage = {"input_tokens": sum(t["prompt"] for t in tokens),
                                 "output_tokens": sum(t["candidates"] + t.get("thoughts", 0) for t in tokens)}
            pt, ct = usage.get("input_tokens"), usage.get("output_tokens")
        else:
            for event in events:
                if event.get("type") == "system":
                    actual_model = event.get("model", actual_model)
                if event.get("type") == "result":
                    terminal = event
            if terminal:
                text = terminal.get("result", "")
                if terminal.get("is_error") or terminal.get("subtype") != "success":
                    error = str(terminal.get("errors") or terminal.get("subtype") or "native execution failed")
                usage = terminal.get("usage") or {}
            pt, ct = usage.get("input_tokens"), usage.get("output_tokens")
        if terminal is None:
            error = error or "native stream ended without a terminal result"
        if not isinstance(text, str):
            raise ValueError("native final result is not text")
        known = type(pt) is int and type(ct) is int and pt >= 0 and ct >= 0
        # Cache pricing is platform/model-specific; do not pretend ordinary token pricing is exact.
        cache_used = any(usage.get(k, 0) for k in ("cache_creation_input_tokens", "cache_read_input_tokens", "cached_input_tokens"))
        return Completion(text, latency, pt if known else 0, ct if known else 0,
                          actual_model, error=error, finish_reason="stop" if not error else "error",
                          events=events, metadata={"usage_known": known, "cost_supported": known and not cache_used,
                                                   "usage_raw": usage, "platform": platform})
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        return Completion("", latency, model=model, error="invalid native output: %s" % exc)


class NativeRunner:
    kind = "native"

    def __init__(self, options):
        self.options = options
        self.model = options.model
        self.platform = options.runner
        self.executable = shutil.which(options.agent_command or {"cursor": "agent"}.get(self.platform, self.platform))
        if not self.executable:
            raise RunnerError("native CLI not installed: %s (use --agent-command)" % self.platform)
        if os.name == "nt" and Path(self.executable).suffix.lower() in (".cmd", ".bat"):
            raise RunnerError("use a native executable wrapper or WSL for Windows CLI batch shims")
        try:
            version = subprocess.run([self.executable, "--version"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=10, check=True)
            self.version = version.stdout.strip() or version.stderr.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise RunnerError("cannot determine CLI version: %s" % exc) from exc

    def command(self, prompt):
        if self.platform == "codex":
            args = ["exec", "--json", "--skip-git-repo-check", "--sandbox", "workspace-write"]
        elif self.platform == "claude":
            args = ["-p", "--output-format", "stream-json", "--verbose"]
        elif self.platform == "gemini":
            args = ["--output-format", "json", "-p"]
        else:
            args = ["-p", "--output-format", "stream-json"]
        # -p consumes the prompt for Gemini; place it before optional flags.
        if self.platform == "gemini":
            args += [prompt]
        if self.model:
            args += ["--model", self.model]
        args += self.options.agent_args
        if self.platform != "gemini":
            args += ["--", prompt]
        return [self.executable] + args

    def execute(self, skill, task):
        started = time.monotonic()
        events = []
        with tempfile.TemporaryDirectory(prefix="skilleval-") as temporary:
            root = Path(temporary)
            if skill.path:
                directory = {"codex": ".agents", "claude": ".claude",
                             "gemini": ".gemini", "cursor": ".cursor"}[self.platform]
                destination = root / directory / "skills" / skill.name
                source = Path(skill.path)
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    destination.mkdir(parents=True)
                    shutil.copy2(source, destination / "SKILL.md")
            for name, content in task.files.items():
                target = root / safe_relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            prompt = task.input
            if skill.path and self.options.invocation == "explicit":
                prompt = "Use the installed skill named %s to complete this task.\n\n%s" % (skill.name, prompt)
            try:
                kwargs = {"cwd": root, "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
                          "stderr": subprocess.PIPE, "text": True, "encoding": "utf-8", "errors": "replace"}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                else:
                    kwargs["start_new_session"] = True
                process = subprocess.Popen(self.command(prompt), **kwargs)
                try:
                    stdout, stderr = process.communicate(timeout=self.options.timeout)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    return Completion("", time.monotonic() - started, error="native execution timed out")
                completion = parse_native(self.platform, stdout, time.monotonic() - started, self.model)
                if process.returncode:
                    completion.error = "native exit %d: %s" % (process.returncode, stderr[:1000])
                completion.metadata.update(cli_version=self.version, exit_code=process.returncode,
                                           invocation=self.options.invocation, workspace_isolation="fresh-directory",
                                           user_configuration="inherited")
                # Only explicitly requested text artifacts are retained. Do not collect credentials or arbitrary files.
                for spec in task.checks:
                    if "artifact" not in spec:
                        continue
                    relative = safe_relative(spec["artifact"])
                    target = root / relative
                    resolved = target.resolve()
                    if root.resolve() not in resolved.parents or target.is_symlink():
                        completion.error = "artifact escapes workspace"
                    elif target.is_file():
                        if target.stat().st_size > 2_000_000:
                            completion.error = "artifact exceeds 2 MB limit"
                        else:
                            completion.artifacts[spec["artifact"]] = target.read_text(encoding="utf-8")
                return completion
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                return Completion("", time.monotonic() - started, error="native runner: %s" % exc)

