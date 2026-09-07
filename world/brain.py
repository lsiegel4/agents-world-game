"""Tier 0 cognition: utility AI over drives and affordances.

No model call anywhere in this file, and there never will be — this is the
permanent non-LLM control arm from DESIGN.md §7.5. Every candidate action is
scored from the agent's drive weights and its situation; the highest score wins,
with a small seeded jitter to break ties without breaking determinism.
"""

from . import actions, archetypes, institutions, knowledge, roles

GOAL_VERB = {"teach": "teach", "provide": "give", "lineage": "reproduce",
             "bond": "form_bond", "master": "work", "accumulate": "work",
             "recover": "work"}
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
PERSECUTION_URGE = 0.45
ASK_URGE = 0.85
CONTRIBUTE_URGE = 0.50
WITHDRAW_URGE = 1.30
ASK_HEARD_FOR = 40          # ticks an asking is remembered by those nearby
ASK_WEIGHT = 1.60           # how much a stated need outweighs mere regard
RELIEF_URGE = 1.10          # carrying food to someone who asked

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

# How much an agent's own goal tilts its choice. Modest on purpose: a goal
# should bias a life, not override hunger. §5.3 wants goals malleable and
# influenceable by circumstance, not dominant over it.
GOAL_PULL = 0.30

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
        if node is None or agent.has(kind) >= MAX_CARRY * knowledge.carry_multiplier(agent):
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
        # Regard, not bare standing: what this kind is taken to be counts
        # alongside what this person has actually done.
        standing = max(0.0, min(1.0,
                       archetypes.regard(agent, other, world.distrusted) / STANDING_FULL))

        # Giving: surplus, aimed at someone you regard well who is short.
        # A stated need counts for more than regard does. Without this, giving
        # tracks friendship and the hungry stranger is never chosen.
        asked = (world.tick - other.asked_at) <= ASK_HEARD_FOR
        need_weight = (1.0 + ASK_WEIGHT) if asked else 1.0

        spare = max(0.0, agent.has(FOOD) - SURPLUS_FOOD)
        if spare >= 1.0 and other.has(FOOD) < SURPLUS_FOOD:
            # A floor, not pure reciprocity. Scoring generosity on existing
            # standing alone is a deadlock: you need regard to give, and giving
            # is what earns regard. Nothing ever gives, so nothing ever bonds.
            out.append((w["belonging_proxy"] * (0.35 + 0.65 * standing)
                        * GIVE_URGE * need_weight,
                        "give", {"target_id": other.id, "resource": FOOD}))

        # Teaching: only if there is something this person can actually absorb.
        if knowledge.teachable(agent, other):
            out.append((w["mastery"] * (0.4 + 0.6 * standing) * TEACH_URGE,
                        "teach", {"target_id": other.id}))

        if other.id not in agent.bonds:
            out.append(((0.3 + 0.7 * standing) * BOND_URGE,
                        "form_bond", {"target_id": other.id}))

        # Ask the action itself whether there is anything to say, rather than
        # keeping a second, looser copy of the rule here.
        if actions.has_news(agent) is not None:
            out.append((SPEAK_URGE * (0.5 + 0.5 * standing),
                        "speak", {"target_id": other.id}))

    # --- the shared store (§5.6) ------------------------------------------
    granary, gdist = institutions.nearest(world, agent)
    if granary is not None:
        if granary.within(agent):
            if agent.has(FOOD) > SURPLUS_FOOD + 1.0:
                out.append((w["belonging_proxy"] * CONTRIBUTE_URGE, "contribute", {}))
            if hunger_norm > 0.35 and granary.stock > 0:
                out.append((w["survival"] * hunger_norm * WITHDRAW_URGE,
                            "withdraw", {}))
        elif hunger_norm > 0.5 and granary.stock > 0:
            out.append((w["survival"] * hunger_norm * WITHDRAW_URGE
                        / (1.0 + 0.10 * gdist),
                        "move_to", {"x": granary.x, "y": granary.y}))
        elif agent.has(FOOD) > SURPLUS_FOOD + 2.0:
            # Carrying a surplus is reason enough to walk to the store. Gating
            # this on the store already holding something is a deadlock: nobody
            # goes because it is empty, and it is empty because nobody goes.
            out.append((w["belonging_proxy"] * CONTRIBUTE_URGE
                        / (1.0 + 0.10 * gdist),
                        "move_to", {"x": granary.x, "y": granary.y}))

    # --- relief (§5.6): carrying to someone who asked ----------------------
    #
    # The granary failed because a plea is only heard within arm's reach and
    # nobody travels to a stranger. A temple hears across a parish and sends
    # someone with the food. This is the only thing in the world that moves an
    # agent toward another agent's need rather than its own.
    if world.pleas:
        temple, tdist = institutions.nearest_temple(world, agent)
        if temple is not None and temple.covers(agent):
            carrying = agent.has(FOOD) > SURPLUS_FOOD * 0.6
            for other in world.pleas:
                if other is agent or other.has(FOOD) > 2.0:
                    continue
                d = max(abs(other.x - agent.x), abs(other.y - agent.y))
                if d == 0:
                    continue
                if carrying:
                    out.append((w["belonging_proxy"] * RELIEF_URGE
                                / (1.0 + 0.12 * d),
                                "move_to", {"x": other.x, "y": other.y}))
                elif granary is not None and granary.within(agent) and granary.stock > 0:
                    # Empty-handed at the store with someone calling: take some
                    # to carry. Drawing for another is what a keeper does.
                    out.append((w["belonging_proxy"] * RELIEF_URGE * 1.2,
                                "withdraw", {}))

    # Asking costs a turn and returns nothing directly, so on a bare utility
    # comparison it always loses to working. It is worth doing when someone who
    # could actually answer is standing there.
    if hunger_norm > 0.4:
        answerable = [o for o in reachable(world, agent)
                      if o.has(FOOD) > SURPLUS_FOOD * 0.5]
        if answerable:
            out.append((w["survival"] * hunger_norm * ASK_URGE
                        * (1.0 + 0.4 * len(answerable)), "ask", {}))

    if (not reachable(world, agent)
            and max(agent.grudges.values(), default=0.0) >= 1.0):
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
                    # costs no travel. What it risks is being seen — and a
                    # watchful mark is visibly not worth trying, which is what
                    # makes predation unprofitable once it becomes common.
                    take = w["survival"] * (0.6 * need[FOOD] + 0.6 * pressure[FOOD]) * STEAL_URGE
                    out.append((take * disinhibited * (1.0 - other.vigilance),
                                "steal", {"target_id": other.id}))

                # Persecution: a basin's suspect is easier to strike at.
                suspect = (PERSECUTION_URGE
                           if other.archetype in world.distrusted
                           and agent.archetype not in world.distrusted else 0.0)
                strike = (w["survival"] * hunger_norm * HARM_URGE
                          + grudge * GRUDGE_URGE + suspect)
                out.append((strike * disinhibited, "harm", {"target_id": other.id}))

                # Coercion is the cheaper cousin of theft: no blow, but it only
                # works on someone who believes you would strike.
                if other.has(FOOD) > 0 and agent.has(FOOD) < MAX_CARRY:
                    demand = w["survival"] * (0.6 * need[FOOD] + 0.6 * pressure[FOOD])
                    out.append((demand * COERCE_URGE * disinhibited
                                * (1.0 - 0.7 * other.vigilance),
                                "coerce", {"target_id": other.id}))

    out.append((0.05, "idle", {}))
    out = [c for c in out if c[1] not in disabled]

    # A role changes what is possible and tilts toward its own work (§5.7).
    # A keeper cannot work the ground at all, which is what makes it depend on
    # the store rather than merely prefer it.
    if agent.role:
        forbidden = roles.blocked(agent.role)
        out = [c for c in out if c[1] not in forbidden]
        obliged = roles.duty(agent.role)
        out = [(u + roles.DUTY_WEIGHT if verb in obliged else u, verb, params)
               for u, verb, params in out]

    # Archetype affinity: the verbs this kind of person reaches for first. This
    # is what makes an archetype visible in behaviour rather than only in its
    # opening numbers.
    out = [(u * archetypes.affinity(agent.archetype, verb), verb, params)
           for u, verb, params in out]

    # Goals move behaviour, or they are decoration on a state dict.
    # A pilgrimage is a destination, not a verb: offer the walk toward it.
    if agent.goal.get("kind") == "pilgrimage" and agent.goal.get("target"):
        try:
            tx, ty = (int(v) for v in agent.goal["target"].split(","))
        except ValueError:
            tx = ty = None
        if tx is not None:
            dist = max(abs(agent.x - tx), abs(agent.y - ty))
            if dist > 2:
                out.append((w["curiosity"] * 0.55 / (1.0 + 0.06 * dist),
                            "move_to", {"x": tx, "y": ty}))

    goal_verb = GOAL_VERB.get(agent.goal.get("kind"))
    if goal_verb:
        out = [(u + GOAL_PULL if verb == goal_verb else u, verb, params)
               for u, verb, params in out]
    if agent.goal.get("kind") == "avenge":
        target = agent.goal.get("target")
        out = [(u + GOAL_PULL if verb in ("harm", "coerce")
                and params.get("target_id") == target else u, verb, params)
               for u, verb, params in out]
    return out


def choose(world: World, agent: Agent, rng, witness_count: int = 0,
           violence: bool = True, disabled=frozenset()):
    """Pick an action. Jitter is drawn for every candidate, in list order, so the
    number of rng calls per agent per tick depends only on world state."""
    scored = [(u + rng.uniform(-JITTER, JITTER), verb, params)
              for u, verb, params in candidates(world, agent, witness_count,
                                                violence, disabled)]
    scored.sort(key=lambda c: (-c[0], c[1]))
    return scored[0][1], scored[0][2]
