"""API key pool for the annotation pipeline.

Persistent key document (one key per line, '#' comments allowed) with
fixed-order rotation: every request uses the first alive key; a dead or
exhausted key is retired and the pool moves to the next one. When every key
is retired the pool raises :class:`APIKeyPoolExhausted` so the run fails fast
instead of looping — the shard checkpoint is already on disk, so rerunning
the same command resumes from it.

Keys are never logged; only their 1-based index is printed.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from foundry.api_client import APIError

ENV_KEY_FILE = "ANNOTATION_API_KEY_FILE"
ENV_KEYS = "ANNOTATION_API_KEYS"
DEFAULT_KEY_FILE = Path(__file__).resolve().parents[1] / "keys" / "api_keys.txt"


class APIKeyPoolExhausted(APIError):
    """Raised when every key in the pool is retired."""


def load_api_keys(path: str | Path | None = None) -> list[str]:
    """Load keys in fixed order.

    Resolution: explicit ``path`` > ``$ANNOTATION_API_KEY_FILE`` >
    ``keys/api_keys.txt`` in the repository > ``$ANNOTATION_API_KEYS``
    (comma-separated). Returns an empty list when no source exists.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    elif os.environ.get(ENV_KEY_FILE, "").strip():
        candidates.append(Path(os.environ[ENV_KEY_FILE].strip()))
    else:
        candidates.append(DEFAULT_KEY_FILE)
    for candidate in candidates:
        if candidate.is_file():
            keys: list[str] = []
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.split("#", 1)[0].strip()
                if line:
                    keys.append(line)
            return keys
    env_value = os.environ.get(ENV_KEYS, "").strip()
    if env_value:
        return [part.strip() for part in env_value.split(",") if part.strip()]
    return []


class APIKeyPool:
    """Thread-shared fixed-order key rotation."""

    def __init__(self, keys: list[str], *, notify=None) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for key in keys:
            if not isinstance(key, str) or not key.strip():
                continue
            key = key.strip()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(key)
        if not cleaned:
            raise ValueError("API key pool is empty")
        self._keys = cleaned
        self._retired: set[int] = set()
        self._lock = threading.Lock()
        self._notify = notify or (lambda message: None)

    @property
    def size(self) -> int:
        return len(self._keys)

    def alive(self) -> int:
        with self._lock:
            return len(self._keys) - len(self._retired)

    def current(self) -> tuple[int, str]:
        """Return ``(index, key)`` of the first alive key.

        Raises :class:`APIKeyPoolExhausted` when every key is retired.
        """
        with self._lock:
            for index, key in enumerate(self._keys):
                if index not in self._retired:
                    return index, key
        raise APIKeyPoolExhausted(
            "API key pool exhausted: every key is retired. "
            "Add keys to the key file (or $ANNOTATION_API_KEYS) and rerun "
            "the same command to resume from the checkpoint."
        )

    def retire(self, index: int, reason: str) -> None:
        """Retire a key by index (idempotent) and report the switch."""
        with self._lock:
            if index in self._retired or not 0 <= index < len(self._keys):
                return
            self._retired.add(index)
            remaining = len(self._keys) - len(self._retired)
            if remaining:
                self._notify(
                    f"[key-pool] key#{index + 1} retired ({reason}) -> "
                    f"switching to key#{index + 2} ({remaining}/{len(self._keys)} alive)"
                )
            else:
                self._notify(
                    f"[key-pool] key#{index + 1} retired ({reason}) -> "
                    f"pool exhausted ({len(self._keys)} keys)"
                )

    def describe(self) -> str:
        return f"{self.alive()}/{self.size} alive"
