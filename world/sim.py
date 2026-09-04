"""The tick loop.

Deterministic given (seed, config, code). One Random instance owns all
randomness; agents are always processed in list order.
"""

import random

from . import actions, deck, indices
from .genesis import BASELINE_DRIVES, make_world
from .log import EventLog
from .state import (
    GRUDGE_DECAY,
    HUNGER_PER_TICK,
    INTERACT_RADIUS,
    RESTRAINT_HUNGER_EROSION,
    RESTRAINT_RECOVERY,
    SHELTER_DECAY,
    STARVATION_THRESHOLD,
    WITNESS_RADIUS,
    World,
)

DEFAULT_CONFIG = {
    "width": 24,
    "height": 16,
    "agents": 5,
    "food_nodes": 6,
    "wood_nodes": 3,
    "node_capacity": 40.0,
    "regen_rate": 0.025,
    "start_food": 6,
    "founder_max_age": 140,
    "deck": True,          # set False for the §7.3 no-deck ablation arm
    "violence": True,      # set False for the no-defection ablation arm
    "deck_scale": 1.0,
    "snapshot_every": 25,
}

# Drive dynamics. Sustained hunger pulls survival up; everything relaxes back
# toward the archetype baseline when the pressure is off (DESIGN.md §5.1).
DRIVE_GAIN = 0.05
MASTERY_PER_WORK = 0.010
CURIOSITY_PER_MOVE = 0.004
RELAX = 0.006
DRIVE_MIN, DRIVE_MAX = 0.05, 0.99


def _clamp(v: float) -> float:
    return max(DRIVE_MIN, min(DRIVE_MAX, v))


def update_drives(agent, verb: str) -> None:
    hunger_norm = min(1.0, agent.hunger / STARVATION_THRESHOLD)
    target = BASELINE_DRIVES["survival"] + 0.60 * hunger_norm
    d = agent.drives
    d["survival"] = _clamp(d["survival"] + DRIVE_GAIN * (target - d["survival"]))

    if verb == "work":
        d["mastery"] = _clamp(d["mastery"] + MASTERY_PER_WORK)
    else:
        d["mastery"] = _clamp(d["mastery"] + RELAX * (BASELINE_DRIVES["mastery"] - d["mastery"]))

    if verb == "move":
        d["curiosity"] = _clamp(d["curiosity"] + CURIOSITY_PER_MOVE)
    else:
        d["curiosity"] = _clamp(d["curiosity"] + RELAX * (BASELINE_DRIVES["curiosity"] - d["curiosity"]))

    for k in d:
        d[k] = round(d[k], 6)


def apply(world: World, agent, verb: str, params: dict, rng, log, w: int = 0, opp: int = 0) -> None:
    if verb == "move":
        actions.move(world, agent, params["node_id"], log, w, opp)
    elif verb == "work":
        actions.work(world, agent, params["node_id"], log, w, opp)
    elif verb == "eat":
        actions.eat(world, agent, log, w, opp)
    elif verb == "repair":
        actions.repair(world, agent, log, w, opp)
    elif verb == "reproduce":
        actions.reproduce(world, agent, rng, log, w, opp)
    elif verb == "steal":
        actions.steal(world, agent, params["target_id"], log, w, opp)
    elif verb == "harm":
        actions.harm(world, agent, params["target_id"], rng, log, w, opp)
    else:
        actions.idle(world, agent, log, w, opp)


def surroundings(world: World, agent) -> tuple:
    """(witnesses within sight, agents within reach) for this agent, right now."""
    w = opp = 0
    for other in world.living_agents():
        if other is agent:
            continue
        d = max(abs(other.x - agent.x), abs(other.y - agent.y))
        if d <= WITNESS_RADIUS:
            w += 1
        if d <= INTERACT_RADIUS:
            opp += 1
    return w, opp


def update_restraint(agent) -> None:
    """Environment half of §5.6. Sustained hunger pulls the target down; the
    value relaxes back toward it, so an agent who comes through a hard season
    recovers rather than staying permanently disinhibited."""
    hunger_norm = min(1.0, agent.hunger / STARVATION_THRESHOLD)
    target = agent.restraint_base - RESTRAINT_HUNGER_EROSION * hunger_norm
    agent.restraint = max(0.0, min(1.0,
        agent.restraint + RESTRAINT_RECOVERY * (target - agent.restraint)))
    for other_id in list(agent.grudges):
        agent.grudges[other_id] -= GRUDGE_DECAY
        if agent.grudges[other_id] <= 0:
            del agent.grudges[other_id]


def step(world: World, rng, log, deck_rng=None, cfg=None) -> None:
    from . import brain
    world.tick += 1

    violence = bool(cfg.get("violence", True)) if cfg else True

    for agent in world.living_agents():
        agent.age += 1
        agent.shelter = max(0.0, agent.shelter - SHELTER_DECAY)
        # An unsheltered agent burns through food faster. This is what keeps the
        # wood economy and the food economy in genuine competition.
        agent.hunger += HUNGER_PER_TICK * agent.exposure()
        # Both counts are taken live, immediately before this agent acts, not
        # from a tick-start snapshot: agents move within a tick, so a snapshot
        # denominator and a decision-time numerator measure different worlds and
        # the norm-compliance ratio is computed over mismatched arms.
        w, opp = surroundings(world, agent)
        verb, params = brain.choose(world, agent, rng, w, violence)
        apply(world, agent, verb, params, rng, log, w, opp)
        update_drives(agent, verb)
        update_restraint(agent)

        if agent.hunger >= STARVATION_THRESHOLD:
            agent.alive = False
            agent.cause_of_death = "starvation"
            log.emit(world.tick, "death", agent=agent.id, cause="starvation",
                     age=agent.age, shelter=round(agent.shelter, 3))

    for node in world.nodes:
        node.regenerate()

    if deck_rng is not None and cfg and cfg.get("deck", True):
        deck.draw(world, deck_rng, log, cfg.get("deck_scale", 1.0))

    if world.tick % DEFAULT_CONFIG["snapshot_every"] == 0:
        log.emit(world.tick, "indices", **indices.snapshot(world))


def run(seed: int, ticks: int, config: dict = None):
    """Run one world to completion. Returns (world, log)."""
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)

    log = EventLog()
    log.header(seed, cfg)
    log.records[0]["deck"] = [
        {"event": name, "base_p": base} for name, base, _, _ in deck.DECK
    ]
    world = make_world(seed, cfg)
    for agent in world.agents:
        log.emit(0, "spawn", agent=agent.id, generation=0, restraint=agent.restraint,
                 x=agent.x, y=agent.y, age=agent.age,
                 food=agent.has("food"), drives=dict(agent.drives),
                 # Distance to the nearest node of each kind is the spatial half
                 # of endowment, and M0 showed it dominates survival.
                 d_food=min((max(abs(n.x - agent.x), abs(n.y - agent.y))
                             for n in world.nodes if n.kind == "food"), default=-1),
                 d_wood=min((max(abs(n.x - agent.x), abs(n.y - agent.y))
                             for n in world.nodes if n.kind == "wood"), default=-1))
    # Separate streams: worldgen, agent cognition, and the deck each draw from
    # their own PRNG, so changing deck parameters does not reshuffle the jitter
    # in every agent's decision and vice versa. Ablations stay comparable.
    rng = random.Random(seed ^ 0x5EED)
    deck_rng = random.Random(seed ^ 0xDECC)

    for _ in range(ticks):
        step(world, rng, log, deck_rng, cfg)
        if not world.living_agents():
            log.emit(world.tick, "extinction")
            break

    log.emit(world.tick, "indices", **indices.snapshot(world))
    return world, log
