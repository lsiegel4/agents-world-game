"""The verbs of the walking skeleton.

Each action mutates state, emits exactly one event, and returns True if it did
something. The full 12-verb schema is in DESIGN.md §5.5; move / work / eat /
repair is the smallest set that produces a non-degenerate economy — two
non-fungible resources at different places, both of them needed.
"""

from .state import (
    DRIVE_INHERIT_NOISE,
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
    taken = min(node.harvest(), room)
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
    agent.hunger = max(0.0, agent.hunger - HUNGER_PER_MEAL)
    log.emit(world.tick, "action", agent=agent.id, verb="eat",
             hunger=round(agent.hunger, 2), food=round(agent.has(FOOD), 2), w=witness_count, opp=opp)
    return True


def repair(world: World, agent: Agent, log, witness_count: int = 0, opp: int = 0) -> bool:
    """Spend one wood on shelter. Shelter decays every tick, so this is upkeep,
    not construction — it is what keeps wood and food in competition."""
    if agent.has(WOOD) < 1.0 or agent.shelter >= 1.0:
        return False
    agent.inventory[WOOD] -= 1.0
    agent.shelter = min(1.0, agent.shelter + SHELTER_PER_WOOD)
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
        id=f"c{world.tick:05d}-{agent.id}",
        name=f"{agent.name}sson",
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
        parent=agent.id,
        generation=agent.generation + 1,
        last_birth=world.tick,
    )
    world.agents.append(child)

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

    log.emit(world.tick, "action", agent=agent.id, verb="steal",
             target=target_id, taken=round(taken, 2),
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

    killed = rng.random() < HARM_DEATH_P
    log.emit(world.tick, "action", agent=agent.id, verb="harm",
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


def idle(world: World, agent: Agent, log, witness_count: int = 0, opp: int = 0) -> bool:
    log.emit(world.tick, "action", agent=agent.id, verb="idle", w=witness_count, opp=opp)
    return True
