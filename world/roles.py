"""Roles — the division of labour. DESIGN.md §5.7.

An archetype is who someone is; a role is what they do all day. Until now every
agent was a generalist with a lean: the six archetypes tilted utilities but
everyone still foraged, ate, repaired and bonded.

The gap surfaced when the temple failed. Relief worked — food moved out of the
store doubled — but starvation did not fall and population dropped, because
every agent occasionally abandoned foraging to carry food to a stranger. The
cost was spread across everyone. A temple is not everyone helping sometimes; it
is a few people who do nothing else, fed by the surplus of those who do.

A role does three things, and the third is the point:

  it changes the action space   — a keeper is not offered `work`
  it carries a duty             — the role's verb is weighted heavily
  it redirects sustenance       — a keeper eats from the granary, not the ground

The third creates dependency, which the world otherwise entirely lacks. A keeper
who is not fed dies, and a basin that cannot sustain its specialists loses them.
"""

FARMER = "farmer"
KEEPER = "keeper"

SPEC = {
    FARMER: {
        # Works the ground and hands the surplus over. Feeds itself, so it needs
        # no upkeep — it is what pays for everyone else.
        "duty": ("work", "contribute"),
        "blocked": ("teach", "speak", "form_bond", "leave_message"),
        "upkeep": 0.0,
        "drawn_to": ("artisan", "steward"),
        "needs": "granary",
    },
    KEEPER: {
        # Carries relief. Cannot work the ground at all, so it lives or dies by
        # what the store can pay it.
        "duty": ("withdraw", "give", "move_to"),
        "blocked": ("work",),
        "upkeep": 0.30,
        "drawn_to": ("steward", "scholar"),
        "needs": "temple",
    },
}

DUTY_WEIGHT = 0.55          # how heavily a role tilts toward its own work
KEEPER_PER_STOCK = 25.0     # granary units needed to support one keeper
MAX_FARMER_SHARE = 0.35     # a world of nothing but farmers has nobody to feed
APPOINT_EVERY = 20          # ticks between fills


def blocked(role: str) -> tuple:
    return SPEC[role]["blocked"] if role in SPEC else ()


def duty(role: str) -> tuple:
    return SPEC[role]["duty"] if role in SPEC else ()


def capacity(world, role: str) -> int:
    """How many of this role the world can currently support."""
    if role == KEEPER:
        if not world.temples or not world.granaries:
            return 0
        stock = sum(g.stock for g in world.granaries)
        return int(stock // KEEPER_PER_STOCK)
    if role == FARMER:
        if not world.granaries:
            return 0
        return int(len(world.living_agents()) * MAX_FARMER_SHARE)
    return 0


def holders(world, role: str) -> list:
    return [a for a in world.living_agents() if a.role == role]


def appoint(world, rng, log) -> None:
    """Institutions fill their vacancies.

    Offices are appointed rather than claimed: a temple takes on a keeper. An
    agent's archetype makes it a likelier choice — a steward is drawn to keeping
    — but an unlikely match is allowed, because a basin whose only survivor fit
    for the office is a zealot will have a zealot for a keeper.
    """
    for role in (FARMER, KEEPER):
        room = capacity(world, role) - len(holders(world, role))
        if room <= 0:
            continue
        spec = SPEC[role]
        free = [a for a in world.living_agents() if not a.role]
        if not free:
            continue
        # Prefer the drawn-to archetypes, then anyone.
        free.sort(key=lambda a: (a.archetype not in spec["drawn_to"], a.id))
        for agent in free[:room]:
            if agent.archetype not in spec["drawn_to"] and rng.random() > 0.25:
                continue
            agent.role = role
            log.emit(world.tick, "role", agent=agent.id, role=role,
                     archetype=agent.archetype, took=True)


def sustain(world, log) -> None:
    """Pay the offices, and vacate the ones that cannot be paid.

    This is where the dependency bites. A keeper cannot work the ground, so an
    empty store does not merely inconvenience it — the office lapses and the
    agent goes back to foraging with none of the standing or technique of one
    who never left.
    """
    for agent in list(world.living_agents()):
        if not agent.role:
            continue
        upkeep = SPEC[agent.role]["upkeep"]
        if upkeep <= 0:
            continue
        paid = 0.0
        for granary in world.granaries:
            if granary.stock <= 0:
                continue
            take = min(upkeep - paid, granary.stock)
            granary.stock -= take
            paid += take
            if paid >= upkeep:
                break
        if paid < upkeep:
            log.emit(world.tick, "role", agent=agent.id, role=agent.role,
                     took=False, reason="unpaid")
            agent.role = ""
        else:
            agent.inventory["food"] = agent.has("food") + paid


def vacate_if_unsupported(world, log) -> None:
    """An office whose institution is gone stands empty."""
    for role in (FARMER, KEEPER):
        if capacity(world, role) > 0:
            continue
        for agent in holders(world, role):
            log.emit(world.tick, "role", agent=agent.id, role=role,
                     took=False, reason="no institution")
            agent.role = ""
