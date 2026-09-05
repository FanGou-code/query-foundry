"""Offline tests for the API key pool and pooled client rotation."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

from foundry.api_client import APIError, OpenAIProtocolClient
from foundry.keys import (
    APIKeyPool,
    APIKeyPoolExhausted,
    load_api_keys,
)


def _http_error(code: int) -> HTTPError:
    return HTTPError("https://example.invalid", code, "err", Message(), io.BytesIO(b"{}"))


class LoadKeyFileTests(unittest.TestCase):
    def test_parses_comments_blanks_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "api_keys.txt"
            path.write_text("# comment\n\nkey-one\n  key-two  \n# more\nkey-three\n")
            self.assertEqual(load_api_keys(path), ["key-one", "key-two", "key-three"])

    def test_env_fallback_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.txt"
            old = os.environ.get("ANNOTATION_API_KEYS")
            os.environ["ANNOTATION_API_KEYS"] = "env-a, env-b,,env-a"
            try:
                # loader preserves raw order; dedup happens in APIKeyPool
                self.assertEqual(load_api_keys(missing), ["env-a", "env-b", "env-a"])
            finally:
                if old is None:
                    os.environ.pop("ANNOTATION_API_KEYS", None)
                else:
                    os.environ["ANNOTATION_API_KEYS"] = old


class KeyPoolTests(unittest.TestCase):
    def test_fixed_order_rotation_and_exhaustion(self):
        messages = []
        pool = APIKeyPool(["k1", "k2"], notify=messages.append)
        self.assertEqual(pool.current(), (0, "k1"))
        pool.retire(0, "HTTP 429")
        self.assertEqual(pool.current(), (1, "k2"))
        self.assertEqual(pool.describe(), "1/2 alive")
        self.assertTrue(any("key#1 retired" in m for m in messages))
        pool.retire(1, "HTTP 402")
        with self.assertRaises(APIKeyPoolExhausted):
            pool.current()
        pool.retire(1, "HTTP 402")  # idempotent

    def test_rejects_empty_pool(self):
        with self.assertRaises(ValueError):
            APIKeyPool(["", "  "])
        with self.assertRaises(ValueError):
            APIKeyPool([])


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._body


class PooledClientTests(unittest.TestCase):
    def _payload(self):
        return {
            "id": "r1",
            "model": "glm-4.6v",
            "choices": [
                {"message": {"content": '{"query":"test"}'}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def test_switches_key_on_quota_error_and_fails_fast_when_exhausted(self):
        seen_keys = []
        responses = {"k1": "429", "k2": "ok"}

        def opener(request, timeout):
            key = request.headers["Authorization"].removeprefix("Bearer ")
            seen_keys.append(key)
            if responses[key] == "429":
                raise _http_error(429)
            return _FakeResponse(self._payload())

        pool = APIKeyPool(["k1", "k2"], notify=lambda m: None)
        client = OpenAIProtocolClient(
            key_pool=pool,
            model="glm-4.6v",
            base_url="https://api.example.invalid/v1",
            opener=opener,
            sleeper=lambda delay: None,
        )
        response = client.complete(
            messages=[{"role": "user", "content": "t"}], max_tokens=8, temperature=0.1
        )
        self.assertEqual(seen_keys, ["k1", "k1", "k2"])
        self.assertEqual(response.record["response_id"], "r1")

        responses["k2"] = "429"
        with self.assertRaises(APIKeyPoolExhausted):
            client.complete(
                messages=[{"role": "user", "content": "t"}], max_tokens=8, temperature=0.1
            )

    def test_immediate_switch_on_auth_error(self):
        seen_keys = []

        def opener(request, timeout):
            key = request.headers["Authorization"].removeprefix("Bearer ")
            seen_keys.append(key)
            if key == "bad":
                raise _http_error(401)
            return _FakeResponse(self._payload())

        pool = APIKeyPool(["bad", "good"], notify=lambda m: None)
        client = OpenAIProtocolClient(
            key_pool=pool,
            model="glm-4.6v",
            base_url="https://api.example.invalid/v1",
            opener=opener,
            sleeper=lambda delay: None,
        )
        client.complete(
            messages=[{"role": "user", "content": "t"}], max_tokens=8, temperature=0.1
        )
        self.assertEqual(seen_keys, ["bad", "good"])

    def test_server_error_keeps_same_key(self):
        seen_keys = []

        def opener(request, timeout):
            key = request.headers["Authorization"].removeprefix("Bearer ")
            seen_keys.append(key)
            raise _http_error(503)

        pool = APIKeyPool(["k1", "k2"], notify=lambda m: None)
        client = OpenAIProtocolClient(
            key_pool=pool,
            model="glm-4.6v",
            base_url="https://api.example.invalid/v1",
            opener=opener,
            sleeper=lambda delay: None,
            transport_attempts=2,
        )
        with self.assertRaises(APIError) as ctx:
            client.complete(
                messages=[{"role": "user", "content": "t"}], max_tokens=8, temperature=0.1
            )
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(seen_keys, ["k1", "k1"])
        self.assertEqual(pool.alive(), 2)


if __name__ == "__main__":
    unittest.main()
