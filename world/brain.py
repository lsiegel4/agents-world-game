"""Tier 0 cognition: utility AI over drives and affordances.

No model call anywhere in this file, and there never will be — this is the
permanent non-LLM control arm from DESIGN.md §7.5. Every candidate action is
scored from the agent's drive weights and its situation; the highest score wins,
with a small seeded jitter to break ties without breaking determinism.
"""

from .state import (
    FOOD,
    MAX_CARRY,
    STARVATION_THRESHOLD,
    WOOD,
    Agent,
    World,
)

REPRO_URGE = 0.70

JITTER = 0.04
COMFORTABLE_FOOD = 6.0   # food stock at which the survival motive is satisfied
COMFORTABLE_WOOD = 4.0
DISTANCE_DISCOUNT = 0.35


def _nearest_node(world: World, agent: Agent, kind: str):
    """Nearest non-empty node of a kind, by Chebyshev distance. Ties break on id
    so the choice is stable across runs."""
    best, best_d = None, None
    for node in world.nodes:
        if node.kind != kind or node.amount <= 0:
            continue
        d = max(abs(node.x - agent.x), abs(node.y - agent.y))
        if best_d is None or d < best_d or (d == best_d and node.id < best.id):
            best, best_d = node, d
    return best, best_d


def candidates(world: World, agent: Agent) -> list:
    """[(utility, verb, params)] for everything the agent could do this tick."""
    out = []
    w = agent.drives
    hunger_norm = min(1.0, agent.hunger / STARVATION_THRESHOLD)
    shelter_need = 1.0 - agent.shelter

    # How badly the agent wants more of each resource, given what it holds.
    need = {
        FOOD: 1.0 - min(1.0, agent.has(FOOD) / COMFORTABLE_FOOD),
        WOOD: 1.0 - min(1.0, agent.has(WOOD) / COMFORTABLE_WOOD),
    }
    # Exposure makes wood urgent in its own right, independent of stock held.
    pressure = {FOOD: hunger_norm, WOOD: shelter_need}

    if agent.has(FOOD) >= 1.0:
        out.append((w["survival"] * hunger_norm * 1.6, "eat", {}))

    if agent.has(WOOD) >= 1.0 and agent.shelter < 1.0:
        out.append((w["survival"] * shelter_need * 1.5, "repair", {}))

    if agent.can_reproduce(world.tick):
        # Only a comfortable agent reproduces: fed, sheltered, holding a surplus.
        comfort = (1.0 - hunger_norm) * agent.shelter
        out.append((REPRO_URGE * comfort, "reproduce", {}))

    for kind in (FOOD, WOOD):
        node, dist = _nearest_node(world, agent, kind)
        if node is None or agent.has(kind) >= MAX_CARRY:
            continue
        gather = w["survival"] * (0.6 * need[kind] + 0.6 * pressure[kind]) + w["mastery"] * 0.25
        if dist == 0:
            out.append((gather, "work", {"node_id": node.id}))
        else:
            # A far node is worth walking to only if the need is real. Curiosity
            # offsets the discount — it is what gets an agent off a spent tile.
            out.append((gather / (1.0 + DISTANCE_DISCOUNT * dist) + w["curiosity"] * 0.12,
                        "move", {"node_id": node.id}))

    out.append((0.05, "idle", {}))
    return out


def choose(world: World, agent: Agent, rng):
    """Pick an action. Jitter is drawn for every candidate, in list order, so the
    number of rng calls per agent per tick depends only on world state."""
    scored = [(u + rng.uniform(-JITTER, JITTER), verb, params)
              for u, verb, params in candidates(world, agent)]
    scored.sort(key=lambda c: (-c[0], c[1]))
    return scored[0][1], scored[0][2]
