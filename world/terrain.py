"""Passes 1-3 of §4.1: terrain, deep time, settlement.

Procedural and seeded — no model calls, no network. The world exists as a place
before anything happens in it, which is the point of §4.1: agents should inherit
context rather than invent it.

Deep time runs before history for a reason. Ruins are placed where people
actually could have lived, so when pass 4 writes an era that ended badly there
is already somewhere for it to have ended.
"""

WATER, MARSH, MEADOW, WOOD, STONE = "water", "marsh", "meadow", "wood", "stone"
BIOMES = (WATER, MARSH, MEADOW, WOOD, STONE)

# Which biome supports which resource, and how richly.
FOOD_BIOMES = {MARSH: 0.7, MEADOW: 1.0, WOOD: 0.5}
WOOD_BIOMES = {WOOD: 1.0, MARSH: 0.4}


def _hash(x: int, y: int, seed: int) -> float:
    h = x * 374761393 + y * 668265263 + seed * 2654435761
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 4294967296.0


def _noise(x: float, y: float, seed: int, octaves: int = 3) -> float:
    total = amplitude = 0.0
    weight, frequency = 1.0, 0.16
    for _ in range(octaves):
        xi, yi = int(x * frequency), int(y * frequency)
        fx, fy = x * frequency - xi, y * frequency - yi
        a, b = _hash(xi, yi, seed), _hash(xi + 1, yi, seed)
        c, d = _hash(xi, yi + 1, seed), _hash(xi + 1, yi + 1, seed)
        u, v = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        total += (a * (1 - u) * (1 - v) + b * u * (1 - v)
                  + c * (1 - u) * v + d * u * v) * weight
        amplitude += weight
        weight *= 0.5
        frequency *= 2.1
    return total / amplitude


def generate_terrain(width: int, height: int, seed: int) -> list:
    """Pass 1. Returns a [height][width] grid of biome names."""
    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            elevation = _noise(x, y, seed)
            # A river wandering roughly west to east, so settlement has a spine.
            river = abs(y - (height * 0.45 + _noise(x, 0, seed + 7) * height * 0.25))
            if river < 1.1 or elevation < 0.34:
                row.append(WATER)
            elif elevation < 0.42:
                row.append(MARSH)
            elif elevation < 0.60:
                row.append(MEADOW)
            elif elevation < 0.74:
                row.append(WOOD)
            else:
                row.append(STONE)
        grid.append(row)
    return grid


def settlement_score(grid: list, x: int, y: int) -> float:
    """Pass 3. Where people would historically have lived, and why.

    Fresh water within reach, workable ground underfoot, timber and stone nearby.
    Returns 0 for anywhere uninhabitable.
    """
    height, width = len(grid), len(grid[0])
    here = grid[y][x]
    if here in (WATER, STONE):
        return 0.0

    near = {}
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                near[grid[ny][nx]] = near.get(grid[ny][nx], 0) + 1

    score = 0.0
    score += 2.0 if near.get(WATER, 0) else 0.0          # you must have water
    score += 1.4 * min(1.0, near.get(MEADOW, 0) / 12.0)  # ground to work
    score += 1.0 * min(1.0, near.get(WOOD, 0) / 8.0)     # timber and fuel
    score += 0.6 * min(1.0, near.get(STONE, 0) / 6.0)    # something to build with
    score += 0.4 if here == MEADOW else 0.0
    return score


def settlement_sites(grid: list, count: int, spacing: int = 5) -> list:
    """Best habitable sites, kept apart so they read as separate places."""
    height, width = len(grid), len(grid[0])
    scored = sorted(
        ((settlement_score(grid, x, y), x, y)
         for y in range(height) for x in range(width)),
        key=lambda s: (-s[0], s[1], s[2]))

    chosen = []
    for score, x, y in scored:
        if score <= 0:
            break
        if all(max(abs(x - cx), abs(y - cy)) >= spacing for _, cx, cy in chosen):
            chosen.append((score, x, y))
        if len(chosen) == count:
            break
    return chosen


def ruins(grid: list, sites: list, rng, count: int) -> list:
    """Pass 2. Deep time: places people lived and stopped living.

    Ruins sit on sites that *would* have scored well, so the landscape carries
    evidence of a past that pass 4 can then explain.
    """
    out = []
    candidates = [s for s in settlement_sites(grid, count * 3, spacing=3)
                  if (s[1], s[2]) not in {(x, y) for _, x, y in sites}]
    for score, x, y in candidates[:count]:
        out.append({"x": x, "y": y, "kind": rng.choice(
            ["foundations", "a collapsed weir", "burial ground",
             "a walled enclosure", "kilns, long cold"]),
            "score": round(score, 2)})
    return out
