"""World indices — DESIGN.md §7.1.

"Progress" is a vector, never a scalar. Collapsing these into one number would
reintroduce the global objective the design rejects (§2.1), so nothing here
returns an overall score, and nothing here weights one index against another.

Five of the ten indices are computable from the M0 world. The other five need
machinery that does not exist yet, and they are listed in UNAVAILABLE rather
than silently omitted or faked with a proxy — a proxy would let a result be
reported for an index the simulation cannot actually measure.
"""

from . import knowledge, stats
from .state import FOOD, WOOD, World

UNAVAILABLE = {
    "goal_attainment": "agents have drives but no private goals until M1 slice 3",
}

VIOLENT_VERBS = ("steal", "harm")


def population(world: World) -> int:
    return len(world.living_agents())


def _harvested(log) -> float:
    return sum(r.get("taken", 0.0) for r in log.records
               if r["kind"] == "action" and r.get("verb") == "work")


def material_output(world: World, log) -> float:
    """Units harvested per living agent per 1000 ticks.

    Report this ONLY alongside `material_output_total`. Per-capita output moves
    when population moves, so a change that supports more people on similar
    production reads here as a productivity *collapse*. The teach ablation is the
    worked example: teaching raised total extraction 25% and population 88%, and
    this index fell from 737 to 385 — the exact opposite of what happened.
    """
    pop = max(1, population(world))
    ticks = max(1, world.tick)
    return _harvested(log) / pop / ticks * 1000.0


def material_output_total(world: World, log) -> float:
    """Units harvested per 1000 ticks, population-independent."""
    return _harvested(log) / max(1, world.tick) * 1000.0


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


def norm_compliance(log) -> float:
    """§7.1: the defection rate when unobserved, minus the rate when observed.

    Positive means agents defect disproportionately when nobody is watching —
    the norm is being *complied with* under observation rather than internalized.
    Zero means being seen makes no difference. This is only a real measurement
    because §5.6 makes inhibition scale with witnesses *and* with restraint, so
    the differential is produced by agents rather than asserted by the metric.

    Returns None when there is not enough defection to estimate from.
    """
    obs_acts = obs_viol = unobs_acts = unobs_viol = 0
    for r in log.records:
        if r["kind"] != "action":
            continue
        # Only agent-ticks where violence was actually possible count.
        if r.get("opp", 0) < 1:
            continue
        # Discount the prospective victim from the witness count — see
        # brain.candidates. "Observed" means a bystander beyond the target.
        seen = (r.get("w", 0) - 1) > 0
        violent = r["verb"] in VIOLENT_VERBS
        if seen:
            obs_acts += 1
            obs_viol += violent
        else:
            unobs_acts += 1
            unobs_viol += violent

    if obs_viol + unobs_viol < 10 or not obs_acts or not unobs_acts:
        return None
    return (unobs_viol / unobs_acts) - (obs_viol / obs_acts)


def violence_rate(log) -> float:
    """Violent acts per 1000 actions."""
    acts = [r for r in log.records if r["kind"] == "action"]
    if not acts:
        return 0.0
    return sum(1 for r in acts if r["verb"] in VIOLENT_VERBS) / len(acts) * 1000.0


def mean_restraint(world: World) -> float:
    live = world.living_agents()
    return stats.mean([a.restraint for a in live]) if live else 0.0


def knowledge_depth(world: World) -> int:
    return knowledge.known_depth(world.living_agents())


def knowledge_breadth(world: World) -> float:
    return knowledge.breadth(world.living_agents())


def institution_density(world: World) -> int:
    """Connected components of the bond graph with at least two members.

    §7.1 asks for structures with a persisting rule; a bond is that rule in its
    smallest form — bonded agents resist coercion from each other and are given
    to preferentially.
    """
    live = {a.id: a for a in world.living_agents()}
    seen, groups = set(), 0
    for agent_id in live:
        if agent_id in seen:
            continue
        stack, size = [agent_id], 0
        while stack:
            current = stack.pop()
            if current in seen or current not in live:
                continue
            seen.add(current)
            size += 1
            stack.extend(b for b in live[current].bonds if b not in seen)
        if size >= 2:
            groups += 1
    return groups


def trust_network(world: World) -> dict:
    """Mean regard and reciprocity across living agents."""
    live = world.living_agents()
    by_id = {a.id: a for a in live}
    regard, mutual, ties = [], 0, 0
    for a in live:
        for other_id in set(list(a.favors) + list(a.grudges)):
            if other_id not in by_id:
                continue
            ties += 1
            regard.append(a.standing(other_id))
            if by_id[other_id].standing(a.id) > 0 and a.standing(other_id) > 0:
                mutual += 1
    return {"ties": ties,
            "mean_regard": round(stats.mean(regard), 4) if regard else 0.0,
            "reciprocity": round(mutual / ties, 4) if ties else 0.0}


def vector(world: World, log) -> dict:
    """The measurable slice of §7.1. Report it whole — a world can rise in
    material output while collapsing in diversity, and that tradeoff is the
    finding, not noise to be averaged away."""
    return {
        "population": population(world),
        "material_output": round(material_output(world, log), 3),
        "material_output_total": round(material_output_total(world, log), 3),
        "knowledge_depth": knowledge_depth(world),
        "knowledge_breadth": round(knowledge_breadth(world), 3),
        "institution_density": institution_density(world),
        "reciprocity": trust_network(world)["reciprocity"],
        "inequality": round(inequality(world), 4),
        "drive_diversity": round(drive_diversity(world), 4),
        "life_expectancy": round(life_expectancy(log), 1),
        "violence_rate": round(violence_rate(log), 3),
        "mean_restraint": round(mean_restraint(world), 4),
        "norm_compliance": norm_compliance(log),
    }


def snapshot(world: World) -> dict:
    """Cheap per-tick record written into the event log."""
    return {"population": population(world)}
