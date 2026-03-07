"""API balance and usage tracking for Anthropic API calls.

Tracks token consumption and cost per API call, persists data to JSON,
and provides balance info for Discord commands.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Pricing per million tokens (as of 2025)
PRICING = {
    "input": {
        "sonnet": 3.00,   # claude-sonnet-* family
        "haiku":  0.80,   # claude-haiku-* family
        "opus":   15.00,  # claude-opus-* family
        "default": 3.00,
    },
    "output": {
        "sonnet": 15.00,
        "haiku":  4.00,
        "opus":   75.00,
        "default": 15.00,
    },
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BALANCE_FILE = os.path.join(DATA_DIR, "balance_data.json")

# Warn in console when balance drops below this
LOW_BALANCE_THRESHOLD = 5.00


def _model_family(model: str) -> str:
    """Map a model ID string to a pricing family key."""
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    return "default"


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate dollar cost for a single API call."""
    family = _model_family(model)
    input_cost  = (input_tokens  / 1_000_000) * PRICING["input"].get(family,  PRICING["input"]["default"])
    output_cost = (output_tokens / 1_000_000) * PRICING["output"].get(family, PRICING["output"]["default"])
    return input_cost + output_cost


class BalanceTracker:
    """Tracks Anthropic API usage and estimated dollar balance."""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._data = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if os.path.exists(BALANCE_FILE):
            try:
                with open(BALANCE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning("balance_data.json corrupt or unreadable — starting fresh.")
        return {
            "initial_balance": 0.0,
            "total_spent": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "sessions": [],          # last N sessions kept
        }

    def _save(self):
        try:
            with open(BALANCE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save balance data: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_initial_balance(self, amount: float):
        """Set (or reset) the initial balance. Does not affect spent tracking."""
        self._data["initial_balance"] = round(float(amount), 4)
        self._save()

    def add_funds(self, amount: float):
        """Add funds to the balance (e.g. after topping up)."""
        self._data["initial_balance"] = round(
            self._data["initial_balance"] + float(amount), 4
        )
        self._save()

    def track_usage(self, model: str, input_tokens: int, output_tokens: int,
                    session_id: str = ""):
        """Record a completed API call and deduct its cost from the balance."""
        call_cost = _cost(model, input_tokens, output_tokens)

        self._data["total_spent"]         = round(self._data["total_spent"] + call_cost, 6)
        self._data["total_input_tokens"]  += input_tokens
        self._data["total_output_tokens"] += output_tokens

        # Keep last 50 sessions in memory
        session_record = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "model":   model,
            "in":      input_tokens,
            "out":     output_tokens,
            "cost":    round(call_cost, 6),
            "session": session_id,
        }
        self._data["sessions"].append(session_record)
        if len(self._data["sessions"]) > 50:
            self._data["sessions"] = self._data["sessions"][-50:]

        self._save()

        # Console warning when low
        if self.needs_refill(LOW_BALANCE_THRESHOLD):
            logger.warning(
                f"[BALANCE] Low balance warning! "
                f"Remaining: ${self.current_balance:.2f} "
                f"(threshold: ${LOW_BALANCE_THRESHOLD:.2f})"
            )

    def get_balance_info(self) -> dict:
        """Return a summary dict suitable for Discord display."""
        initial  = self._data["initial_balance"]
        spent    = self._data["total_spent"]
        current  = max(0.0, initial - spent)
        pct      = (current / initial * 100) if initial > 0 else 0.0

        total_in  = self._data["total_input_tokens"]
        total_out = self._data["total_output_tokens"]

        # Estimate average cost per request from recent sessions
        sessions = self._data["sessions"]
        if sessions:
            last_10 = sessions[-10:]
            avg_cost = sum(s["cost"] for s in last_10) / len(last_10)
            est_remaining = int(current / avg_cost) if avg_cost > 0 else 0
        else:
            avg_cost = 0.0
            est_remaining = 0

        return {
            "initial_balance":        round(initial, 2),
            "current_balance":        round(current, 4),
            "total_spent":            round(spent, 4),
            "pct_remaining":          round(pct, 1),
            "total_input_tokens":     total_in,
            "total_output_tokens":    total_out,
            "total_tokens":           total_in + total_out,
            "estimated_remaining_requests": est_remaining,
            "avg_cost_per_request":   round(avg_cost, 6),
            "session_count":          len(sessions),
            "low_balance":            current < LOW_BALANCE_THRESHOLD,
            "uninitialized":          initial == 0.0,
        }

    @property
    def current_balance(self) -> float:
        return max(0.0, self._data["initial_balance"] - self._data["total_spent"])

    def needs_refill(self, threshold: float = LOW_BALANCE_THRESHOLD) -> bool:
        return 0 < self._data["initial_balance"] and self.current_balance < threshold

    def recent_sessions(self, count: int = 10) -> list[dict]:
        """Return the N most recent session records, newest first."""
        return list(reversed(self._data["sessions"][-count:]))
