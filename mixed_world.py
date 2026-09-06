#!/usr/bin/env python3
"""Mixed-world experiment: a Tier 0 crowd with a small LLM-driven cast.

This tests the product architecture rather than a research question. If ~190
agents run free on the utility AI and 6-12 run on a model, cost scales with cast
size instead of world size — the difference between ~$20 and ~$340 a month at
200 agents. What is unknown is whether such a world holds together: whether
model-driven agents behave sensibly surrounded by utility-AI ones, whether they
reach for actions that do not work, and whether they earn enough of the story to
be worth the money.

    python3 mixed_world.py --mode record --max-usd 6
"""

import argparse
import gc
from collections import Counter

from study import scaled
from world import cognition, indices, narrative, stats
from world.llm import ModelClient
from world.sim import run

SEEDS, TICKS = 3, 1000
INDEX_KEYS = ["population", "knowledge_depth", "knowledge_breadth",
              "institution_density", "reciprocity", "goal_attainment",
              "inequality", "life_expectancy", "violence_rate"]


def failed_actions(log, principals):
    """A principal that picks an impossible action produces a routing record and
    no action record on that tick. That gap is the seam we are looking for.

    `reproduce` writes a `birth` record rather than an `action` record, so a
    successful birth looks like a refusal unless births are counted too — that
    false positive put reproduce at 100% refused in the first measurement.
    """
    routed = {(r["tick"], r["agent"]) for r in log.records
              if r["kind"] == "routing" and r.get("outcome") == "chose"}
    acted = {(r["tick"], r["agent"]) for r in log.records
             if r["kind"] == "action"}
    born = {(r["tick"], r["parent"]) for r in log.records if r["kind"] == "birth"}
    return len(routed - acted - born), len(routed)


def verb_mix(log, ids):
    counts = Counter(r["verb"] for r in log.records
                     if r["kind"] == "action" and r["agent"] in ids)
    total = sum(counts.values()) or 1
    return {v: n / total for v, n in counts.items()}, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="replay", choices=["replay", "record", "live"])
    ap.add_argument("--max-usd", type=float, default=6.0, dest="max_usd")
    ap.add_argument("--cache", default="cache/mixed.jsonl")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=TICKS)
    args = ap.parse_args()

    client = ModelClient(cache_path=args.cache, mode=args.mode,
                         max_usd=args.max_usd, progress_every=100)
    print(f"MIXED WORLD · 120 agents, cast of 6 · {args.seeds} seeds x {args.ticks} "
          f"ticks · mode={args.mode}", flush=True)
    if args.mode != "replay":
        print(f"  spending real money, ceiling ${args.max_usd:.2f}\n", flush=True)

    t0_idx = {k: [] for k in INDEX_KEYS}
    mx_idx = {k: [] for k in INDEX_KEYS}
    seams = crowd_mix = princ_mix = None
    seam_fail = seam_total = 0
    princ_counts, crowd_counts = Counter(), Counter()
    share_num = share_den = 0

    for seed in range(args.seeds):
        # The event log lives entirely in memory — ~100k records per world at
        # this size — so each world is summarised and released before the next
        # is built. Holding all six at once is what exhausted RAM.
        world, log = run(seed, args.ticks, scaled())
        vec = indices.vector(world, log)
        for k in INDEX_KEYS:
            t0_idx[k].append(vec[k])
        del world, log
        gc.collect()

        mind = cognition.Cognition(client=client, principals=1,
                                   on_cache_miss="error")
        world, log = run(seed, args.ticks, scaled(), mind=mind)
        for k in INDEX_KEYS:
            mx_idx[k].append(indices.vector(world, log)[k])

        principals = mind.principals or set()
        ever = {r["agent"] for r in log.records if r["kind"] == "routing"}
        f, t = failed_actions(log, ever)
        seam_fail += f
        seam_total += t

        pm, pn = verb_mix(log, ever)
        cm, cn = verb_mix(log, {a.id for a in world.agents} - ever)
        for v, share in pm.items():
            princ_counts[v] += share * pn
        for v, share in cm.items():
            crowd_counts[v] += share * cn

        ids = {a.id for a in world.agents}
        scored = narrative.score(log.records, ids)
        threads = narrative.thread(scored)
        top = threads[:20]
        share_den += len(top)
        share_num += sum(1 for arc in top if arc["who"] & ever)

        del world, log, scored, threads, top
        gc.collect()

    print(f"\n{'index':<22} {'tier0 only':>11} {'mixed':>10} {'cohen d':>9}")
    for k in INDEX_KEYS:
        print(f"{k:<22} {stats.mean(t0_idx[k]):>11.3f} {stats.mean(mx_idx[k]):>10.3f} "
              f"{stats.cohens_d(mx_idx[k], t0_idx[k]):>9.2f}", flush=True)

    print(f"\nSEAMS  actions chosen by the model that the engine refused: "
          f"{seam_fail}/{seam_total} ({seam_fail/max(1,seam_total):.1%})")

    pt = sum(princ_counts.values()) or 1
    ct = sum(crowd_counts.values()) or 1
    print(f"\n{'verb':<14} {'cast':>8} {'crowd':>8}")
    for v in sorted(set(princ_counts) | set(crowd_counts),
                    key=lambda v: -princ_counts[v]):
        print(f"{v:<14} {princ_counts[v]/pt:>8.1%} {crowd_counts[v]/ct:>8.1%}")

    print(f"\nNARRATIVE  top-20 threads involving the cast: "
          f"{share_num}/{share_den} ({share_num/max(1,share_den):.0%}) "
          f"— the cast is ~5% of the population")

    r = client.report()
    print(f"\nCOST  {r['billed_calls']} billed calls · "
          f"{r['input_tokens']/1000:.0f}k in / {r['output_tokens']/1000:.0f}k out · "
          f"${r['cost_usd']:.4f}")


if __name__ == "__main__":
    main()
