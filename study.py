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

from world import cognition, indices, profiles, stats
from world.llm import ModelClient
from world.sim import run

# The full §7.1 vector. Kept in one place so every command reports the same
# thing — a study that quietly drops indices is how a tradeoff gets hidden.
# Every social result before 2026-09-04 was measured with 5 founders. At that
# size institution_density and reciprocity are structurally zero — bonds die
# with their members and no group survives. §12 puts the design's target at
# 100-300. This is the canonical scale condition; studies run against it so the
# numbers are comparable to each other rather than to a world too small to show
# the phenomena being measured.
SCALE = {
    "agents": 120, "sites": 12,
    "width": 120, "height": 60,
    "food_nodes": 40, "wood_nodes": 20,
}


def scaled(extra=None):
    cfg = dict(SCALE)
    if extra:
        cfg.update(extra)
    return cfg


INDEX_KEYS = ["population", "material_output", "material_output_total",
              "knowledge_depth", "knowledge_breadth", "institution_density",
              "reciprocity", "goal_attainment", "goal_progress",
              "inequality", "drive_diversity", "life_expectancy",
              "violence_rate", "mean_restraint"]


def collect(seeds: int, ticks: int, config: dict = None) -> dict:
    out = {k: [] for k in INDEX_KEYS}
    for seed in range(seeds):
        world, log = run(seed, ticks, config)
        vec = indices.vector(world, log)
        for k in INDEX_KEYS:
            out[k].append(vec[k])
    return out


def cmd_indices(args):
    data = collect(args.seeds, args.ticks, scaled() if args.scale else None)
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
    base = scaled if args.scale else (lambda extra=None: dict(extra or {}))
    on = collect(args.seeds, args.ticks, base({arm: True}))
    off = collect(args.seeds, args.ticks, base({arm: False}))

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
        _, log = run(seed, args.ticks, scaled() if args.scale else None)
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


def cmd_worldgen(args):
    """Generated worlds against flat ones, same seeds.

    Scope limit, stated up front: at Tier 0 no agent ever reads a prompt, and
    lore only reaches agents through the prompt. This measures terrain, node
    siting and endowment — the procedural half of §4.1. It cannot measure
    whether inherited history changes behaviour, which is §11's actual claim and
    needs the LLM arm.
    """
    base = scaled if args.scale else (lambda extra=None: dict(extra or {}))
    flat = collect(args.seeds, args.ticks, base({"worldgen": "flat"}))
    gen = collect(args.seeds, args.ticks, base({"worldgen": "generated"}))

    print(f"WORLDGEN · generated vs flat · {args.seeds} paired seeds · "
          f"{args.ticks} ticks · Tier 0 only\n")
    print(f"{'index':<22} {'flat':>10} {'generated':>10} {'delta':>10} {'cohen d':>9}")
    for k in INDEX_KEYS:
        a, b = gen[k], flat[k]
        print(f"{k:<22} {stats.mean(b):>10.3f} {stats.mean(a):>10.3f} "
              f"{stats.mean(a) - stats.mean(b):>10.3f} {stats.cohens_d(a, b):>9.2f}")
    print("\n  Tier 0 agents never read a prompt, so no lore reached them.")
    print("  This is the terrain/siting/endowment effect only.")


def cmd_violence(args):
    """Pooled violence analysis. Norm compliance needs more defections than one
    seed produces, so the arms are pooled across seeds before the ratio."""
    obs_acts = obs_viol = unobs_acts = unobs_viol = 0
    killed = victim_restraint = 0
    perp_restraint, all_restraint = [], []
    retaliations = violent_total = 0

    for seed in range(args.seeds):
        _, log = run(seed, args.ticks, scaled() if args.scale else None)
        for r in log.records:
            if r["kind"] == "action" and r.get("opp", 0) >= 1:
                violent = r["verb"] in indices.VIOLENT_VERBS
                if (r.get("w", 0) - 1) > 0:
                    obs_acts += 1
                    obs_viol += violent
                else:
                    unobs_acts += 1
                    unobs_viol += violent
                if violent:
                    perp_restraint.append(r.get("restraint", 0.0))
            elif r["kind"] == "death" and r["cause"] == "killed":
                killed += 1
        prof = profiles.build(log)
        all_restraint += [a["restraint_at_t0"] for a in prof.values() if a["restraint_at_t0"]]
        retaliations += sum(a["retaliations"] for a in prof.values())
        violent_total += sum(a["verbs"].get("steal", 0) + a["verbs"].get("harm", 0)
                             for a in prof.values())

    r_unobs = unobs_viol / unobs_acts if unobs_acts else 0.0
    r_obs = obs_viol / obs_acts if obs_acts else 0.0

    print(f"VIOLENCE · {args.seeds} seeds x {args.ticks} ticks (pooled)\n")
    print(f"  opportunity agent-ticks   unobserved {unobs_acts:>8}   observed {obs_acts:>8}")
    print(f"  defections                unobserved {unobs_viol:>8}   observed {obs_viol:>8}")
    print(f"  defection rate            unobserved {r_unobs:>8.5f}   observed {r_obs:>8.5f}")
    print(f"\n  norm compliance (unobs - obs): {r_unobs - r_obs:>+.5f}")
    print("    positive = agents defect more when unwatched, i.e. the norm is")
    print("    complied with under observation rather than internalized.")
    print(f"\n  killings: {killed}")
    print(f"  retaliation share of violence: {retaliations / violent_total:.1%}"
          if violent_total else "  retaliation share: n/a")
    if perp_restraint and all_restraint:
        print(f"\n  mean restraint of perpetrators at the moment of the act: "
              f"{stats.mean(perp_restraint):.3f}")
        print(f"  mean restraint of the population at birth:                 "
              f"{stats.mean(all_restraint):.3f}")


def cmd_cognition(args):
    """T0 (utility AI) against T1 (model), same seeds, same verbs.

    The verb set is identical in both arms, so a difference in the indices is
    attributable to cognition and not to a wider action space. This is the
    comparison the permanent control arm in brain.py exists for (§7.5).
    """
    client = ModelClient(cache_path=args.cache, mode=args.mode, max_usd=args.max_usd,
                         progress_every=args.progress_every)
    if args.mode != "replay":
        print(f"  spending real money (mode={args.mode}, ceiling "
              f"${args.max_usd:.2f}). Live cost below.\n", flush=True)

    t0 = {k: [] for k in INDEX_KEYS}
    t1 = {k: [] for k in INDEX_KEYS}
    minds = []

    for seed in range(args.seeds):
        world, log = run(seed, args.ticks)
        for k in INDEX_KEYS:
            t0[k].append(indices.vector(world, log)[k])

        mind = cognition.Cognition(client=client, on_cache_miss=args.on_miss)
        world, log = run(seed, args.ticks, mind=mind)
        for k in INDEX_KEYS:
            t1[k].append(indices.vector(world, log)[k])
        minds.append(mind)

    print(f"COGNITION · Tier 0 vs Tier 1 · {args.seeds} paired seeds · "
          f"{args.ticks} ticks · mode={args.mode}\n")
    print(f"{'index':<18} {'tier0':>9} {'tier1':>9} {'delta':>9} {'cohen d':>9}")
    for k in INDEX_KEYS:
        a, b = t1[k], t0[k]
        print(f"{k:<18} {stats.mean(b):>9.3f} {stats.mean(a):>9.3f} "
              f"{stats.mean(a) - stats.mean(b):>9.3f} {stats.cohens_d(a, b):>9.2f}")

    keys = ("decisions", "attempted_t1", "attempted_t2", "served_by_model",
            "fallbacks", "no_tool_call")
    total = {k: 0 for k in keys}
    for m in minds:
        r = m.report()
        for k in keys:
            total[k] += r[k]
    decisions = total["decisions"] or 1
    attempted = total["attempted_t1"] + total["attempted_t2"]

    print(f"\n  decisions {decisions}   escalations attempted {attempted} "
          f"(t1 {total['attempted_t1']}, t2 {total['attempted_t2']})")
    print(f"  escalation rate: {attempted / decisions:.2%}"
          "   <- the cost lever (§10)")
    print(f"  served by model: {total['served_by_model']}   "
          f"fell back to tier0: {total['fallbacks']}   "
          f"no tool call: {total['no_tool_call']}")
    if total["fallbacks"]:
        print("  NOTE: fallbacks ran the utility AI, so those ticks are not a")
        print("        model arm. Treat this run as incomplete, not as a result.")
    rep = client.report()
    print(f"\n  model calls {rep['calls']} (cache hits {rep['cache_hits']})  "
          f"tokens {rep['input_tokens']}in/{rep['output_tokens']}out  "
          f"cost ${rep['cost_usd']:.4f}")


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
                     ("attribution", cmd_attribution), ("violence", cmd_violence),
                     ("worldgen", cmd_worldgen),
                     ("cognition", cmd_cognition), ("replay", cmd_replay)):
        sp = sub.add_parser(name)
        sp.add_argument("--seeds", type=int, default=20)
        sp.add_argument("--ticks", type=int, default=2000)
        sp.add_argument("--scale", action="store_true",
                        help="run at the 120-founder scale condition")
        if name == "ablation":
            sp.add_argument("--arm", default="deck")
        if name == "cognition":
            # Defaults spend nothing: replay mode never touches the network, and
            # going live takes an explicit mode plus an explicit ceiling.
            sp.add_argument("--mode", default="replay",
                            choices=["replay", "record", "live"])
            sp.add_argument("--cache", default="cache/model.jsonl")
            sp.add_argument("--max-usd", type=float, default=1.0, dest="max_usd")
            sp.add_argument("--on-miss", default="error",
                            choices=["error", "tier0"], dest="on_miss")
            sp.add_argument("--progress-every", type=int, default=25,
                            dest="progress_every",
                            help="print running cost every N billed calls (0 = off)")
        sp.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
