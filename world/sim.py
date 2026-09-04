"""The tick loop.

Deterministic given (seed, config, code). One Random instance owns all
randomness; agents are always processed in list order.
"""

import random

from . import actions, deck, goals, indices, knowledge
from .memory import Memory
from .genesis import BASELINE_DRIVES, make_world
from .log import EventLog
from .state import (
    FAVOR_DECAY,
    GRUDGE_DECAY,
    MESSAGE_TTL,
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
    # Any verb named here is removed from the action space. This is the §7.3
    # ablation mechanism: run matched worlds with a verb withheld and compare.
    "disabled_verbs": (),
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
    elif verb == "give":
        actions.give(world, agent, params["target_id"],
                     params.get("resource", "food"), log, w, opp)
    elif verb == "teach":
        actions.teach(world, agent, params["target_id"], log, w, opp)
    elif verb == "form_bond":
        actions.form_bond(world, agent, params["target_id"], log, w, opp)
    elif verb == "speak":
        actions.speak(world, agent, params["target_id"], log, w, opp)
    elif verb == "leave_message":
        actions.leave_message(world, agent, log, w, opp)
    elif verb == "coerce":
        actions.coerce(world, agent, params["target_id"], rng, log, w, opp)
    else:
        actions.idle(world, agent, log, w, opp)


def tally(agent, verb: str, params: dict) -> None:
    if verb == "teach":
        agent.counters["teach"] = agent.counters.get("teach", 0) + 1
    elif verb == "give":
        agent.counters["provide"] = agent.counters.get("provide", 0) + 1
    elif verb == "reproduce":
        agent.counters["lineage"] = agent.counters.get("lineage", 0) + 1
    elif verb in ("harm", "coerce"):
        goal = agent.goal
        if goal.get("kind") == "avenge" and params.get("target_id") == goal.get("target"):
            agent.counters["avenged"] = agent.counters.get("avenged", 0) + 1


def review_goal(world: World, agent, rng, log) -> None:
    """§5.3's three levers, engine-side.

    Revision happens at thresholds — achieved, proven impossible, or a major
    life event — and the old goal is retained in history. Nothing here asks the
    agent to change its mind; the engine restates the goal and the next prompt
    is rendered from the new state.
    """
    goal = agent.goal
    if not goal:
        return

    done = goals.progress(agent, goal, agent.counters) >= 1.0
    dead_end = goals.impossible(agent, goal, world)
    if not (done or dead_end):
        return

    goal["met"] = done
    goal["ended"] = world.tick
    agent.goal_history.append(dict(goal))
    if done:
        # Reaching something you set out to do is its own reinforcement.
        agent.drives["mastery"] = min(0.99, agent.drives["mastery"] + 0.04)

    agent.goal = goals.generate(agent, rng, world)
    log.emit(world.tick, "goal", agent=agent.id, previous=goal["kind"],
             outcome="met" if done else "abandoned",
             new=agent.goal["kind"], held_for=world.tick - goal.get("since", 0))


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


def step(world: World, rng, log, deck_rng=None, cfg=None, mind=None,
         goal_rng=None) -> None:
    from . import brain
    world.tick += 1

    violence = bool(cfg.get("violence", True)) if cfg else True
    disabled = frozenset(cfg.get("disabled_verbs", ())) if cfg else frozenset()

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
        if agent.memory is None:
            agent.memory = Memory()
        if mind is not None:
            verb, params = mind.choose(world, agent, rng, w, violence, log)
        else:
            verb, params = brain.choose(world, agent, rng, w, violence, disabled)
        if verb in disabled:
            verb, params = "idle", {}
        apply(world, agent, verb, params, rng, log, w, opp)
        tally(agent, verb, params)
        review_goal(world, agent, goal_rng or rng, log)
        update_drives(agent, verb)
        update_restraint(agent)
        agent.memory.decay(world.tick)

        # Working something out alone is rare by design, so a world that reaches
        # depth 3 got there by teaching rather than by parallel discovery.
        if verb == "work":
            found = knowledge.try_discover(agent, rng)
            if found:
                agent.techniques.add(found)
                log.emit(world.tick, "discovery", agent=agent.id, technique=found,
                         depth=knowledge.depth(found))

        # Reading what someone left behind, including the dead.
        for msg in world.messages:
            if msg["x"] == agent.x and msg["y"] == agent.y and msg["by"] != agent.id:
                agent.believe(msg["claim"], msg["about"], msg["by"], world.tick)
                if msg["about"] != agent.id:
                    agent.grudges[msg["about"]] = (
                        agent.grudge_against(msg["about"]) + 0.25)

        if agent.hunger >= STARVATION_THRESHOLD:
            agent.alive = False
            agent.cause_of_death = "starvation"
            log.emit(world.tick, "death", agent=agent.id, cause="starvation",
                     age=agent.age, shelter=round(agent.shelter, 3))

    for node in world.nodes:
        node.regenerate()

    world.messages = [m for m in world.messages
                      if world.tick - m["tick"] <= MESSAGE_TTL]

    for agent in world.living_agents():
        for other_id in list(agent.favors):
            agent.favors[other_id] -= FAVOR_DECAY
            if agent.favors[other_id] <= 0:
                del agent.favors[other_id]

    if deck_rng is not None and cfg and cfg.get("deck", True):
        deck.draw(world, deck_rng, log, cfg.get("deck_scale", 1.0))

    if world.tick % DEFAULT_CONFIG["snapshot_every"] == 0:
        log.emit(world.tick, "indices", **indices.snapshot(world))


def run(seed: int, ticks: int, config: dict = None, mind=None):
    """Run one world to completion. Returns (world, log).

    `mind` is an optional world.cognition.Cognition. With none, every agent runs
    on the Tier 0 utility AI — the permanent control arm (§7.5).
    """
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
                 goal=agent.goal.get("kind", ""),
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
    goal_rng = random.Random(seed ^ 0x6041)

    for agent in world.agents:
        agent.goal = goals.generate(agent, goal_rng, world)

    for _ in range(ticks):
        step(world, rng, log, deck_rng, cfg, mind, goal_rng)
        if not world.living_agents():
            log.emit(world.tick, "extinction")
            break

    log.emit(world.tick, "indices", **indices.snapshot(world))
    return world, log
