"""World indices — DESIGN.md §7.1.

"Progress" is a vector, never a scalar. Collapsing these into one number would
reintroduce the global objective the design rejects (§2.1), so nothing here
returns an overall score, and nothing here weights one index against another.

Five of the ten indices are computable from the M0 world. The other five need
machinery that does not exist yet, and they are listed in UNAVAILABLE rather
than silently omitted or faked with a proxy — a proxy would let a result be
reported for an index the simulation cannot actually measure.
"""

from . import stats
from .state import FOOD, WOOD, World

UNAVAILABLE = {
    "knowledge_depth":    "no technique graph until `craft`/`teach` land in M1",
    "knowledge_breadth":  "no knowledge transmission until `teach` lands in M1",
    "institution_density": "no multi-agent structures until `form_bond` lands in M1",
    "norm_compliance":    "no norms, and no verb an agent could break one with (§12)",
    "trust_network":      "no relationship state until agents can `speak` (M1)",
    "goal_attainment":    "agents have drives but no private goals until M1",
}


def population(world: World) -> int:
    return len(world.living_agents())


def material_output(world: World, log) -> float:
    """Units harvested per living agent per 1000 ticks."""
    harvested = sum(r.get("taken", 0.0) for r in log.records
                    if r["kind"] == "action" and r.get("verb") == "work")
    pop = max(1, population(world))
    ticks = max(1, world.tick)
    return harvested / pop / ticks * 1000.0


def inequality(world: World) -> float:
    """Gini over total holdings of the living."""
    return stats.gini([a.has(FOOD) + a.has(WOOD) for a in world.living_agents()])


def drive_diversity(world: World) -> float:
    """Entropy of the drive-vector distribution across the population — §7.1's
    pluralism index. Measured per drive as spread across agents, then averaged:
    a population that has all converged on the same vector scores low."""
    live = world.living_agents()
    if len(live) < 2:
        return 0.0
    names = list(live[0].drives.keys())
    return stats.mean([stats.entropy([a.drives[n] for a in live]) for n in names])


def life_expectancy(log) -> float:
    ages = [r["age"] for r in log.records if r["kind"] == "death"]
    return stats.mean(ages)


def deaths_by_cause(log) -> dict:
    out = {}
    for r in log.records:
        if r["kind"] == "death":
            out[r["cause"]] = out.get(r["cause"], 0) + 1
    return out


def vector(world: World, log) -> dict:
    """The measurable slice of §7.1. Report it whole — a world can rise in
    material output while collapsing in diversity, and that tradeoff is the
    finding, not noise to be averaged away."""
    return {
        "population": population(world),
        "material_output": round(material_output(world, log), 3),
        "inequality": round(inequality(world), 4),
        "drive_diversity": round(drive_diversity(world), 4),
        "life_expectancy": round(life_expectancy(log), 1),
    }


def snapshot(world: World) -> dict:
    """Cheap per-tick record written into the event log."""
    return {"population": population(world)}
