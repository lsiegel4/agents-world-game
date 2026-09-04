"""Append-only event log.

Deterministic by construction: nothing here records wall-clock time, so two runs
of the same (seed, config, code) produce byte-identical logs (DESIGN.md §2.7).
"""

import hashlib
import json
import subprocess


def code_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()[:12]
    except Exception:
        return "unknown"


class EventLog:
    def __init__(self):
        self.records = []

    def header(self, seed: int, config: dict) -> None:
        self.records.append({
            "kind": "header",
            "seed": seed,
            "config": config,
            "code_hash": code_hash(),
        })

    def emit(self, tick: int, kind: str, **payload) -> None:
        rec = {"kind": kind, "tick": tick}
        rec.update(payload)
        self.records.append(rec)

    def lines(self) -> list:
        return [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in self.records]

    def digest(self, include_header: bool = False) -> str:
        """SHA-256 over the log. The header carries code_hash, which changes with
        every commit, so determinism checks compare the body only."""
        records = self.records if include_header else self.records[1:]
        body = "\n".join(
            json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records
        )
        return hashlib.sha256(body.encode()).hexdigest()

    def write(self, path: str) -> None:
        with open(path, "w") as f:
            for line in self.lines():
                f.write(line + "\n")

    def count(self, kind: str) -> int:
        return sum(1 for r in self.records if r["kind"] == kind)
