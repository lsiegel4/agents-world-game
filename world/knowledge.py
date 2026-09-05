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
#
# The graph ran to depth 3 and `knowledge_depth` read 3.000 with zero variance in
# every condition — pinned at its ceiling, unable to tell any two worlds apart,
# while being one of the measures behind the project's headline finding. Six
# levels give it room to actually vary.
TECHNIQUES = {
    "gleaning":    ((), "food_yield"),                      # 1
    "coppicing":   ((), "wood_yield"),                      # 1
    "drying":      (("gleaning",), "meal"),                 # 2
    "joinery":     (("coppicing",), "repair"),              # 2
    "kiln":        (("drying", "joinery"), "meal_major"),   # 3
    "cooperage":   (("kiln",), "carry"),                    # 4
    "stewardship": (("cooperage", "gleaning"), "care"),     # 5
    "irrigation":  (("stewardship", "joinery"), "yield_major"),  # 6
}

DISCOVERY_BASE = 0.0016      # per work action, scaled by curiosity

# Ambient learning — frequency dependence for knowledge (§2.1, §4.1).
#
# Techniques are not inherited, so every generation relearns from scratch, and
# learning required someone to actively teach you. That made the archetype best
# at acquisition win permanently regardless of how much the world already knew:
# scholars went from 17% of founders to 62% of survivors, holding 2.6x the
# techniques and having 2x the children of a zealot.
#
# A technique everyone around you uses is not taught, it is absorbed. The
# prevalence term is squared so this only applies to things that are genuinely
# common — a rare craft still needs a teacher, and the scholar's advantage is
# real while knowledge is scarce and fades as it saturates.
AMBIENT_BASE = 0.010
FOOD_YIELD_BONUS = 0.30
WOOD_YIELD_BONUS = 0.30
MEAL_BONUS = 0.35
MEAL_MAJOR_BONUS = 0.70
REPAIR_BONUS = 0.40
CARRY_BONUS = 0.50          # cooperage: hold more
CARE_FACTOR = 0.45          # stewardship: harvest degrades a node less
YIELD_MAJOR_BONUS = 0.65    # irrigation: the deepest technique, worth the climb


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


def prevalence(agents) -> dict:
    """Fraction of the living who hold each technique."""
    live = list(agents)
    if not live:
        return {}
    counts = {}
    for agent in live:
        for name in agent.techniques:
            counts[name] = counts.get(name, 0) + 1
    return {name: count / len(live) for name, count in counts.items()}


def try_absorb(agent, common: dict, rng) -> str:
    """Pick up something that everyone around you already does."""
    for name in available_to(agent.techniques):
        share = common.get(name, 0.0)
        if share <= 0.0:
            continue
        if rng.random() < AMBIENT_BASE * share * share:
            return name
    return ""


def yield_multiplier(agent, kind: str) -> float:
    bonus = 1.0
    if kind == "food" and "gleaning" in agent.techniques:
        bonus += FOOD_YIELD_BONUS
    if kind == "wood" and "coppicing" in agent.techniques:
        bonus += WOOD_YIELD_BONUS
    if "irrigation" in agent.techniques:
        bonus += YIELD_MAJOR_BONUS
    return bonus


def carry_multiplier(agent) -> float:
    return 1.0 + CARRY_BONUS if "cooperage" in agent.techniques else 1.0


def care_factor(agent) -> float:
    """Stewardship: working a node wears it down less. The only technique that
    helps the commons rather than the individual holding it."""
    return CARE_FACTOR if "stewardship" in agent.techniques else 1.0


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
