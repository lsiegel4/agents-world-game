#!/usr/bin/env python3
"""Re-run every study at the 120-founder scale condition.

Every social result recorded before this was measured with 5 founders, where
institution_density and reciprocity are structurally zero. This re-runs the same
studies at the scale §12 actually targets and prints both numbers side by side,
so a finding that does not survive is visible rather than quietly superseded.
"""

import sys
import time

from study import SCALE, scaled
from world import indices, narrative, profiles, stats
from world.sim import run

SEEDS, TICKS = 20, 2000

# What the small-world runs reported, for direct comparison.
SMALL = {
    "population": 13.50, "knowledge_depth": 3.00, "knowledge_breadth": 10.57,
    "institution_density": 2.00, "reciprocity": 0.371, "goal_attainment": 0.426,
    "inequality": 0.254, "life_expectancy": 223.32, "violence_rate": 5.54,
    "mean_restraint": 0.526, "material_output_total": 2741.31,
}


def vec(seeds, ticks, cfg):
    out = {}
    for seed in range(seeds):
        world, log = run(seed, ticks, cfg)
        for key, value in indices.vector(world, log).items():
            out.setdefault(key, []).append(value)
    return out


def line(label, a, b, d=None):
    delta = f"{a - b:>9.3f}" if b is not None else " " * 9
    cohen = f"{d:>7.2f}" if d is not None else " " * 7
    return f"  {label:<24} {a:>10.3f} {('%10.3f' % b) if b is not None else '':>10} {delta} {cohen}"


def main():
    started = time.time()
    print(f"RE-MEASUREMENT AT SCALE · {SCALE['agents']} founders · "
          f"{SEEDS} seeds x {TICKS} ticks\n", flush=True)

    # ---- 1. the index vector, scale vs small ----------------------------
    print("[1/5] index vector", flush=True)
    at_scale = vec(SEEDS, TICKS, scaled())
    print(f"\n  {'index':<24} {'at scale':>10} {'5 founders':>10} {'delta':>9}")
    for key in SMALL:
        if key in at_scale:
            print(line(key, stats.mean(at_scale[key]), SMALL[key]), flush=True)
    print(flush=True)

    # ---- 2-4. the ablations ---------------------------------------------
    for step, arm in ((2, "teach"), (3, "violence"), (4, "deck")):
        print(f"[{step}/5] {arm} ablation", flush=True)
        if arm == "teach":
            on = vec(SEEDS, TICKS, scaled())
            off = vec(SEEDS, TICKS, scaled({"disabled_verbs": ("teach",)}))
        else:
            on = vec(SEEDS, TICKS, scaled({arm: True}))
            off = vec(SEEDS, TICKS, scaled({arm: False}))
        print(f"\n  {arm + ' ablation':<24} {'on':>10} {'off':>10} {'delta':>9} {'cohen d':>7}")
        for key in ("population", "knowledge_depth", "knowledge_breadth",
                    "institution_density", "reciprocity", "goal_attainment",
                    "inequality", "life_expectancy", "violence_rate",
                    "material_output_total"):
            if key in on:
                print(line(key, stats.mean(on[key]), stats.mean(off[key]),
                           stats.cohens_d(on[key], off[key])), flush=True)
        print(flush=True)

    # ---- 5. attribution --------------------------------------------------
    print("[5/5] attribution", flush=True)
    pooled = {}
    for seed in range(SEEDS):
        _, log = run(seed, TICKS, scaled())
        for agent_id, prof in profiles.build(log).items():
            pooled[f"s{seed}:{agent_id}"] = prof
    res = profiles.attribution(pooled)
    print(f"\n  lifespan ~ endowment + luck + policy   "
          f"n={res['n']} of {len(pooled)} agents   R2={res['r2']}")
    for group, value in res["groups"].items():
        print(f"    {group:<24} {value:>7.4f}", flush=True)
    print("    (5 founders gave: policy 0.574, luck 0.442, endowment 0.115)")
    for name, beta in sorted(res["betas"].items(), key=lambda kv: -abs(kv[1])):
        print(f"      {name:<26} {beta:>+8.4f}", flush=True)

    print(f"\ndone in {(time.time() - started)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
