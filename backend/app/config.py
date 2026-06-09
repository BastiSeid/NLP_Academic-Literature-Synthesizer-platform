"""Environment-driven configuration. All guardrail + runtime knobs live here."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _abspath(p: str) -> str:
    path = Path(p)
    return str(path if path.is_absolute() else (_BACKEND_ROOT / path).resolve())


class Config:
    # Agent runtime
    MODEL: str = os.getenv("LITSYNTH_MODEL", "claude-opus-4-8")
    # Models offered in the per-run picker (env-overridable, comma-separated).
    AVAILABLE_MODELS: list[str] = [
        m.strip()
        for m in os.getenv(
            "LITSYNTH_AVAILABLE_MODELS",
            "claude-opus-4-8,claude-sonnet-4-6,claude-haiku-4-5-20251001",
        ).split(",")
        if m.strip()
    ]
    CLAUDE_BIN: str = os.getenv("LITSYNTH_CLAUDE_BIN", "claude")
    AGENT_TIMEOUT: int = int(os.getenv("LITSYNTH_AGENT_TIMEOUT", "300"))
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()

    # Run guardrails (defaults; per-run params may tighten these)
    COST_CAP_USD: float = float(os.getenv("LITSYNTH_COST_CAP_USD", "40"))
    RUN_TIMEOUT: int = int(os.getenv("LITSYNTH_RUN_TIMEOUT", "3600"))
    MAX_STEPS: int = int(os.getenv("LITSYNTH_MAX_STEPS", "200"))

    # Data sources
    OPENALEX_EMAIL: str = os.getenv("LITSYNTH_OPENALEX_EMAIL", "").strip()
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    # Web grey-literature author recovery: best-effort scrape of each result
    # page's own bibliographic metadata (deterministic, read-only — no model).
    WEB_ENRICH: bool = os.getenv("LITSYNTH_WEB_ENRICH", "1") not in ("0", "false", "False", "")
    WEB_ENRICH_TIMEOUT: float = float(os.getenv("LITSYNTH_WEB_ENRICH_TIMEOUT", "6"))

    # Storage
    DB_PATH: str = _abspath(os.getenv("LITSYNTH_DB_PATH", "./litsynth.db"))
    EXPORT_DIR: str = _abspath(os.getenv("LITSYNTH_EXPORT_DIR", "./exports"))

    USER_AGENT: str = (
        "AcademicLiteratureSynthesizer/1.0 (read-only research tool; "
        "respectful of source rate limits)"
    )


config = Config()
Path(config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
