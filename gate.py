#!/usr/bin/env python3
"""The M0 gate.

DESIGN.md §11 / M0: prove the economy and the event deck produce non-degenerate
outcomes with no cognition. Written before tuning, deliberately, so the criteria
cannot drift to fit whatever the sim happens to do.

Criteria, across N seeds:
  1. survival     — population neither extinct nor unbounded
  2. variety      — normalized action entropy >= 0.35 (not one verb forever)
  3. commons      — mean node stock settles off both floor and ceiling
"""

import argparse
import math
from collections import Counter

from world.sim import run

ENTROPY_FLOOR = 0.35
STOCK_FLOOR, STOCK_CEIL = 0.05, 0.95


def action_entropy(log) -> float:
    verbs = Counter(r["verb"] for r in log.records if r["kind"] == "action")
    total = sum(verbs.values())
    if total == 0 or len(verbs) < 2:
        return 0.0
    h = -sum((n / total) * math.log(n / total) for n in verbs.values())
    return h / math.log(len(verbs))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--ticks", type=int, default=500)
    args = p.parse_args()

    print(f"{'seed':>4} {'pop':>5} {'entropy':>8} {'stock':>7} {'degrad':>7}  verdict")
    fails = Counter()

    for seed in range(args.seeds):
        world, log = run(seed, args.ticks)
        pop = len(world.living_agents())
        ent = action_entropy(log)
        stock = sum(n.stock_fraction() for n in world.nodes) / len(world.nodes)
        degr = sum(n.degradation for n in world.nodes) / len(world.nodes)

        bad = []
        if pop == 0:
            bad.append("extinct")
        if ent < ENTROPY_FLOOR:
            bad.append("monotony")
        if stock < STOCK_FLOOR:
            bad.append("stripped")
        if stock > STOCK_CEIL:
            bad.append("untouched")
        for b in bad:
            fails[b] += 1

        print(f"{seed:>4} {pop:>5} {ent:>8.3f} {stock:>7.1%} {degr:>7.2f}  "
              f"{'PASS' if not bad else ', '.join(bad)}")

    print()
    if not fails:
        print(f"GATE PASSED across {args.seeds} seeds.")
    else:
        print(f"GATE FAILED: " + ", ".join(f"{k} in {v}/{args.seeds}"
                                          for k, v in fails.most_common()))


if __name__ == "__main__":
    main()
