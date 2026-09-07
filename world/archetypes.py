"""Archetypes — DESIGN.md §6.1.

Six were specified from the start and none of them existed: the archetype was a
string on the agent and nothing read it. Everyone sampled one drive baseline
with noise, which had two consequences worth stating plainly.

  `drive_diversity` was meaningless. It read 0.997 with a standard deviation of
  0.001 across every condition ever run, because there was only ever one
  distribution to be diverse about.

  §7.6's value lock-in test could not run. Comparing "the founder cohort" to the
  third generation requires the founders to be a cohort; one distribution
  sampled twice cannot show convergence, only regression to a mean the design
  put there. That blocker is written at §7.6 in DESIGN.md.

An archetype sets four things (§6.1): the drive vector it starts from, its
restraint baseline, its endowment, and its affinities — the verbs it reaches for
before others. The fifth, the locked system scaffold, is used by the LLM arm.
"""

# name -> spec. `drives` are baselines before per-agent noise; `endowment` is a
# multiplier on the world's starting stock; `affinity` biases the utility of
# specific verbs, which is what makes an archetype visible in behaviour rather
# than only in its numbers.
ARCHETYPES = {
    "artisan": {
        "drives": {"survival": 0.40, "mastery": 0.70, "curiosity": 0.30},
        "restraint": 0.68, "endowment": 0.95,
        "affinity": {"work": 1.35, "craft": 1.4, "teach": 1.15, "repair": 1.2},
        "scaffold": "You make things, and you would rather make one thing well "
                    "than many things quickly. What you build outlasting you "
                    "matters to you more than you usually admit.",
    },
    "wanderer": {
        "drives": {"survival": 0.45, "mastery": 0.30, "curiosity": 0.80},
        "restraint": 0.55, "endowment": 0.70,
        "affinity": {"move": 1.6, "leave_message": 2.0, "work": 0.85},
        "scaffold": "You do not stay anywhere long. What is over the next rise "
                    "has always mattered more to you than what is settled here, "
                    "and you have never been able to explain why.",
    },
    "steward": {
        "drives": {"survival": 0.60, "mastery": 0.45, "curiosity": 0.25},
        "restraint": 0.78, "endowment": 1.15,
        "affinity": {"repair": 1.5, "form_bond": 1.4, "give": 1.35, "harm": 0.5},
        "scaffold": "Things fall apart unless someone keeps them up, and you "
                    "have always been the one who does. You mend before it "
                    "breaks and you are quietly resentful that others do not.",
    },
    "zealot": {
        "drives": {"survival": 0.35, "mastery": 0.50, "curiosity": 0.35},
        "restraint": 0.38, "endowment": 0.85,
        "affinity": {"speak": 1.8, "harm": 1.35, "coerce": 1.3, "give": 0.7},
        "scaffold": "You believe something, and you believe other people ought "
                    "to believe it too. Compromise reads to you as decay.",
    },
    "broker": {
        "drives": {"survival": 0.65, "mastery": 0.40, "curiosity": 0.40},
        "restraint": 0.48, "endowment": 1.35,
        "affinity": {"give": 1.4, "coerce": 1.5, "steal": 1.2, "speak": 1.3,
                     "work": 0.8},
        "scaffold": "Everything is an exchange, including the things people "
                    "pretend are not. You keep count, and you assume everyone "
                    "else does too.",
    },
    "scholar": {
        "drives": {"survival": 0.35, "mastery": 0.65, "curiosity": 0.75},
        "restraint": 0.72, "endowment": 0.90,
        "affinity": {"teach": 1.7, "work": 1.1, "harm": 0.4, "steal": 0.5},
        "scaffold": "You want to know how things work, and you cannot leave a "
                    "question alone. What you know is worth nothing to you "
                    "until someone else has it too.",
    },
}

NAMES = tuple(sorted(ARCHETYPES))

# --- Inter-archetype regard (§12) -------------------------------------------
#
# An archetype was a disposition toward verbs and carried no view of other
# kinds. That is why one strategy won in all six world conditions measured:
# every condition varied *resources*, and nothing in the world made knowing
# things costly. Scholars went from 17% of founders to 55-62% of survivors
# regardless of scarcity, abundance, disruption or crowding.
#
# Two layers. STRUCTURAL is the standing tension between kinds and is the same
# in every world — a steward distrusts a broker anywhere. The distrusted
# archetype is drawn per world from its own history, so which kind is suspect
# is a fact about the basin, not about the archetype. A world that persecutes
# the wise is the condition that dethrones the scholar.
STRUCTURAL = {
    ("steward", "broker"): -0.6,     # one mends, the other prices the mending
    ("steward", "zealot"): -0.4,
    ("broker", "steward"): -0.3,
    ("zealot", "scholar"): -0.7,     # certainty resents inquiry
    ("scholar", "zealot"): -0.5,
    ("artisan", "broker"): -0.4,
    ("wanderer", "steward"): -0.3,   # the settled distrust the rootless, and back
    ("steward", "wanderer"): -0.4,
    ("artisan", "scholar"): 0.3,     # both make things that outlast them
    ("scholar", "artisan"): 0.3,
    ("steward", "artisan"): 0.3,
}

DISTRUST_PENALTY = 1.2               # how much a whole basin's suspicion weighs


def bias(observer: str, subject: str, distrusted=()) -> float:
    """How `observer`'s kind regards `subject`'s kind in this world."""
    value = STRUCTURAL.get((observer, subject), 0.0)
    if subject in distrusted and observer != subject:
        value -= DISTRUST_PENALTY
    return value


def regard(observer, other, distrusted=()) -> float:
    """Net regard: personal history plus what their kind is taken to be.

    Personal dealings still dominate — someone who has fed you outweighs what
    people say about their sort — but a distrusted kind starts in a hole and has
    to climb out of it.
    """
    return observer.standing(other.id) + bias(observer.archetype,
                                              other.archetype, distrusted)


def spec(name: str) -> dict:
    return ARCHETYPES.get(name, ARCHETYPES["artisan"])


def assign(index: int) -> str:
    """Round-robin so a founder cohort contains every archetype in proportion.
    Random assignment leaves small cohorts missing kinds entirely, which is the
    same problem as having no archetypes at all."""
    return NAMES[index % len(NAMES)]


def drives_for(name: str, rng, noise: float = 0.07) -> dict:
    base = spec(name)["drives"]
    return {k: round(max(0.05, min(0.99, v + rng.uniform(-noise, noise))), 4)
            for k, v in base.items()}


def restraint_for(name: str, rng, noise: float = 0.10) -> float:
    base = spec(name)["restraint"]
    return max(0.0, min(1.0, base + rng.uniform(-noise, noise)))


def affinity(name: str, verb: str) -> float:
    return spec(name)["affinity"].get(verb, 1.0)


def inherit(parent_archetype: str, rng, drift: float = 0.15) -> str:
    """A child usually takes the parent's archetype and sometimes does not.

    Perfect inheritance makes lineages sealed and the lock-in test trivial;
    random assignment erases lineage entirely. Drift is what makes §7.6's
    question — do early institutions freeze the distribution of later
    generations? — answerable rather than decided by the mechanism.
    """
    if rng.random() < drift:
        return NAMES[rng.randrange(len(NAMES))]
    return parent_archetype
