"""
Global rate governor with token bucket, jitter, adaptive backoff, and circuit breakers.

Shared across all tiers. Enforces "one in-flight YouTube request at a time".
"""

import time
import random
import threading
from typing import Optional
from transcript_engine.store import TranscriptStore
from transcript_engine.errors import BlockedError


class RateGovernor:
    """
    Token-bucket rate limiter with:
    - Configurable capacity + refill rate
    - Full jitter on every delay
    - Adaptive backoff on BLOCKED events
    - Persisted state via TranscriptStore
    """

    def __init__(self, store: TranscriptStore,
                 capacity: int = 10,
                 refill_per_sec: float = 0.05,   # 1 token / 20s ≈ 180/hr
                 base_delay: float = 20.0):
        self.store = store
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.base_delay = base_delay
        self._lock = threading.Lock()
        self._last_check = time.time()

    def _get_tokens(self) -> float:
        return self.store.get_throttle_value("tokens", float(self.capacity))

    def _set_tokens(self, value: float):
        self.store.set_throttle_value("tokens", value)

    def _get_last_block(self) -> float:
        return self.store.get_throttle_value("last_block_ts", 0.0)

    def wait_for_token(self, tier: str = "unknown"):
        """
        Block until a token is available.
        Applies jitter and adaptive backoff.
        """
        with self._lock:
            now = time.time()
            tokens = self._get_tokens()

            # Refill
            elapsed = now - self._last_check
            tokens = min(self.capacity, tokens + elapsed * self.refill_per_sec)
            self._last_check = now

            if tokens >= 1.0:
                self._set_tokens(tokens - 1.0)
                return

            # Need to wait
            deficit = 1.0 - tokens
            wait = deficit / self.refill_per_sec

            # Add jitter (0–60% of base)
            jitter = random.uniform(0, self.base_delay * 0.6)
            total_wait = wait + jitter

            # Adaptive backoff if recently blocked
            last_block = self._get_last_block()
            if last_block and (now - last_block) < 3600:
                total_wait *= 2.0   # double delay after recent block

            print(f"[governor] Tier {tier}: waiting {total_wait:.1f}s for rate limit")
            time.sleep(total_wait)

            self._set_tokens(0.0)

    def record_block(self, tier: str):
        """Called when a BLOCKED error occurs. Triggers backoff and breaker."""
        self.store.set_throttle_value("last_block_ts", time.time())
        self.store.record_block(tier, cooldown_minutes=45)
        # Immediately open circuit for this tier
        print(f"[governor] BLOCK detected on tier {tier} — circuit breaker opened for 45 min")

    def is_tier_blocked(self, tier: str) -> bool:
        return self.store.is_circuit_open(tier)