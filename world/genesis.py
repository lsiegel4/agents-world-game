"""World generation — M0 stub.

DESIGN.md §4.1 specifies a nine-pass generator ending in history and myth. That
arrives in M3. This places terrain-free nodes and agents on a grid, seeded, so
the tick loop has something to chew on.
"""

import random

from . import archetypes, institutions
from .state import (
    FOOD,
    RESTRAINT_BASE,
    RESTRAINT_NOISE,
    WOOD,
    Agent,
    ResourceNode,
    World,
)

BASELINE_DRIVES = {"survival": 0.45, "mastery": 0.35, "curiosity": 0.35}

# A child took the parent's name plus "sson" every generation, so within a few
# hundred ticks every living agent was called "Ilkasson" and a chronicle read as
# one person doing everything. Children now take a given name of their own.
NAMES = ["Maren", "Rhoswen", "Doran", "Ilka", "Bastian", "Sela", "Cael", "Wick",
         "Alder", "Bryn", "Corvin", "Dela", "Enna", "Fenn", "Gethin", "Hesper",
         "Idris", "Juna", "Kestrel", "Lorne", "Mabon", "Nesta", "Orin", "Pell",
         "Quillon", "Rowan", "Saskia", "Torin", "Ulla", "Veryan", "Wren", "Ysolde"]


def make_world(seed: int, config: dict) -> World:
    rng = random.Random(seed)
    w = World(width=config["width"], height=config["height"])

    for i in range(config["food_nodes"]):
        w.nodes.append(ResourceNode(
            id=f"n{i:02d}",
            kind=FOOD,
            x=rng.randrange(w.width),
            y=rng.randrange(w.height),
            amount=config["node_capacity"],
            capacity=config["node_capacity"],
            regen_rate=config["regen_rate"],
        ))
    for i in range(config["wood_nodes"]):
        w.nodes.append(ResourceNode(
            id=f"w{i:02d}",
            kind=WOOD,
            x=rng.randrange(w.width),
            y=rng.randrange(w.height),
            amount=config["node_capacity"],
            capacity=config["node_capacity"],
            regen_rate=config["regen_rate"],
        ))

    # Two worlds in three suspect some kind; the rest are the control. Which
    # kind is a fact about the basin, not about the archetype.
    if rng.random() < config.get("distrust_chance", 0.66):
        w.distrusted = (archetypes.NAMES[rng.randrange(len(archetypes.NAMES))],)

    # Flat worlds have no history to inherit from, so a store appears only if
    # one is explicitly asked for.
    requested = config.get("granaries")
    if requested:
        charter = config.get("charter") or institutions.OPEN
        for g in range(requested):
            w.granaries.append(institutions.Granary(
                x=(g + 1) * w.width // (config.get("granaries", 1) + 1),
                y=w.height // 2, charter=charter))

    for i in range(config["agents"]):
        kind = archetypes.assign(i)
        # Uneven endowment from the first tick — DESIGN.md §2.2. Nothing here
        # tries to make the starts fair.
        w.agents.append(Agent(
            id=f"a{i:02d}",
            name=NAMES[i % len(NAMES)],
            x=rng.randrange(w.width),
            y=rng.randrange(w.height),
            archetype=kind,
            drives=archetypes.drives_for(kind, rng),
            inventory={FOOD: round(rng.randrange(0, config["start_food"] + 1)
                                   * archetypes.spec(kind)["endowment"], 1),
                       WOOD: 0.0},
            hunger=float(rng.randrange(0, 8)),
            # Founders are not all newborns. Uniform starting age synchronizes
            # every cohort onto the same breeding tick and drives a boom-bust
            # that has nothing to do with the economy being studied.
            age=rng.randrange(0, config["founder_max_age"]),
            # Nature (§5.6): founders differ in restraint from the first tick.
            restraint=(r := archetypes.restraint_for(kind, rng)),
            restraint_base=r,
        ))
    return w
