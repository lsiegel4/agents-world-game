#!/usr/bin/env python3
"""Export one run as a JSON bundle for the spectator client (§8, §11 M4).

    python3 export_world.py --seed 42 --ticks 3000 --out spectator/world.json

The client is a subscriber to this, not a participant in the sim: the engine
stays authoritative and the renderer only ever reads (§9).
"""

import argparse
import json

from world import indices, narrative
from world.sim import run


def build(seed: int, ticks: int) -> dict:
    world, log = run(seed, ticks, {"worldgen": "generated"})
    ids = {a.id for a in world.agents}
    names = {a.id: a.name for a in world.agents}

    scored = narrative.score(log.records, ids)
    threads = narrative.thread(scored)
    lore = world.lore

    living = world.living_agents()
    # Follow the agents with the most story attached, not the luckiest ones.
    weight = {}
    for event in scored:
        for who in event["who"]:
            weight[who] = weight.get(who, 0.0) + event["salience"]
    followed = sorted(living, key=lambda a: -weight.get(a.id, 0.0))[:8]

    return {
        "seed": seed, "ticks": world.tick,
        "terrain": world.terrain,
        "nodes": [{"id": n.id, "kind": n.kind, "x": n.x, "y": n.y,
                   "stock": round(n.stock_fraction(), 3),
                   "degradation": round(n.degradation, 3)} for n in world.nodes],
        "sites": [{"score": round(s, 2), "x": x, "y": y} for s, x, y in lore["sites"]],
        "ruins": lore["ruins"],
        "history": {
            "eras": lore["history"]["eras"],
            "facts": lore["history"]["facts"],
            "myths": lore["myths"],
            "culture": lore["culture"],
            "institutions": lore["institutions"],
            "divergence": round(lore["myth_divergence"], 3),
        },
        "agents": [{
            "id": a.id, "name": a.name, "x": a.x, "y": a.y, "age": a.age,
            "generation": a.generation,
            "drives": {k: round(v, 3) for k, v in a.drives.items()},
            "restraint": round(a.restraint, 3),
            "shelter": round(a.shelter, 3),
            "hunger": round(a.hunger, 1),
            "food": round(a.has("food"), 1), "wood": round(a.has("wood"), 1),
            "techniques": sorted(a.techniques),
            "bonds": sorted(a.bonds),
            "goal": a.goal, "goals_held": len(a.goal_history),
            "goals_met": sum(1 for g in a.goal_history if g.get("met")),
            "beliefs": a.beliefs[-4:],
            "feed": narrative.personal_feed(a.id, scored, names, limit=7),
        } for a in followed],
        "chronicle": narrative.chronicle(threads, names, limit=8),
        "indices": indices.vector(world, log),
        "deaths": indices.deaths_by_cause(log),
        "population_curve": [
            {"tick": r["tick"], "population": r["population"]}
            for r in log.records if r["kind"] == "indices"],
        "narrative_summary": narrative.summary(log.records, ids),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=3000)
    parser.add_argument("--out", default="spectator/world.json")
    args = parser.parse_args()

    bundle = build(args.seed, args.ticks)
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(bundle, handle, separators=(",", ":"))
    size = os.path.getsize(args.out)
    print(f"wrote {args.out} ({size/1024:.0f} KB)")
    print(f"  {len(bundle['agents'])} followed agents, "
          f"{len(bundle['chronicle'])} chronicle entries, "
          f"{len(bundle['history']['eras'])} eras, "
          f"{bundle['narrative_summary']['threads']} threads")


if __name__ == "__main__":
    main()
