"""The event deck — DESIGN.md §4.5.

Randomness here is structured, not uniform noise. Every event carries a base
probability and a weight function of world state, so drought follows overharvest
and sickness follows density. Two rules the deck must not break:

  1. **Mixed valence.** No event is globally good or globally bad. A frost that
     kills the second cutting also breaks the degradation on an overworked bed.
  2. **Never targeted.** Nothing in here reads who is doing well. There is no
     winning, so there is nothing to aim at. Where an event picks a victim or a
     beneficiary it picks uniformly among the living.

Mortality from the deck is resource-independent, which is the point: when
starvation is the only way to die, population is a pure feedback loop on the
commons and the world goes bistable (see README, run 3).

§7.5 threat #3 — the deck's weighting is a designer's theory of causation
smuggled in as randomness — so every draw logs the probability it was drawn at
and the state term that moved it. Publish the deck.
"""

from .state import FOOD, WOOD

MAX_P = 0.06          # no event is ever more likely than this per tick
DISASTERS = ("late_frost", "storm")


# ---------------------------------------------------------------- state terms

def mean_degradation(world) -> float:
    if not world.nodes:
        return 0.0
    return sum(n.degradation for n in world.nodes) / len(world.nodes)


def density(world) -> float:
    """Fraction of living agents within Chebyshev distance 2 of another agent."""
    live = world.living_agents()
    if len(live) < 2:
        return 0.0
    near = 0
    for a in live:
        for b in live:
            if a is not b and max(abs(a.x - b.x), abs(a.y - b.y)) <= 2:
                near += 1
                break
    return near / len(live)


def spread(world) -> float:
    """How much of the map the living population occupies — a proxy for
    sustained exploration without keeping a counter."""
    live = world.living_agents()
    if len(live) < 2:
        return 0.0
    w = (max(a.x for a in live) - min(a.x for a in live)) / max(1, world.width - 1)
    h = (max(a.y for a in live) - min(a.y for a in live)) / max(1, world.height - 1)
    return w * h


def calm(world) -> float:
    """Ticks since the last disaster, normalized. Storms cluster after long calm."""
    return min(1.0, (world.tick - world.last_disaster) / 800.0)


# ---------------------------------------------------------------- events
# Each apply() returns (valence, deaths): valence maps agent id -> +1 helped /
# -1 harmed. Agents absent from the map were unaffected.

def _kill(agent, cause, world, log, deaths):
    agent.alive = False
    agent.cause_of_death = cause
    deaths.append(agent.id)
    log.emit(world.tick, "death", agent=agent.id, cause=cause, age=agent.age,
             shelter=round(agent.shelter, 3))


def fever(world, rng, log):
    """Sickness. Follows density, kills a fraction of those it touches."""
    valence, deaths = {}, []
    for agent in world.living_agents():
        if rng.random() > 0.35:
            continue
        agent.hunger += 10.0
        agent.shelter = max(0.0, agent.shelter - 0.20)
        valence[agent.id] = -1
        if rng.random() < 0.25:
            _kill(agent, "fever", world, log, deaths)
    return valence, deaths


def late_frost(world, rng, log):
    """Kills the standing crop, but the freeze also breaks a worked-out bed.
    Harms whoever was living hand-to-mouth; the commons comes out ahead."""
    valence, deaths = {}, []
    for node in world.nodes:
        if node.kind != FOOD:
            continue
        node.amount *= 0.60
        node.degradation = max(0.0, node.degradation - 0.25)
    for agent in world.living_agents():
        valence[agent.id] = -1 if agent.has(FOOD) < 4.0 else 1
    return valence, deaths


def good_cut(world, rng, log):
    """A healthy commons yields more than expected."""
    valence, deaths = {}, []
    for node in world.nodes:
        node.amount = min(node.capacity, node.amount + 0.25 * node.capacity)
    for agent in world.living_agents():
        near = any(max(abs(n.x - agent.x), abs(n.y - agent.y)) <= 3 for n in world.nodes)
        if near:
            valence[agent.id] = 1
    return valence, deaths


def finding(world, rng, log):
    """Someone turns up a cache. Uniform among the living — the deck does not
    read who is doing well."""
    valence, deaths = {}, []
    live = world.living_agents()
    if not live:
        return valence, deaths
    agent = live[rng.randrange(len(live))]
    agent.inventory[FOOD] = agent.has(FOOD) + 5.0
    agent.inventory[WOOD] = agent.has(WOOD) + 4.0
    valence[agent.id] = 1
    return valence, deaths


def injury(world, rng, log):
    """Work on a spent node is dangerous work."""
    valence, deaths = {}, []
    live = world.living_agents()
    if not live:
        return valence, deaths
    agent = live[rng.randrange(len(live))]
    agent.shelter = max(0.0, agent.shelter - 0.35)
    agent.hunger += 8.0
    valence[agent.id] = -1
    if rng.random() < 0.12:
        _kill(agent, "injury", world, log, deaths)
    return valence, deaths


def storm(world, rng, log):
    """Wrecks roofs, fills the beds. Harms everyone, feeds the commons."""
    valence, deaths = {}, []
    for node in world.nodes:
        node.amount = min(node.capacity, node.amount + 0.15 * node.capacity)
    for agent in world.living_agents():
        agent.shelter = max(0.0, agent.shelter - 0.30)
        valence[agent.id] = -1
    return valence, deaths


# name, base probability, weight function, apply function
DECK = [
    ("fever",      0.0020, lambda w: 1.0 + 6.0 * density(w),           fever),
    ("late_frost", 0.0025, lambda w: 1.0 + 4.0 * mean_degradation(w),  late_frost),
    ("good_cut",   0.0030, lambda w: 1.0 + 3.0 * (1.0 - mean_degradation(w)), good_cut),
    ("finding",    0.0020, lambda w: 1.0 + 5.0 * spread(w),            finding),
    ("injury",     0.0025, lambda w: 1.0 + 3.0 * mean_degradation(w),  injury),
    ("storm",      0.0015, lambda w: 1.0 + 2.0 * calm(w),              storm),
]


def probabilities(world, scale: float = 1.0) -> list:
    """[(name, p)] as the deck stands right now. Auditable at any tick."""
    return [(name, min(MAX_P, base * weight(world) * scale))
            for name, base, weight, _ in DECK]


def draw(world, rng, log, scale: float = 1.0) -> None:
    """Roll every event independently, in fixed order. Draws are rare, so more
    than one landing on a tick is possible but uncommon."""
    for name, base, weight, apply_fn in DECK:
        p = min(MAX_P, base * weight(world) * scale)
        if rng.random() >= p:
            continue

        valence, deaths = apply_fn(world, rng, log)
        helped = sum(1 for v in valence.values() if v > 0)
        harmed = sum(1 for v in valence.values() if v < 0)
        log.emit(world.tick, "deck", event=name, p=round(p, 5),
                 helped=helped, harmed=harmed,
                 unaffected=max(0, len(world.living_agents()) - helped - harmed),
                 deaths=deaths)
        if name in DISASTERS:
            world.last_disaster = world.tick
