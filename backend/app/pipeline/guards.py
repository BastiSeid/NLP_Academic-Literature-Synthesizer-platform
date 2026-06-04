"""Stop-condition exceptions and the guard check run before every agent call
and between stages. Enforces cost cap, kill switch, wall-clock, and max-steps."""
from __future__ import annotations

import time
from ..config import config


class Cancelled(Exception):
    pass


class CostCapExceeded(Exception):
    pass


class WallClockExceeded(Exception):
    pass


class MaxStepsExceeded(Exception):
    pass


class RunContext:
    """Live, non-persisted handle for an in-flight run."""

    def __init__(self, state):
        import threading
        self.state = state
        self.cancel_event = threading.Event()
        self.start_time = time.monotonic()
        self.lock = threading.Lock()

    @property
    def cost_cap(self) -> float:
        override = self.state.params.cost_cap_usd
        return float(override) if override else config.COST_CAP_USD

    def check(self) -> None:
        """Raise the appropriate stop-condition if any ceiling is hit."""
        if self.cancel_event.is_set():
            raise Cancelled("run cancelled via kill switch")
        if self.state.cost_usd > self.cost_cap:
            raise CostCapExceeded(
                f"cost ${self.state.cost_usd:.2f} exceeded cap ${self.cost_cap:.2f}"
            )
        if (time.monotonic() - self.start_time) > config.RUN_TIMEOUT:
            raise WallClockExceeded(f"run exceeded {config.RUN_TIMEOUT}s wall-clock")
        if self.state.steps > config.MAX_STEPS:
            raise MaxStepsExceeded(f"run exceeded {config.MAX_STEPS} steps")

    def charge(self, res) -> None:
        """Account one agent call, then re-check guards (so the cost cap is a
        hard stop the moment it is crossed)."""
        with self.lock:
            self.state.cost_usd = round(self.state.cost_usd + res.cost_usd, 6)
            self.state.tokens_in += res.input_tokens
            self.state.tokens_out += res.output_tokens
            self.state.steps += 1
        self.check()
