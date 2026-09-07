"""Institutions that do something — DESIGN.md §5.6, §7.1.

Until now "institution" meant two unrelated things: a `guild at High Wells` in
the generated history, which nothing read, and a connected component of the bond
graph, which `institution_density` measured. Neither could hold anything or
decide anything.

The granary is the first with a function, and it exists because the world was
measured: starvation is 42% of all deaths, and **75% of the starving die with
2.24 neighbours carrying food within three tiles** while 1,600 units sit in the
basin. That is not scarcity, it is distribution. Nobody could hold a surplus for
anyone else — `MAX_CARRY` is 12 — and giving followed *standing*, so food moved
along friendship rather than along hunger and a starving stranger was invisible.

A granary is a place that holds food nobody is carrying, and a rule about who
may take it. The rule is the interesting part: it is where politics lives, and
it is a variable rather than a constant.
"""

GRANARY_CAPACITY = 240.0
CONTRIBUTE_AMOUNT = 3.0
WITHDRAW_AMOUNT = 3.0
GRANARY_RADIUS = 2           # you must be at it to use it
SPOILAGE = 0.0006            # per tick; a store is not free to keep

# Who may draw, and on what terms. The charter is the politics.
OPEN = "open"                # anyone hungry may take
MEMBERS = "members"          # only those who have contributed
KINDRED = "kindred"          # contributors, and not the basin's suspect kind
CHARTERS = (OPEN, MEMBERS, KINDRED)


class Granary:
    def __init__(self, x: int, y: int, charter: str = OPEN, seat: str = ""):
        self.x = x
        self.y = y
        self.charter = charter
        self.seat = seat
        self.stock = 0.0
        self.contributors = {}      # agent_id -> total contributed
        self.given = 0.0
        self.taken = 0.0
        self.refused = 0

    def within(self, agent) -> bool:
        return max(abs(agent.x - self.x), abs(agent.y - self.y)) <= GRANARY_RADIUS

    def may_draw(self, agent, distrusted=()) -> bool:
        """The charter, applied. This is the mechanism politics acts through:
        the same store feeds a whole basin or only its members, and a basin that
        suspects a kind can write that suspicion into who eats."""
        if self.charter == OPEN:
            return True
        if self.charter == MEMBERS:
            return agent.id in self.contributors
        if self.charter == KINDRED:
            return (agent.id in self.contributors
                    and agent.archetype not in distrusted)
        return True

    def contribute(self, agent, amount: float) -> float:
        room = GRANARY_CAPACITY - self.stock
        given = min(amount, agent.has("food"), room)
        if given <= 0:
            return 0.0
        agent.inventory["food"] = agent.has("food") - given
        self.stock += given
        self.contributors[agent.id] = self.contributors.get(agent.id, 0.0) + given
        self.given += given
        return given

    def withdraw(self, agent, amount: float, distrusted=()) -> float:
        if not self.may_draw(agent, distrusted):
            self.refused += 1
            return 0.0
        taken = min(amount, self.stock)
        if taken <= 0:
            return 0.0
        self.stock -= taken
        agent.inventory["food"] = agent.has("food") + taken
        self.taken += taken
        return taken

    def spoil(self) -> None:
        self.stock = max(0.0, self.stock - self.stock * SPOILAGE)


PARISH_RADIUS = 14           # how far a temple hears
PLEA_TTL = 60                # ticks a plea stays live
KEEPER_DRAW = 4.0            # food a keeper takes to carry to others


class Temple:
    """An institution that acts on someone else's behalf.

    The granary alone made worlds worse: food went in and did not come out,
    because withdrawing required a starving agent to be standing at the store
    and the people who die are exactly those far from it. Twelve granaries were
    no better than four — 580 units accumulated while 55% of deaths were
    starvation. The missing piece was never storage. It was that nobody carried
    anything to anyone.

    A temple hears need across a parish rather than within arm's reach, and
    sends someone with the food. It is the first thing in the world that acts
    for a person other than the actor.
    """

    def __init__(self, x: int, y: int, seat: str = ""):
        self.x = x
        self.y = y
        self.seat = seat
        self.relieved = 0
        self.carried = 0.0

    def hears(self, x: int, y: int) -> bool:
        return max(abs(x - self.x), abs(y - self.y)) <= PARISH_RADIUS

    def covers(self, agent) -> bool:
        return self.hears(agent.x, agent.y)


def live_pleas(world, tick: int) -> list:
    """Open pleas a temple can hear: (agent, distance-irrelevant) pairs."""
    out = []
    for temple in world.temples:
        for agent in world.living_agents():
            if tick - agent.asked_at > PLEA_TTL:
                continue
            if temple.hears(agent.x, agent.y):
                out.append(agent)
    return out


def nearest_temple(world, agent):
    best, best_d = None, None
    for temple in world.temples:
        d = max(abs(temple.x - agent.x), abs(temple.y - agent.y))
        if best_d is None or d < best_d:
            best, best_d = temple, d
    return best, best_d


def nearest(world, agent):
    best, best_d = None, None
    for granary in world.granaries:
        d = max(abs(granary.x - agent.x), abs(granary.y - agent.y))
        if best_d is None or d < best_d:
            best, best_d = granary, d
    return best, best_d
