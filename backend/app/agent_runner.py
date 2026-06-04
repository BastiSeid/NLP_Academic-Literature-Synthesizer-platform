"""Agent runtime: each subagent is a single headless `claude` CLI invocation,
powered by the user's Claude Max subscription. In-CLI tools are disabled so the
agent is pure reasoning over the context we hand it (its tool scope is enforced
deterministically in Python). Returns the text result plus token/cost usage so
the orchestrator can enforce the cost cap.

A subagent therefore gets an ISOLATED context window (a fresh CLI process), a
NARROW tool scope (none in-CLI; data is pre-fetched), and a single responsibility.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .config import config

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentResult:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class AgentError(RuntimeError):
    pass


def _extract_json(text: str) -> str:
    """Best-effort: pull a JSON object/array out of a model response."""
    text = text.strip()
    # fenced ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    # first balanced object/array
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1] or [-1])
    if start == -1:
        return text
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start : end + 1] if end > start else text


def run_agent(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> AgentResult:
    """Run one agent turn via the claude CLI headless. Tools disabled."""
    model = model or config.MODEL
    timeout = timeout or config.AGENT_TIMEOUT
    cmd = [
        config.CLAUDE_BIN,
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--append-system-prompt",
        system_prompt,
        "--allowedTools",
        "",  # reasoning-only: no in-CLI tool access (narrow scope, read-only)
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise AgentError(f"agent timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise AgentError(
            f"claude CLI not found at '{config.CLAUDE_BIN}'. Set LITSYNTH_CLAUDE_BIN."
        ) from e

    if proc.returncode != 0:
        raise AgentError(f"claude CLI exit {proc.returncode}: {proc.stderr[:500]}")

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AgentError(f"could not parse CLI envelope: {proc.stdout[:300]}") from e

    if payload.get("is_error"):
        raise AgentError(f"agent error: {payload.get('result', '')[:300]}")

    usage = payload.get("usage", {})
    return AgentResult(
        text=payload.get("result", ""),
        input_tokens=int(usage.get("input_tokens", 0))
        + int(usage.get("cache_creation_input_tokens", 0))
        + int(usage.get("cache_read_input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        cost_usd=float(payload.get("total_cost_usd", 0.0)),
    )


def run_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    *,
    model: Optional[str] = None,
    cost_sink=None,
) -> T:
    """Run an agent and validate its JSON output against a Pydantic schema.
    Retries once with a stricter instruction on parse/validation failure.
    `cost_sink(AgentResult)` is called for EVERY attempt so the cost cap counts
    failed attempts too."""
    attempt_prompt = user_prompt
    last_err = None
    for attempt in range(2):
        res = run_agent(system_prompt, attempt_prompt, model=model)
        if cost_sink:
            cost_sink(res)
        raw = _extract_json(res.text)
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            last_err = e
            attempt_prompt = (
                user_prompt
                + "\n\nYOUR PREVIOUS REPLY WAS INVALID. Return ONLY a single JSON "
                f"object matching this schema, no prose, no markdown fences:\n"
                f"{json.dumps(schema.model_json_schema())[:1500]}"
            )
    raise AgentError(f"agent output failed schema {schema.__name__}: {last_err}")
