"""Append-only event log.

Deterministic by construction: nothing here records wall-clock time, so two runs
of the same (seed, config, code) produce byte-identical logs (DESIGN.md §2.7).
"""

import hashlib
import json
import os
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


class RecordStream:
    """An on-disk record list. Iterates by re-reading the file.

    Supports the operations the analysis code actually performs — iteration and
    len() — so `log.records` keeps working across ~48 call sites without any of
    them holding the whole log in memory. Indexing is deliberately absent: it
    would invite an O(n) read per access and hide the cost.
    """

    def __init__(self, path: str):
        self.path = path
        self.count = 0

    def __iter__(self):
        with open(self.path) as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)

    def __len__(self):
        return self.count


class EventLog:
    """Append-only event log (§2.7).

    In-memory by default. Pass `path` to stream records to disk instead: at 120
    agents an 800-tick world produces ~100k records, and holding several worlds'
    worth at once exhausted RAM and killed two experiment runs. A world that
    never ends — M6's — cannot hold its log in memory at all, and the live
    spectator needs to read a growing stream rather than a finished list, so
    both want this same change.
    """

    def __init__(self, path: str = None):
        self.path = path
        self._handle = None
        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self._handle = open(path, "w")
            self.records = RecordStream(path)
        else:
            self.records = []
        self._digest = hashlib.sha256()

    def _write(self, record: dict) -> None:
        if self._handle is None:
            self.records.append(record)
            return
        self._handle.write(json.dumps(record, sort_keys=True,
                                      separators=(",", ":")) + "\n")
        self._handle.flush()
        self.records.count += 1
        self._digest.update(json.dumps(record, sort_keys=True,
                                       separators=(",", ":")).encode())

    def header(self, seed: int, config: dict, extra: dict = None) -> None:
        """Written first. In streaming mode the header cannot be edited after
        the fact, so anything belonging in it must be passed here."""
        record = {"kind": "header", "seed": seed, "config": config,
                  "code_hash": code_hash()}
        if extra:
            record.update(extra)
        self._write(record)

    def emit(self, tick: int, kind: str, **payload) -> None:
        """Record one event.

        Mutable values are copied. Storing a live reference — `drives=child.drives`
        — means the agent goes on mutating the object the log is holding, so a
        birth record ends up reporting that agent's *final* drives rather than
        the ones it was born with. An append-only log that changes after the fact
        is not a log (§2.7), and this was invisible until streaming to disk
        serialised on write and the two modes disagreed.
        """
        rec = {"kind": kind, "tick": tick}
        for key, value in payload.items():
            if isinstance(value, dict):
                rec[key] = dict(value)
            elif isinstance(value, (list, set, tuple)):
                rec[key] = list(value)
            else:
                rec[key] = value
        self._write(rec)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def lines(self) -> list:
        return [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in self.records]

    def digest(self, include_header: bool = False) -> str:
        """SHA-256 over the log. The header carries code_hash, which changes with
        every commit, so determinism checks compare the body only."""
        body = []
        for index, record in enumerate(self.records):
            if index == 0 and not include_header:
                continue
            body.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        return hashlib.sha256("\n".join(body).encode()).hexdigest()

    def write(self, path: str) -> None:
        with open(path, "w") as f:
            for line in self.lines():
                f.write(line + "\n")

    def count(self, kind: str) -> int:
        return sum(1 for r in self.records if r["kind"] == kind)
