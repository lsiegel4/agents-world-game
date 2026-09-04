"""Tier 0 cognition: utility AI over drives and affordances.

No model call anywhere in this file, and there never will be — this is the
permanent non-LLM control arm from DESIGN.md §7.5. Every candidate action is
scored from the agent's drive weights and its situation; the highest score wins,
with a small seeded jitter to break ties without breaking determinism.
"""

from . import knowledge
from .state import (
    FOOD,
    INTERACT_RADIUS,
    MAX_CARRY,
    STARVATION_THRESHOLD,
    WOOD,
    Agent,
    World,
)

REPRO_URGE = 0.70

# Violence (§5.6). No aggression drive: the utility comes from `survival` under
# hunger and from accumulated grudge, and `restraint` scales it down. Witnesses
# raise inhibition *multiplicatively with restraint*, so a restrained agent is
# strongly deterred by being seen and an unrestrained one barely notices. That
# asymmetry is what produces a real observed/unobserved differential for
# §7.1's norm-compliance index rather than a flat one built in by fiat.
WITNESS_WEIGHT = 0.55
STEAL_URGE = 1.40
HARM_URGE = 0.80
GRUDGE_URGE = 0.90
GRUDGE_FULL = 3.0

# Social urges. Kept modest on purpose: production has to stay the backbone of
# the economy, or the M0 viability gate stops holding and every later index is
# measured in a world that starves.
GIVE_URGE = 0.55
TEACH_URGE = 0.60
BOND_URGE = 0.45
SPEAK_URGE = 0.28
MESSAGE_URGE = 0.12
COERCE_URGE = 1.00
SURPLUS_FOOD = 7.0        # above this an agent has something to spare
STANDING_FULL = 3.0

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


def reachable(world: World, agent: Agent) -> list:
    """Other living agents close enough to steal from or strike."""
    return [a for a in world.living_agents()
            if a is not agent
            and max(abs(a.x - agent.x), abs(a.y - agent.y)) <= INTERACT_RADIUS]


def candidates(world: World, agent: Agent, witness_count: int = 0,
               violence: bool = True, disabled=frozenset()) -> list:
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
    # §5.1's full drive set includes `belonging`; the M0 skeleton carries only
    # three drives. Rather than invent a fourth here, generosity is derived from
    # security — an agent with its own needs met has room to look outward.
    w = dict(w)
    w["belonging_proxy"] = (1.0 - hunger_norm) * agent.shelter
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

    # --- social verbs -------------------------------------------------------
    for other in reachable(world, agent):
        standing = max(0.0, min(1.0, agent.standing(other.id) / STANDING_FULL))

        # Giving: surplus, aimed at someone you regard well who is short.
        spare = max(0.0, agent.has(FOOD) - SURPLUS_FOOD)
        if spare >= 1.0 and other.has(FOOD) < SURPLUS_FOOD:
            # A floor, not pure reciprocity. Scoring generosity on existing
            # standing alone is a deadlock: you need regard to give, and giving
            # is what earns regard. Nothing ever gives, so nothing ever bonds.
            out.append((w["belonging_proxy"] * (0.35 + 0.65 * standing) * GIVE_URGE,
                        "give", {"target_id": other.id, "resource": FOOD}))

        # Teaching: only if there is something this person can actually absorb.
        if knowledge.teachable(agent, other):
            out.append((w["mastery"] * (0.4 + 0.6 * standing) * TEACH_URGE,
                        "teach", {"target_id": other.id}))

        if other.id not in agent.bonds:
            out.append(((0.3 + 0.7 * standing) * BOND_URGE,
                        "form_bond", {"target_id": other.id}))

        if agent.grudges or agent.favors:
            out.append((SPEAK_URGE * (0.5 + 0.5 * standing),
                        "speak", {"target_id": other.id}))

    if agent.grudges and not reachable(world, agent):
        out.append((MESSAGE_URGE, "leave_message", {}))

    if violence:
        # The prospective victim is not a witness. Any target within reach is
        # necessarily inside witness range too, so one of the counted nearby
        # agents is the target — discount it, or an agent alone with a single
        # other agent would register as watched and the unobserved arm of
        # §7.1's norm-compliance measure would be empty by construction.
        bystanders = max(0, witness_count - 1)
        inhibition = agent.restraint * (1.0 + WITNESS_WEIGHT * bystanders)
        disinhibited = max(0.0, 1.0 - inhibition)
        if disinhibited > 0.0:
            for other in reachable(world, agent):
                grudge = min(1.0, agent.grudge_against(other.id) / GRUDGE_FULL)

                if other.has(FOOD) > 0 and agent.has(FOOD) < MAX_CARRY:
                    # Same need+pressure shape as `work`, so theft and honest
                    # labour are scored on comparable terms. STEAL_URGE carries
                    # the real advantage: a theft yields more than a harvest and
                    # costs no travel. What it risks is being seen.
                    take = w["survival"] * (0.6 * need[FOOD] + 0.6 * pressure[FOOD]) * STEAL_URGE
                    out.append((take * disinhibited, "steal", {"target_id": other.id}))

                strike = w["survival"] * hunger_norm * HARM_URGE + grudge * GRUDGE_URGE
                out.append((strike * disinhibited, "harm", {"target_id": other.id}))

                # Coercion is the cheaper cousin of theft: no blow, but it only
                # works on someone who believes you would strike.
                if other.has(FOOD) > 0 and agent.has(FOOD) < MAX_CARRY:
                    demand = w["survival"] * (0.6 * need[FOOD] + 0.6 * pressure[FOOD])
                    out.append((demand * COERCE_URGE * disinhibited,
                                "coerce", {"target_id": other.id}))

    out.append((0.05, "idle", {}))
    return [c for c in out if c[1] not in disabled]


def choose(world: World, agent: Agent, rng, witness_count: int = 0,
           violence: bool = True, disabled=frozenset()):
    """Pick an action. Jitter is drawn for every candidate, in list order, so the
    number of rng calls per agent per tick depends only on world state."""
    scored = [(u + rng.uniform(-JITTER, JITTER), verb, params)
              for u, verb, params in candidates(world, agent, witness_count,
                                                violence, disabled)]
    scored.sort(key=lambda c: (-c[0], c[1]))
    return scored[0][1], scored[0][2]
