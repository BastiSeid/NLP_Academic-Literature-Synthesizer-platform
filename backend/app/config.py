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
    CLAUDE_BIN: str = os.getenv("LITSYNTH_CLAUDE_BIN", "claude")
    AGENT_TIMEOUT: int = int(os.getenv("LITSYNTH_AGENT_TIMEOUT", "300"))
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "").strip()

    # Run guardrails (defaults; per-run params may tighten these)
    COST_CAP_USD: float = float(os.getenv("LITSYNTH_COST_CAP_USD", "40"))
    RUN_TIMEOUT: int = int(os.getenv("LITSYNTH_RUN_TIMEOUT", "3600"))
    MAX_STEPS: int = int(os.getenv("LITSYNTH_MAX_STEPS", "200"))
    MAX_VERIFY_ROUNDS: int = int(os.getenv("LITSYNTH_MAX_VERIFY_ROUNDS", "2"))

    # Data sources
    OPENALEX_EMAIL: str = os.getenv("LITSYNTH_OPENALEX_EMAIL", "").strip()
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()

    # Storage
    DB_PATH: str = _abspath(os.getenv("LITSYNTH_DB_PATH", "./litsynth.db"))
    EXPORT_DIR: str = _abspath(os.getenv("LITSYNTH_EXPORT_DIR", "./exports"))

    USER_AGENT: str = (
        "AcademicLiteratureSynthesizer/1.0 (read-only research tool; "
        "respectful of source rate limits)"
    )


config = Config()
Path(config.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
