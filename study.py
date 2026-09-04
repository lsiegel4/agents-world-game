#!/usr/bin/env python3
"""Experiment harness — DESIGN.md §7.3 and §7.4.

    python3 study.py indices     --seeds 20 --ticks 2000
    python3 study.py ablation    --arm deck --seeds 20 --ticks 2000
    python3 study.py attribution --seeds 20 --ticks 4000
    python3 study.py replay      --seeds 5  --ticks 500

Protocol rules this harness enforces:
  * every condition runs the same seeds, so arms are paired
  * effect sizes, not p-values — with seeds this cheap, significance is
    purchasable and only magnitude is informative
  * the indices reported are only those the simulation can actually measure;
    the rest are printed as unavailable, with the reason
"""

import argparse

from world import indices, profiles, stats
from world.sim import run

INDEX_KEYS = ["population", "material_output", "inequality",
              "drive_diversity", "life_expectancy"]


def collect(seeds: int, ticks: int, config: dict = None) -> dict:
    out = {k: [] for k in INDEX_KEYS}
    for seed in range(seeds):
        world, log = run(seed, ticks, config)
        vec = indices.vector(world, log)
        for k in INDEX_KEYS:
            out[k].append(vec[k])
    return out


def cmd_indices(args):
    data = collect(args.seeds, args.ticks)
    print(f"§7.1 index vector · {args.seeds} seeds · {args.ticks} ticks\n")
    print(f"{'index':<18} {'mean':>9} {'sd':>8} {'min':>8} {'max':>8}")
    for k in INDEX_KEYS:
        v = data[k]
        print(f"{k:<18} {stats.mean(v):>9.3f} {stats.pstdev(v):>8.3f} "
              f"{min(v):>8.2f} {max(v):>8.2f}")
    print("\nnot measurable yet:")
    for k, why in indices.UNAVAILABLE.items():
        print(f"  {k:<20} {why}")


def cmd_ablation(args):
    arm = args.arm
    on, off = collect(args.seeds, args.ticks, {arm: True}), \
              collect(args.seeds, args.ticks, {arm: False})

    print(f"ABLATION · {arm} on vs off · {args.seeds} paired seeds · {args.ticks} ticks\n")
    print(f"{'index':<18} {'on':>9} {'off':>9} {'delta':>9} {'cohen d':>9}")
    for k in INDEX_KEYS:
        a, b = on[k], off[k]
        print(f"{k:<18} {stats.mean(a):>9.3f} {stats.mean(b):>9.3f} "
              f"{stats.mean(a) - stats.mean(b):>9.3f} {stats.cohens_d(a, b):>9.2f}")
    print("\n|d| >= 0.8 large, 0.5 medium, 0.2 small.")


def cmd_attribution(args):
    """Pool agents across seeds, then decompose lifespan (§7.2)."""
    pooled = {}
    for seed in range(args.seeds):
        _, log = run(seed, args.ticks)
        for agent_id, prof in profiles.build(log).items():
            pooled[f"s{seed}:{agent_id}"] = prof

    res = profiles.attribution(pooled)
    print(f"ATTRIBUTION · lifespan ~ endowment + luck + policy")
    print(f"{args.seeds} seeds · {args.ticks} ticks · {len(pooled)} agents lived, "
          f"n={res['n']} analysed · R2={res['r2']}\n")
    print("  standardized betas:")
    for name, b in res["betas"].items():
        bar = "#" * int(abs(b) * 40)
        print(f"    {name:<16} {b:>8.4f}  {bar}")
    print("\n  grouped (sum |beta|):")
    for g, v in res["groups"].items():
        print(f"    {g:<16} {v:>8.4f}  {'#' * int(v * 40)}")
    print("\n  Excluded: agents alive at run end (censored) and agents that did not")
    print(f"  survive the {profiles.POLICY_WINDOW}-action policy window.")
    print("\n  not measurable yet:")
    for k, why in profiles.UNAVAILABLE.items():
        print(f"    {k:<32} {why}")


def cmd_replay(args):
    """§2.7: a run that cannot be reproduced is anecdote, not data."""
    ok = True
    for seed in range(args.seeds):
        _, a = run(seed, args.ticks)
        _, b = run(seed, args.ticks)
        match = a.digest() == b.digest()
        ok &= match
        print(f"  seed {seed}: {a.digest()[:16]} {'match' if match else 'MISMATCH'}")
    print("\nreplay verified." if ok else "\nREPLAY BROKEN.")


def main():
    p = argparse.ArgumentParser(description="Kestrel experiment harness.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("indices", cmd_indices), ("ablation", cmd_ablation),
                     ("attribution", cmd_attribution), ("replay", cmd_replay)):
        sp = sub.add_parser(name)
        sp.add_argument("--seeds", type=int, default=20)
        sp.add_argument("--ticks", type=int, default=2000)
        if name == "ablation":
            sp.add_argument("--arm", default="deck")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
