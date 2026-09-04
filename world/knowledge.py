"""Techniques and their transmission — the substrate for DESIGN.md question 1.

"Which strategies help the world progress?" is unanswerable while there is
nothing to accumulate. This is the smallest thing that counts as accumulation:
a shallow dependency graph of techniques that make work pay better, which an
agent can stumble into alone and can hand to someone else.

Two properties matter for §7.1:

  knowledge_depth   - how deep into the graph anyone has got. Bounded by whether
                      prerequisites survive long enough to build on.
  knowledge_breadth - how many agents hold each technique. Moves only through
                      `teach`, so it is the direct readout on transmission.

Depth is the part that cannot be reached alone in a short life: `kiln` needs two
prerequisites, and an agent that discovers one and dies has taught the world
nothing. That is the point.
"""

# name -> (prerequisites, effect)
TECHNIQUES = {
    "gleaning":  ((), "food_yield"),        # depth 1
    "coppicing": ((), "wood_yield"),        # depth 1
    "drying":    (("gleaning",), "meal"),   # depth 2
    "joinery":   (("coppicing",), "repair"),  # depth 2
    "kiln":      (("drying", "joinery"), "meal_major"),  # depth 3
}

DISCOVERY_BASE = 0.0016      # per work action, scaled by curiosity
FOOD_YIELD_BONUS = 0.30
WOOD_YIELD_BONUS = 0.30
MEAL_BONUS = 0.35
MEAL_MAJOR_BONUS = 0.70
REPAIR_BONUS = 0.40


def depth(name: str) -> int:
    reqs = TECHNIQUES[name][0]
    return 1 + max((depth(r) for r in reqs), default=0)


MAX_DEPTH = max(depth(n) for n in TECHNIQUES)


def available_to(known) -> list:
    """Techniques whose prerequisites this agent already holds."""
    return [name for name, (reqs, _) in TECHNIQUES.items()
            if name not in known and all(r in known for r in reqs)]


def try_discover(agent, rng) -> str:
    """A chance of working something out alone, weighted by curiosity. Returns
    the technique discovered, or "" — discovery is rare on purpose, so a world
    that gets anywhere got there by teaching."""
    options = available_to(agent.techniques)
    if not options:
        return ""
    p = DISCOVERY_BASE * (0.4 + agent.drives.get("curiosity", 0.3))
    if rng.random() >= p * len(options):
        return ""
    return options[rng.randrange(len(options))]


def yield_multiplier(agent, kind: str) -> float:
    if kind == "food" and "gleaning" in agent.techniques:
        return 1.0 + FOOD_YIELD_BONUS
    if kind == "wood" and "coppicing" in agent.techniques:
        return 1.0 + WOOD_YIELD_BONUS
    return 1.0


def meal_multiplier(agent) -> float:
    if "kiln" in agent.techniques:
        return 1.0 + MEAL_MAJOR_BONUS
    if "drying" in agent.techniques:
        return 1.0 + MEAL_BONUS
    return 1.0


def repair_multiplier(agent) -> float:
    return 1.0 + REPAIR_BONUS if "joinery" in agent.techniques else 1.0


def teachable(teacher, student) -> list:
    """What the teacher knows, the student lacks, and the student can absorb."""
    return [t for t in teacher.techniques
            if t not in student.techniques
            and all(r in student.techniques for r in TECHNIQUES[t][0])]


def known_depth(agents) -> int:
    best = 0
    for a in agents:
        for t in a.techniques:
            best = max(best, depth(t))
    return best


def breadth(agents) -> float:
    """Mean number of living agents holding each technique that anyone holds."""
    counts = {}
    for a in agents:
        for t in a.techniques:
            counts[t] = counts.get(t, 0) + 1
    return sum(counts.values()) / len(counts) if counts else 0.0
