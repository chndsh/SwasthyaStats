import time
from typing import List, Dict, Optional, Literal


class KeyState:
    def __init__(self, key: str, label: str):
        self.key = key
        self.label = label
        self.is_bad = False  # e.g., 401/403 auth failure
        self.rate_limited_until = 0.0  # timestamp when 429 expires
        self.failure_count = 0

    @property
    def is_available(self) -> bool:
        if self.is_bad:
            return False
        return time.time() >= self.rate_limited_until


class KeyPool:
    def __init__(self, keys: List[Dict[str, str]], strategy: Literal["failover", "round_robin"] = "failover"):
        self.keys = [KeyState(k["key"], k.get("label", f"key-{i+1}")) for i, k in enumerate(keys)]
        self.strategy = strategy
        self._round_robin_idx = 0

    def get_key(self) -> Optional[KeyState]:
        now = time.time()
        available = [k for k in self.keys if k.is_available]
        if not available:
            return None

        if self.strategy == "failover":
            return available[0]
        else:
            self._round_robin_idx = (self._round_robin_idx + 1) % len(available)
            return available[self._round_robin_idx]

    def mark_rate_limited(self, key_str: str, retry_after_s: float = 60.0):
        for k in self.keys:
            if k.key == key_str:
                k.rate_limited_until = time.time() + max(retry_after_s, 5.0)
                k.failure_count += 1
                break

    def mark_bad_auth(self, key_str: str):
        for k in self.keys:
            if k.key == key_str:
                k.is_bad = True
                break

    def mark_success(self, key_str: str):
        for k in self.keys:
            if k.key == key_str:
                k.failure_count = 0
                k.rate_limited_until = 0.0
                break

    @property
    def has_healthy_keys(self) -> bool:
        return any(k.is_available for k in self.keys)
