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

    return {"kind": chosen, "target": target, "threshold": threshold,
            "since": world.tick if world else 0, "met": False}


def progress(agent, goal: dict, counters: dict) -> float:
    """How far along, 0..1. Read from engine state and the agent's own tally."""
    kind = goal["kind"]
    if kind == "accumulate":
        value = agent.has("food")
    elif kind == "master":
        value = len(agent.techniques)
    elif kind == "bond":
        value = len(agent.bonds)
    elif kind == "outlive":
        value = agent.age
    elif kind == "avenge":
        value = counters.get("avenged", 0.0)
    else:
        value = counters.get(kind, 0.0)      # teach, lineage, provide
    return min(1.0, value / goal["threshold"]) if goal["threshold"] else 0.0


def impossible(agent, goal: dict, world) -> bool:
    """A goal can stop making sense. Revenge on the dead is the clear case; so
    is mastering more techniques than the world contains."""
    if goal["kind"] == "avenge":
        return not any(a.id == goal["target"] and a.alive for a in world.agents)
    if goal["kind"] == "master":
        return goal["threshold"] > len(knowledge.TECHNIQUES)
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
