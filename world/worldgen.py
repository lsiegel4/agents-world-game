"""Passes 7-9 of §4.1 and the assembly of all nine.

Institutions are derived from what happened, material state from who was left
standing, and placement from material state. The chain matters: an agent's
starting endowment should be a consequence of the world's history rather than a
number drawn beside it.

This sits behind `worldgen: "generated"` in the config. `genesis.py` remains the
default so every result recorded before M3 stays reproducible — the same
discipline that separate PRNG streams enforce elsewhere.
"""

import random

from . import history as history_pass
from . import terrain as terrain_pass
from .state import FOOD, WOOD, Agent, ResourceNode, World

# Which institution an era leaves behind, and the rule it persists.
INSTITUTION_FROM_ERA = {
    "conflict": ("council", "disputes over water are heard before they are fought"),
    "plague":   ("temple", "the sick are kept apart and fed by others"),
    "growth":   ("guild", "a craft is taught only to those who stay"),
    "collapse": ("watch", "the weirs are walked before every winter"),
    "migration": ("market", "a stranger may trade before they may settle"),
    "recovery": ("school", "what was worked out once is written down"),
    "founding": ("moot", "the boundary stones are walked each year"),
}


def generate_institutions(hist: dict, rng) -> list:
    """Pass 7. One institution per era that produced one, with its charter."""
    out, seen = [], set()
    for era in hist["eras"]:
        entry = INSTITUTION_FROM_ERA.get(era["kind"])
        if not entry or entry[0] in seen:
            continue
        kind, charter = entry
        seen.add(kind)
        out.append({"kind": kind, "charter": charter, "founded_in": era["name"],
                    "seat": rng.choice(hist["places"]),
                    "active": rng.random() > 0.25})
    return out


def generate_material_state(hist: dict, sites: list, rng, inequality: float) -> dict:
    """Pass 8. Who holds what now, and what is scarce, given what happened.

    `inequality` is the tunable from §4.4 and §2.2. At 0 everyone starts level;
    at 1 the distribution is steep. The world is not fair by default.
    """
    shares = []
    for index, _ in enumerate(sites):
        # A geometric-ish split: steepness set by the inequality parameter.
        shares.append((1.0 - inequality) + inequality * (0.85 ** index) * len(sites) * 0.5)
    total = sum(shares) or 1.0
    shares = [s / total for s in shares]

    scarce = FOOD if any(e["kind"] in ("plague", "collapse") for e in hist["eras"]) else WOOD
    debts = []
    for index in range(len(sites)):
        if rng.random() < inequality:
            creditor = rng.randrange(len(sites))
            if creditor != index:
                debts.append({"debtor_site": index, "creditor_site": creditor,
                              "amount": round(2.0 + rng.random() * 6.0, 1)})
    return {"site_shares": shares, "scarce": scarce, "debts": debts}


def place_nodes(grid: list, rng, food_nodes: int, wood_nodes: int,
                capacity: float, regen: float) -> list:
    """Resource nodes sit where the terrain supports them, not at random."""
    height, width = len(grid), len(grid[0])
    nodes = []

    for kind, count, table in ((FOOD, food_nodes, terrain_pass.FOOD_BIOMES),
                              (WOOD, wood_nodes, terrain_pass.WOOD_BIOMES)):
        candidates = [(x, y, table[grid[y][x]])
                      for y in range(height) for x in range(width)
                      if grid[y][x] in table]
        candidates.sort(key=lambda c: (-c[2], c[0], c[1]))
        # Take a spread from the suitable ground rather than the best cluster.
        step = max(1, len(candidates) // max(1, count))
        picked = [candidates[min(i * step, len(candidates) - 1)]
                  for i in range(count)] if candidates else []

        # Biome quality decides WHERE resources sit and how they differ from one
        # another — not how much exists in total. Left unnormalised it silently
        # shrinks the whole economy (marsh food is 0.7, wood-biome food 0.5), and
        # a generated world starves where a flat one survives. Normalising keeps
        # total capacity comparable so the two generators can be compared at all.
        mean_quality = (sum(q for _, _, q in picked) / len(picked)) if picked else 1.0
        for index, (x, y, quality) in enumerate(picked):
            scaled = capacity * (quality / mean_quality)
            prefix = "n" if kind == FOOD else "w"
            nodes.append(ResourceNode(
                id=f"{prefix}{index:02d}", kind=kind, x=x, y=y,
                amount=scaled, capacity=scaled, regen_rate=regen))
    return nodes


def make_world(seed: int, config: dict) -> World:
    """All nine passes, in order. Deterministic given the seed."""
    rng = random.Random(seed ^ 0x9E3D)

    grid = terrain_pass.generate_terrain(config["width"], config["height"], seed)
    sites = terrain_pass.settlement_sites(grid, config.get("sites", 4))
    ruin_list = terrain_pass.ruins(grid, sites, rng, config.get("ruins", 3))
    hist = history_pass.generate_history(sites, rng, config.get("history_years", 300))
    culture = history_pass.generate_culture(hist, rng)
    myths = history_pass.generate_myth(hist, rng)
    institutions = generate_institutions(hist, rng)
    material = generate_material_state(hist, sites, rng,
                                       config.get("inequality", 0.5))

    world = World(width=config["width"], height=config["height"])
    world.nodes = place_nodes(grid, rng, config["food_nodes"], config["wood_nodes"],
                              config["node_capacity"], config["regen_rate"])
    world.terrain = grid
    world.lore = {"sites": sites, "ruins": ruin_list, "history": hist,
                  "culture": culture, "myths": myths,
                  "institutions": institutions, "material": material,
                  "myth_divergence": history_pass.myth_divergence(hist, myths)}

    # Pass 9: placement. Endowment follows the site an agent is born into, so
    # inequality is inherited from the world's state rather than sprinkled on.
    from .genesis import BASELINE_DRIVES, NAMES
    from .state import RESTRAINT_BASE, RESTRAINT_NOISE

    for index in range(config["agents"]):
        site_index = index % max(1, len(sites))
        _, sx, sy = sites[site_index] if sites else (0, world.width // 2, world.height // 2)
        share = material["site_shares"][site_index] if material["site_shares"] else 0.25
        restraint = max(0.0, min(1.0, RESTRAINT_BASE
                                 + rng.uniform(-RESTRAINT_NOISE, RESTRAINT_NOISE)))
        world.agents.append(Agent(
            id=f"a{index:02d}",
            name=NAMES[index % len(NAMES)],
            x=max(0, min(world.width - 1, sx + rng.randrange(-2, 3))),
            y=max(0, min(world.height - 1, sy + rng.randrange(-2, 3))),
            drives={k: round(v + rng.uniform(-0.08, 0.08), 4)
                    for k, v in BASELINE_DRIVES.items()},
            inventory={FOOD: round(config["start_food"] * share * len(sites), 1),
                       WOOD: 0.0},
            hunger=float(rng.randrange(0, 8)),
            age=rng.randrange(0, config["founder_max_age"]),
            restraint=restraint,
            restraint_base=restraint,
        ))
    return world
