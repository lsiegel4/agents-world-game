"""Model client with record/replay, cost accounting, and a spend guard.

DESIGN.md §2.7 requires a run to be reproducible from (seed, config, code), and
§9 requires every model call logged with request and response so a run replays
exactly. Both are satisfied the same way: every request is hashed, and the
response is stored against that hash. In replay mode nothing touches the
network, tests are free and deterministic, and a recorded run can be re-derived
years later without the model still existing.

Live mode is opt-in and guarded. Nothing here spends money unless
`mode="live"` is passed explicitly and a spend ceiling is set.
"""

import hashlib
import json
import os

# $ per million tokens, from the model table. Kept local so a cost report never
# depends on a network call.
PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5":  (2.00, 10.00),
    "claude-opus-5":    (5.00, 25.00),
}


class SpendLimitExceeded(RuntimeError):
    pass


class CacheMiss(KeyError):
    pass


def request_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ModelClient:
    """Wraps the Anthropic SDK. Three modes:

    replay  - cache only; a miss raises CacheMiss. No network, no cost.
    record  - call the API, store every response into the cache.
    live    - call the API, use the cache when it hits (cheapest correct mode).
    """

    def __init__(self, cache_path: str = "cache/model.jsonl", mode: str = "replay",
                 max_usd: float = 0.0, progress_every: int = 0):
        self.mode = mode
        # Live spend reporting. A record run can take minutes, and watching a
        # number climb is the difference between noticing a runaway loop and
        # reading about it afterwards.
        self.progress_every = progress_every
        self.cache_path = cache_path
        self.max_usd = max_usd
        self.cache = {}
        self.calls = 0
        self.hits = 0
        self.billed = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self._client = None
        self._load()

    # ---------------------------------------------------------------- cache
    def _load(self) -> None:
        if not os.path.exists(self.cache_path):
            return
        with open(self.cache_path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    self.cache[rec["hash"]] = rec["response"]

    def _store(self, key: str, response: dict) -> None:
        self.cache[key] = response
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "a") as f:
            f.write(json.dumps({"hash": key, "response": response},
                               sort_keys=True, separators=(",", ":")) + "\n")

    # ---------------------------------------------------------------- cost
    def _charge(self, model: str, usage: dict) -> None:
        inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        self.billed += 1
        self.input_tokens += inp
        self.output_tokens += out
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
        self.cost_usd += inp / 1e6 * price_in + out / 1e6 * price_out

        if self.progress_every and self.billed % self.progress_every == 0:
            pct = f" of ${self.max_usd:.2f}" if self.max_usd else ""
            print(f"    [{self.billed:>5} calls] ${self.cost_usd:>8.4f}{pct}"
                  f"   {self.input_tokens/1000:.0f}k in / "
                  f"{self.output_tokens/1000:.1f}k out", flush=True)

        if self.max_usd and self.cost_usd > self.max_usd:
            raise SpendLimitExceeded(
                f"spend ${self.cost_usd:.4f} exceeded ceiling ${self.max_usd:.2f}")

    def report(self) -> dict:
        return {
            "mode": self.mode,
            "calls": self.calls,
            "cache_hits": self.hits,
            "billed_calls": self.billed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }

    # ---------------------------------------------------------------- call
    def complete(self, payload: dict) -> dict:
        """payload is the full Messages request. Returns a trimmed response dict:
        {content: [...], usage: {...}, model: str}."""
        key = request_hash(payload)
        self.calls += 1

        if key in self.cache:
            self.hits += 1
            return self.cache[key]

        if self.mode == "replay":
            raise CacheMiss(
                f"no cached response for {key[:12]} — run in record mode to populate")

        response = self._call_api(payload)
        self._charge(payload["model"], response["usage"])
        self._store(key, response)
        return response

    def _call_api(self, payload: dict) -> dict:
        if self._client is None:
            import anthropic          # imported lazily: replay mode needs no SDK
            self._client = anthropic.Anthropic()

        message = self._client.messages.create(**payload)
        return {
            "model": message.model,
            "stop_reason": message.stop_reason,
            "content": [b.model_dump() for b in message.content],
            "usage": {"input_tokens": message.usage.input_tokens,
                      "output_tokens": message.usage.output_tokens},
        }
