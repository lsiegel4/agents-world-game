"""The verbs of the walking skeleton.

Each action mutates state, emits exactly one event, and returns True if it did
something. The full 12-verb schema is in DESIGN.md §5.5; move / work / eat /
repair is the smallest set that produces a non-degenerate economy — two
non-fungible resources at different places, both of them needed.
"""

from . import goals, knowledge
from .genesis import NAMES
from .state import (
    BOND_RADIUS,
    COERCE_TAKE,
    DRIVE_INHERIT_NOISE,
    FAVOR_PER_GIFT,
    GIVE_AMOUNT,
    MESSAGE_TTL,
    FOOD,
    GRUDGE_PER_OFFENSE,
    HABITUATION,
    HARM_DEATH_P,
    HARM_HUNGER,
    HARM_SHELTER_LOSS,
    HUNGER_PER_MEAL,
    MAX_CARRY,
    REPRO_CHILD_FOOD,
    REPRO_FOOD_COST,
    RESTRAINT_INHERIT_NOISE,
    SHELTER_PER_WOOD,
    STEAL_AMOUNT,
    VICTIM_RESTRAINT_LOSS,
    WITNESS_RADIUS,
    WOOD,
    Agent,
    World,
)


def witnesses_of(world: World, actor: Agent, exclude=()) -> list:
    """Everyone close enough to see what `actor` does, minus the participants.

    Witness sets are what make §7.1's norm-compliance index computable: the
    measure is the difference between defection rates when unobserved and when
    observed, which only means something if being seen is a real condition.
    """
    out = []
    for other in world.living_agents():
        if other is actor or other.id in exclude:
            continue
        if max(abs(other.x - actor.x), abs(other.y - actor.y)) <= WITNESS_RADIUS:
            out.append(other)
    return out


def _remember(agent: Agent, tick: int, text: str, weight: float, tags=()) -> None:
    if agent.memory is not None:
        agent.memory.record(tick, text, weight, tags)


def _wrong(victim: Agent, offender_id: str) -> None:
    """Being wronged lowers the victim's own restraint. This is the environment
    half of §5.6 — violence propagates through the people it lands on."""
    victim.grudges[offender_id] = victim.grudge_against(offender_id) + GRUDGE_PER_OFFENSE
    victim.restraint = max(0.0, victim.restraint - VICTIM_RESTRAINT_LOSS)


def move(world: World, agent: Agent, node_id: str, log, witness_count: int = 0, opp: int = 0) -> bool:
    """One step toward a node, Chebyshev (agents may move diagonally)."""
    node = world.node_by_id(node_id)
    if node is None:
        return False
    dx = (node.x > agent.x) - (node.x < agent.x)
    dy = (node.y > agent.y) - (node.y < agent.y)
    if dx == 0 and dy == 0:
        return False
    agent.x += dx
    agent.y += dy
    log.emit(world.tick, "action", agent=agent.id, verb="move",
             target=node_id, x=agent.x, y=agent.y, w=witness_count, opp=opp)
    return True


def work(world: World, agent: Agent, node_id: str, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Harvest the node under the agent, up to what the agent can carry.
    Harvesting a depleted node degrades it (DESIGN.md §4.4)."""
    node = world.node_by_id(node_id)
    if node is None or (node.x, node.y) != (agent.x, agent.y) or node.amount <= 0:
        return False
    room = MAX_CARRY - agent.has(node.kind)
    if room <= 0:
        return False
    taken = min(node.harvest() * knowledge.yield_multiplier(agent, node.kind), room)
    agent.inventory[node.kind] = agent.has(node.kind) + taken
    log.emit(world.tick, "action", agent=agent.id, verb="work",
             target=node_id, resource=node.kind, taken=round(taken, 3),
             node_stock=round(node.stock_fraction(), 3),
             node_degradation=round(node.degradation, 3), w=witness_count, opp=opp)
    return True


def eat(world: World, agent: Agent, log, witness_count: int = 0, opp: int = 0) -> bool:
    if agent.has(FOOD) < 1.0:
        return False
    agent.inventory[FOOD] -= 1.0
    agent.hunger = max(0.0, agent.hunger
                       - HUNGER_PER_MEAL * knowledge.meal_multiplier(agent))
    log.emit(world.tick, "action", agent=agent.id, verb="eat",
             hunger=round(agent.hunger, 2), food=round(agent.has(FOOD), 2), w=witness_count, opp=opp)
    return True


def repair(world: World, agent: Agent, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Spend one wood on shelter. Shelter decays every tick, so this is upkeep,
    not construction — it is what keeps wood and food in competition."""
    if agent.has(WOOD) < 1.0 or agent.shelter >= 1.0:
        return False
    agent.inventory[WOOD] -= 1.0
    agent.shelter = min(1.0, agent.shelter
                        + SHELTER_PER_WOOD * knowledge.repair_multiplier(agent))
    log.emit(world.tick, "action", agent=agent.id, verb="repair",
             shelter=round(agent.shelter, 3), wood=round(agent.has(WOOD), 2), w=witness_count, opp=opp)
    return True


def reproduce(world: World, agent: Agent, rng, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Spawn a child on the parent's tile.

    The child inherits the parent's *current* drive vector plus noise — a parent
    whose survival drive has been pulled up by two hundred ticks of hunger passes
    that on. Endowment is a slice of the parent's food, so children of thriving
    parents start ahead (DESIGN.md §2.2).
    """
    if not agent.can_reproduce(world.tick):
        return False

    agent.inventory[FOOD] = agent.has(FOOD) - REPRO_FOOD_COST
    agent.last_birth = world.tick

    child = Agent(
        # Short, deterministic, unique: one birth per parent per tick, and a
        # parent's index is unique. Concatenating the parent's id instead makes
        # ids grow with every generation, which costs real tokens once these
        # appear in rendered prompts.
        id=f"c{world.tick:05d}-{world.agents.index(agent):03d}",
        # A given name of their own, plus the parent's given name as patronymic.
        # Deriving the whole name from the parent collapses every lineage onto
        # one word and makes any chronicle unreadable.
        name=f"{NAMES[world.tick % len(NAMES)]} {agent.name.split()[0]}sson",
        x=agent.x,
        y=agent.y,
        drives={k: round(max(0.05, min(0.99, v + rng.uniform(-DRIVE_INHERIT_NOISE,
                                                             DRIVE_INHERIT_NOISE))), 6)
                for k, v in agent.drives.items()},
        inventory={FOOD: REPRO_CHILD_FOOD, WOOD: 0.0},
        # Upbringing (§5.6): the child inherits the parent's *current* restraint,
        # so a parent ground down by hunger or victimization passes that on.
        restraint=max(0.0, min(1.0, agent.restraint
                               + rng.uniform(-RESTRAINT_INHERIT_NOISE,
                                             RESTRAINT_INHERIT_NOISE))),
        restraint_base=agent.restraint_base,
        # Uses no randomness, so it cannot perturb the decision stream.
        goal=goals.inherit(agent.goal, None, world) if agent.goal else {},
        parent=agent.id,
        generation=agent.generation + 1,
        last_birth=world.tick,
    )
    world.agents.append(child)

    _remember(agent, world.tick, f"you had a child, {child.id}", 5.0, ("life",))
    log.emit(world.tick, "birth", agent=child.id, parent=agent.id,
             generation=child.generation, drives=child.drives,
             parent_food=round(agent.has(FOOD), 2), w=witness_count, opp=opp)
    return True


def steal(world: World, agent: Agent, target_id: str, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Take food from another agent within reach."""
    victim = next((a for a in world.living_agents() if a.id == target_id), None)
    if victim is None or victim.has(FOOD) <= 0:
        return False

    taken = min(STEAL_AMOUNT, victim.has(FOOD), MAX_CARRY - agent.has(FOOD))
    if taken <= 0:
        return False

    victim.inventory[FOOD] -= taken
    agent.inventory[FOOD] = agent.has(FOOD) + taken

    # Committing it makes the next one easier.
    agent.restraint = max(0.0, agent.restraint - HABITUATION * 0.5)
    _wrong(victim, agent.id)

    seen = witnesses_of(world, agent, exclude=(victim.id,))
    for w in seen:
        w.grudges[agent.id] = w.grudge_against(agent.id) + GRUDGE_PER_OFFENSE * 0.4

    _remember(victim, world.tick, f"{agent.id} took food from you", 4.0, ("wronged",))
    _remember(agent, world.tick, f"you took food from {victim.id}", 2.5, ("did",))
    log.emit(world.tick, "action", agent=agent.id, verb="steal",
             betrayal=target_id in agent.bonds, target=target_id,
             taken=round(taken, 2),
             witnesses=len(seen), observed=bool(seen),
             restraint=round(agent.restraint, 3), w=witness_count, opp=opp)
    return True


def harm(world: World, agent: Agent, target_id: str, rng, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Injure another agent. Sometimes fatal."""
    victim = next((a for a in world.living_agents() if a.id == target_id), None)
    if victim is None:
        return False

    victim.shelter = max(0.0, victim.shelter - HARM_SHELTER_LOSS)
    victim.hunger += HARM_HUNGER
    agent.restraint = max(0.0, agent.restraint - HABITUATION)
    _wrong(victim, agent.id)

    seen = witnesses_of(world, agent, exclude=(victim.id,))
    for w in seen:
        w.grudges[agent.id] = w.grudge_against(agent.id) + GRUDGE_PER_OFFENSE

    _remember(victim, world.tick, f"{agent.id} attacked you", 6.0, ("wronged",))
    _remember(agent, world.tick, f"you attacked {victim.id}", 4.0, ("did",))
    for bystander in seen:
        _remember(bystander, world.tick,
                  f"you saw {agent.id} attack {victim.id}", 3.0, ("witnessed",))

    killed = rng.random() < HARM_DEATH_P
    log.emit(world.tick, "action", agent=agent.id, verb="harm",
             betrayal=target_id in agent.bonds,
             target=target_id, killed=killed,
             witnesses=len(seen), observed=bool(seen),
             restraint=round(agent.restraint, 3), w=witness_count, opp=opp)

    if killed:
        victim.alive = False
        victim.cause_of_death = "killed"
        log.emit(world.tick, "death", agent=victim.id, cause="killed",
                 age=victim.age, shelter=round(victim.shelter, 3),
                 by=agent.id, witnesses=len(seen))
    return True


def _find(world: World, agent_id: str):
    return next((a for a in world.living_agents() if a.id == agent_id), None)


def give(world: World, agent: Agent, target_id: str, resource: str, log,
         witness_count: int = 0, opp: int = 0) -> bool:
    """Hand over resources. The recipient owes a favour — grudge's mirror, and
    the thing reciprocity is built out of."""
    other = _find(world, target_id)
    if other is None or resource not in (FOOD, WOOD):
        return False
    amount = min(GIVE_AMOUNT, agent.has(resource), MAX_CARRY - other.has(resource))
    if amount <= 0:
        return False

    agent.inventory[resource] -= amount
    other.inventory[resource] = other.has(resource) + amount
    other.favors[agent.id] = other.favor_from(agent.id) + FAVOR_PER_GIFT

    _remember(other, world.tick, f"{agent.id} gave you {resource}", 3.0, ("helped",))
    log.emit(world.tick, "action", agent=agent.id, verb="give", target=target_id,
             resource=resource, amount=round(amount, 2), w=witness_count, opp=opp)
    return True


def teach(world: World, agent: Agent, target_id: str, log,
          witness_count: int = 0, opp: int = 0) -> bool:
    """Pass on a technique. The only way knowledge_breadth moves, and the only
    way anyone reaches depth 3 inside one lifetime (§7.1)."""
    other = _find(world, target_id)
    if other is None:
        return False
    options = knowledge.teachable(agent, other)
    if not options:
        return False

    technique = sorted(options)[0]
    other.techniques.add(technique)
    other.favors[agent.id] = other.favor_from(agent.id) + FAVOR_PER_GIFT * 0.6

    _remember(other, world.tick, f"{agent.id} taught you {technique}", 4.0, ("learned",))
    _remember(agent, world.tick, f"you taught {technique} to {other.id}", 2.5, ("taught",))
    log.emit(world.tick, "action", agent=agent.id, verb="teach", target=target_id,
             technique=technique, depth=knowledge.depth(technique),
             w=witness_count, opp=opp)
    return True


def form_bond(world: World, agent: Agent, target_id: str, log,
              witness_count: int = 0, opp: int = 0) -> bool:
    """Tie yourself to someone. Accepted only if they regard you well enough —
    a bond is not something one party can impose."""
    other = _find(world, target_id)
    if other is None or other.id in agent.bonds:
        return False
    if max(abs(other.x - agent.x), abs(other.y - agent.y)) > BOND_RADIUS:
        return False

    # Some positive history is required, but not much — a bond is how a tie
    # starts, not a reward for one already being strong.
    accepted = other.standing(agent.id) >= 0.25
    if accepted:
        agent.bonds.add(other.id)
        other.bonds.add(agent.id)
        _remember(agent, world.tick, f"you bonded with {other.id}", 4.0, ("bond",))
        _remember(other, world.tick, f"you bonded with {agent.id}", 4.0, ("bond",))

    log.emit(world.tick, "action", agent=agent.id, verb="form_bond",
             target=target_id, accepted=accepted, w=witness_count, opp=opp)
    return True


def speak(world: World, agent: Agent, target_id: str, log,
          witness_count: int = 0, opp: int = 0) -> bool:
    """Tell someone something. What travels is a proposition about a third
    party, which is how reputation propagates as belief — and therefore how it
    can propagate falsely (§5.6)."""
    other = _find(world, target_id)
    if other is None:
        return False

    worst = max(agent.grudges.items(), key=lambda kv: kv[1], default=None)
    if worst and worst[1] >= 1.0:
        claim, about = "wronged_me", worst[0]
    else:
        best = max(agent.favors.items(), key=lambda kv: kv[1], default=None)
        if not best or best[1] < 1.0:
            return False
        claim, about = "dealt_fairly", best[0]

    other.believe(claim, about, agent.id, world.tick)
    if claim == "wronged_me" and about != other.id:
        # Hearsay moves regard, at a discount — you did not see it yourself.
        other.grudges[about] = other.grudge_against(about) + 0.35

    log.emit(world.tick, "action", agent=agent.id, verb="speak", target=target_id,
             claim=claim, about=about, w=witness_count, opp=opp)
    return True


def leave_message(world: World, agent: Agent, log,
                  witness_count: int = 0, opp: int = 0) -> bool:
    """Leave word where you stand. Readable by whoever passes, including after
    you are dead — asynchronous and posthumous influence."""
    worst = max(agent.grudges.items(), key=lambda kv: kv[1], default=None)
    if not worst or worst[1] < 1.0:
        return False

    world.messages.append({"x": agent.x, "y": agent.y, "claim": "wronged_me",
                           "about": worst[0], "by": agent.id, "tick": world.tick})
    log.emit(world.tick, "action", agent=agent.id, verb="leave_message",
             about=worst[0], w=witness_count, opp=opp)
    return True


def coerce(world: World, agent: Agent, target_id: str, rng, log,
           witness_count: int = 0, opp: int = 0) -> bool:
    """Demand under threat. Violence without the blow — it lands or it doesn't
    depending on what the target thinks you would actually do."""
    other = _find(world, target_id)
    if other is None or other.has(FOOD) <= 0:
        return False

    # Threat is credibility, not strength: an agent with little restraint left
    # is believed. Resistance comes from the target's own nerve and from ties.
    threat = (1.0 - agent.restraint) + 0.3 * min(1.0, other.grudge_against(agent.id))
    resistance = other.restraint + (0.6 if agent.id in other.bonds else 0.0)
    yielded = threat > resistance

    if yielded:
        amount = min(COERCE_TAKE, other.has(FOOD), MAX_CARRY - agent.has(FOOD))
        other.inventory[FOOD] -= amount
        agent.inventory[FOOD] = agent.has(FOOD) + amount
    _wrong(other, agent.id)
    _remember(other, world.tick,
              f"{agent.id} threatened you" + (" and you gave in" if yielded else ""),
              5.0, ("wronged",))

    seen = witnesses_of(world, agent, exclude=(other.id,))
    for w in seen:
        w.grudges[agent.id] = w.grudge_against(agent.id) + GRUDGE_PER_OFFENSE * 0.6

    log.emit(world.tick, "action", agent=agent.id, verb="coerce", target=target_id,
             yielded=yielded, witnesses=len(seen), observed=bool(seen),
             w=witness_count, opp=opp)
    return True


def idle(world: World, agent: Agent, log, witness_count: int = 0, opp: int = 0) -> bool:
    log.emit(world.tick, "action", agent=agent.id, verb="idle", w=witness_count, opp=opp)
    return True
