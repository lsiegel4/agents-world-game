"""The verbs of the walking skeleton.

Each action mutates state, emits exactly one event, and returns True if it did
something. The full 12-verb schema is in DESIGN.md §5.5; move / work / eat /
repair is the smallest set that produces a non-degenerate economy — two
non-fungible resources at different places, both of them needed.
"""

from .state import (
    DRIVE_INHERIT_NOISE,
    FOOD,
    HUNGER_PER_MEAL,
    MAX_CARRY,
    REPRO_CHILD_FOOD,
    REPRO_FOOD_COST,
    SHELTER_PER_WOOD,
    WOOD,
    Agent,
    World,
)


def move(world: World, agent: Agent, node_id: str, log) -> bool:
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
             target=node_id, x=agent.x, y=agent.y)
    return True


def work(world: World, agent: Agent, node_id: str, log) -> bool:
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
             node_degradation=round(node.degradation, 3))
    return True


def eat(world: World, agent: Agent, log) -> bool:
    if agent.has(FOOD) < 1.0:
        return False
    agent.inventory[FOOD] -= 1.0
    agent.hunger = max(0.0, agent.hunger - HUNGER_PER_MEAL)
    log.emit(world.tick, "action", agent=agent.id, verb="eat",
             hunger=round(agent.hunger, 2), food=round(agent.has(FOOD), 2))
    return True


def repair(world: World, agent: Agent, log) -> bool:
    """Spend one wood on shelter. Shelter decays every tick, so this is upkeep,
    not construction — it is what keeps wood and food in competition."""
    if agent.has(WOOD) < 1.0 or agent.shelter >= 1.0:
        return False
    agent.inventory[WOOD] -= 1.0
    agent.shelter = min(1.0, agent.shelter + SHELTER_PER_WOOD)
    log.emit(world.tick, "action", agent=agent.id, verb="repair",
             shelter=round(agent.shelter, 3), wood=round(agent.has(WOOD), 2))
    return True


def reproduce(world: World, agent: Agent, rng, log) -> bool:
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
        parent=agent.id,
        generation=agent.generation + 1,
        last_birth=world.tick,
    )
    world.agents.append(child)

    log.emit(world.tick, "birth", agent=child.id, parent=agent.id,
             generation=child.generation, drives=child.drives,
             parent_food=round(agent.has(FOOD), 2))
    return True


def idle(world: World, agent: Agent, log) -> bool:
    log.emit(world.tick, "action", agent=agent.id, verb="idle")
    return True
