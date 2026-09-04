"""World generation — M0 stub.

DESIGN.md §4.1 specifies a nine-pass generator ending in history and myth. That
arrives in M3. This places terrain-free nodes and agents on a grid, seeded, so
the tick loop has something to chew on.
"""

import random

from .state import FOOD, WOOD, Agent, ResourceNode, World

BASELINE_DRIVES = {"survival": 0.45, "mastery": 0.35, "curiosity": 0.35}

NAMES = ["Maren", "Rhoswen", "Doran", "Ilka", "Bastian", "Sela", "Cael", "Wick"]


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

    for i in range(config["agents"]):
        # Uneven endowment from the first tick — DESIGN.md §2.2. Nothing here
        # tries to make the starts fair.
        w.agents.append(Agent(
            id=f"a{i:02d}",
            name=NAMES[i % len(NAMES)],
            x=rng.randrange(w.width),
            y=rng.randrange(w.height),
            drives={k: round(v + rng.uniform(-0.08, 0.08), 4)
                    for k, v in BASELINE_DRIVES.items()},
            inventory={FOOD: float(rng.randrange(0, config["start_food"] + 1)),
                       WOOD: 0.0},
            hunger=float(rng.randrange(0, 8)),
            # Founders are not all newborns. Uniform starting age synchronizes
            # every cohort onto the same breeding tick and drives a boom-bust
            # that has nothing to do with the economy being studied.
            age=rng.randrange(0, config["founder_max_age"]),
        ))
    return w
