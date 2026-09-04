"""World indices.

M0 computes population only. DESIGN.md §7.1 defines the full vector — knowledge
depth and breadth, institution density, norm compliance, trust network, material
output, Gini, goal attainment, drive entropy — which arrives in M2 alongside the
behavioral profiles. Resisting the urge to add them early keeps M0's gate honest.
"""

from .state import World


def population(world: World) -> int:
    return len(world.living_agents())


def snapshot(world: World) -> dict:
    return {"population": population(world)}
