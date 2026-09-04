#!/usr/bin/env python3
"""Run one world and print a summary.

    python3 run.py --seed 42 --ticks 500
    python3 run.py --seed 42 --ticks 500 --out runs/
"""

import argparse
import os
from collections import Counter

from world import indices
from world.sim import run


def main():
    p = argparse.ArgumentParser(description="Run one Kestrel world.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--ticks", type=int, default=500)
    p.add_argument("--out", default=None, help="directory to write events.jsonl into")
    args = p.parse_args()

    world, log = run(args.seed, args.ticks)

    verbs = Counter(r["verb"] for r in log.records if r["kind"] == "action")
    total = sum(verbs.values())
    deaths = log.count("death")

    print(f"seed {args.seed} · {world.tick} ticks · digest {log.digest()[:16]}")
    print(f"population {indices.population(world)} of {len(world.agents)} · deaths {deaths}")
    print("actions:")
    for verb, n in verbs.most_common():
        print(f"  {verb:<6} {n:>6}  {n / total:>6.1%}")
    print("nodes:")
    for node in world.nodes:
        print(f"  {node.id} {node.kind:<4} stock {node.stock_fraction():>5.1%}"
              f"  degradation {node.degradation:>5.2f}")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, f"events-{args.seed}.jsonl")
        log.write(path)
        print(f"wrote {path} ({len(log.records)} records)")


if __name__ == "__main__":
    main()
