"""Private goals, revision, and inheritance — DESIGN.md §5.3.

Three properties the design demands, and how each is met here:

  Private        Goals never appear in another agent's observation. An agent can
                 infer what someone wants from what they do, and that is all.
  Heterogeneous  Drawn per agent from a generator, weighted by current drives.
                 No global objective exists to converge on (§2.1).
  Malleable      Goals live in state, not in a prompt, and the engine revises
                 them at thresholds: achieved, proven impossible, or a life event.

Goals are structured rather than free text, deliberately. §7.5's threat #5 is
that measurement becomes model-mediated; a goal the engine can evaluate keeps
`goal_attainment` computable from world state, with no judge in the loop and no
inter-model agreement to report.

Note the asymmetry that makes these non-zero-sum: most kinds can be satisfied by
every agent at once (`master`, `lineage`, `provide`), a few are contested only
incidentally (`accumulate` under scarcity), and one is genuinely adversarial
(`avenge`). The mix is the point — a world where everyone wants the same thing
is the thing the design refuses to build.
"""

from . import knowledge

# kind -> (default threshold, which drive makes it likely)
KINDS = {
    "accumulate": (10.0, "survival"),   # hold this much food at once
    "master":     (3.0,  "mastery"),    # know this many techniques
    "teach":      (3.0,  "mastery"),    # pass knowledge on this many times
    "bond":       (2.0,  "belonging"),  # hold this many ties
    "lineage":    (2.0,  "legacy"),     # this many children
    "outlive":    (600.0, "survival"),  # reach this age
    "provide":    (5.0,  "belonging"),  # give this many times
    "avenge":     (1.0,  "autonomy"),   # strike back at someone who wronged you
}

REVISION_ON_LIFE_EVENT = 0.35    # chance a life event prompts a restatement

# A goal held this long without real progress is given up on. Without this,
# slow goals are an absorbing state: fast goals complete and cycle, `outlive`
# takes 600+ ticks, and every survivor eventually drains into it — a population
# converged on one goal, which is §2.1's global objective by another route.
STALE_TICKS = 500
STALE_PROGRESS = 0.55


def _weight(agent, drive_name: str) -> float:
    """M0 carries three of §5.1's seven drives; the rest map onto what exists."""
    drives = agent.drives
    if drive_name in drives:
        return drives[drive_name]
    return {"belonging": (1.0 - min(1.0, agent.hunger / 40.0)) * agent.shelter,
            "legacy": drives.get("mastery", 0.3) * 0.7,
            "autonomy": 1.0 - agent.restraint}.get(drive_name, 0.3)


def generate(agent, rng, world=None) -> dict:
    """Draw a goal, weighted by what is currently pulling at this agent."""
    kinds = sorted(KINDS)
    weights = [_weight(agent, KINDS[k][1]) for k in kinds]

    # `avenge` is only coherent if someone has actually wronged you.
    if not agent.grudges:
        weights[kinds.index("avenge")] = 0.0

    # Damp the kind just given up on, so a stale goal is not redrawn at once.
    last = agent.goal_history[-1]["kind"] if agent.goal_history else None
    if last in kinds and not agent.goal_history[-1].get("met"):
        weights[kinds.index(last)] *= 0.25

    total = sum(weights)
    if total <= 0:
        chosen = kinds[rng.randrange(len(kinds))]
    else:
        roll, acc = rng.random() * total, 0.0
        chosen = kinds[-1]
        for k, w in zip(kinds, weights):
            acc += w
            if roll <= acc:
                chosen = k
                break

    threshold = KINDS[chosen][0]
    target = ""
    if chosen == "avenge":
        target = max(agent.grudges.items(), key=lambda kv: kv[1])[0]
    elif chosen == "outlive":
        threshold = agent.age + KINDS[chosen][0]

    # Baselines, so progress is measured from where the agent stood when it took
    # the goal on. Scoring `outlive` as age/threshold makes an agent aged 1000
    # start at 0.62 progress and never go stale, which is how a slow goal became
    # an absorbing state for the whole population.
    return {"kind": chosen, "target": target, "threshold": threshold,
            "since": world.tick if world else 0, "met": False,
            "start_age": agent.age,
            "start_counts": {k: agent.counters.get(k, 0)
                             for k in ("teach", "provide", "lineage", "avenged")}}


def progress(agent, goal: dict, counters: dict) -> float:
    """How far along, 0..1, measured from where the agent stood when it took the
    goal on rather than from zero."""
    kind = goal["kind"]
    base = goal.get("start_counts") or {}

    if kind == "accumulate":
        value, target = agent.has("food"), goal["threshold"]
    elif kind == "master":
        value, target = len(agent.techniques), goal["threshold"]
    elif kind == "bond":
        value, target = len(agent.bonds), goal["threshold"]
    elif kind == "outlive":
        # Ticks survived since taking it on, against the span required.
        value = agent.age - goal.get("start_age", 0)
        target = goal["threshold"] - goal.get("start_age", 0)
    elif kind == "avenge":
        value = counters.get("avenged", 0.0) - base.get("avenged", 0)
        target = goal["threshold"]
    else:                                    # teach, lineage, provide
        value = counters.get(kind, 0.0) - base.get(kind, 0)
        target = goal["threshold"]

    return min(1.0, max(0.0, value) / target) if target else 0.0


def impossible(agent, goal: dict, world) -> bool:
    """A goal can stop making sense: the target of revenge dies, the ambition
    outruns the world, or it simply goes nowhere for long enough that the agent
    stops holding it."""
    if goal["kind"] == "avenge":
        return not any(a.id == goal["target"] and a.alive for a in world.agents)
    if goal["kind"] == "master":
        return goal["threshold"] > len(knowledge.TECHNIQUES)

    held = world.tick - goal.get("since", 0)
    if held > STALE_TICKS:
        # `counters` lives on the agent; progress is cheap to recompute here.
        if progress(agent, goal, agent.counters) < STALE_PROGRESS:
            return True
    return False


def inherit(parent_goal: dict, rng, world) -> dict:   # rng unused, kept for symmetry
    """A child takes the shape of the parent's goal, not its progress.

    §5.3 counts goal acquisition — taught, inherited, coerced, absorbed — as a
    measured phenomenon. This is the inherited case, and it is what gives §7.6's
    lock-in test something to look at once archetypes differentiate.
    """
    return {"kind": parent_goal["kind"], "target": "", "met": False,
            "threshold": KINDS[parent_goal["kind"]][0], "since": world.tick,
            "acquired": "inherited"}
