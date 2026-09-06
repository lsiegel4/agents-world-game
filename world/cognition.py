"""Tier routing and model-driven action selection — DESIGN.md §5.7.

Most ticks are not model calls. Tier 0 is the utility AI in brain.py and handles
routine life; escalation is triggered by a novelty/stakes score, not by a tick
counter. Every routing decision is logged, because the router's own behaviour is
a research artifact and because results have to be checkable for sensitivity to
which tier ran (§7.5).

The model chooses among exactly the verbs the engine exposes. It cannot invent
an action, and an action it picks that turns out to be impossible simply fails
in the engine — authority is the tool schema's, not the text's (§2.5).
"""

from . import brain, prompt
from .state import FOOD, MAX_CARRY, STARVATION_THRESHOLD

TIER1_MODEL = "claude-haiku-4-5"    # §5.7 cheap tier
TIER2_MODEL = "claude-opus-5"       # §5.7 frontier tier
ESCALATE_T1 = 0.35
ESCALATE_T2 = 0.80
MAX_TOKENS = 512


def stakes(world, agent, nearby_agents) -> float:
    """How much this tick matters. Bounded 0-1.

    Routine foraging scores low and stays on Tier 0. Hunger, a failing shelter,
    another person within reach, an unsettled grudge, or the chance to have a
    child all raise it — these are the moments where a policy and a person come
    apart.
    """
    hunger = min(1.0, agent.hunger / STARVATION_THRESHOLD)
    score = 0.0

    # Pressure only counts once it is real. A mildly hungry agent with a worn
    # roof is having an ordinary day, and the utility AI handles ordinary days.
    score += 0.55 * max(0.0, hunger - 0.45) / 0.55
    score += 0.25 * max(0.0, 0.45 - agent.shelter) / 0.45

    # Proximity on its own is not a decision — agents cluster at nodes all the
    # time. It matters when something is actually at stake: an unsettled grudge,
    # or a hungry agent standing next to someone carrying food.
    if nearby_agents:
        if any(agent.grudge_against(o.id) >= 1.0 for o in nearby_agents):
            score += 0.45
        if hunger > 0.5 and any(o.has(FOOD) > 0 for o in nearby_agents):
            score += 0.35

    if agent.can_reproduce(world.tick):
        score += 0.40
    return min(1.0, score)


def route(score: float) -> int:
    if score >= ESCALATE_T2:
        return 2
    if score >= ESCALATE_T1:
        return 1
    return 0


def _parse(response: dict):
    """Pull the chosen verb out of a response. Returns (verb, params) or None."""
    for block in response.get("content", []):
        if block.get("type") == "tool_use":
            return block["name"], dict(block.get("input") or {})
    return None


def cast(world, per_archetype: int = 1) -> set:
    """Pick a cast spread across archetypes.

    Choosing the most prominent agents instead would pick almost entirely
    scholars — they are 55-62% of survivors in every condition measured — and a
    cast drawn from one kind shows one kind of life.
    """
    chosen, seen = set(), {}
    for agent in world.living_agents():
        held = seen.get(agent.archetype, 0)
        if held < per_archetype:
            seen[agent.archetype] = held + 1
            chosen.add(agent.id)
    return chosen


def _visible(world, agent, radius: int = 12):
    nodes = []
    for node in world.nodes:
        d = max(abs(node.x - agent.x), abs(node.y - agent.y))
        if d <= radius:
            nodes.append((node, d))
    nodes.sort(key=lambda nd: nd[1])
    return nodes[:6]


class Cognition:
    """Chooses actions, escalating from the utility AI to a model as stakes rise."""

    def __init__(self, client=None, allow_violence: bool = True,
                 on_cache_miss: str = "error", tier2: bool = False,
                 principals=None):
        self.client = client
        # A cast, not a population. `principals` is a set of agent ids allowed to
        # escalate; everyone else stays on the utility AI however high the stakes
        # get. Cost then scales with cast size rather than world size, which is
        # the difference between ~$20 and ~$340 a month at 200 agents — and it is
        # dramaturgically right, since every story has a foreground and a crowd.
        # None means everyone may escalate. An int means "this many per
        # archetype, chosen once the world exists" — the world is built inside
        # run(), so a cast cannot be named before the call.
        self.cast_per_archetype = principals if isinstance(principals, int) else None
        self.principals = (set(principals)
                           if principals is not None and not isinstance(principals, int)
                           else None)
        self.on_cache_miss = on_cache_miss
        self.tier2 = tier2
        self.allow_violence = allow_violence
        self.tier_counts = {0: 0, 1: 0, 2: 0}
        # Attempts are counted before the call. A fallback still escalated — it
        # still rendered a prompt and still would have cost money on a live run —
        # so counting it as a Tier 0 decision hides the number that drives the
        # bill (§10).
        self.attempts = {1: 0, 2: 0}
        self.fallbacks = 0
        self.invalid = 0

    def _maintain_cast(self, world, log) -> None:
        """Pick the cast, and refill it as members die.

        Lifespan is ~400 ticks, so a cast chosen at t=0 is dead well before a
        run ends. A story follows whoever is alive; without refilling, the
        experiment would silently become an all-Tier-0 run partway through and
        the cost would quietly stop being spent.
        """
        if self.cast_per_archetype is None:
            return
        living = {a.id for a in world.living_agents()}
        if self.principals is None:
            self.principals = cast(world, self.cast_per_archetype)
            log.emit(world.tick, "cast", members=sorted(self.principals))
            return

        surviving = self.principals & living
        if len(surviving) == len(self.principals):
            return

        held = {}
        by_id = {a.id: a for a in world.living_agents()}
        for agent_id in surviving:
            kind = by_id[agent_id].archetype
            held[kind] = held.get(kind, 0) + 1
        replacements = set()
        for other in world.living_agents():
            if other.id in surviving:
                continue
            kind = other.archetype
            if held.get(kind, 0) < self.cast_per_archetype:
                held[kind] = held.get(kind, 0) + 1
                replacements.add(other.id)
        if replacements:
            log.emit(world.tick, "cast", promoted=sorted(replacements),
                     lost=sorted(self.principals - living))
        self.principals = surviving | replacements

    def choose(self, world, agent, rng, witness_count, violence, log, brief=""):
        self._maintain_cast(world, log)
        nearby = brain.reachable(world, agent)
        score = stakes(world, agent, nearby)
        tier = route(score)
        if tier == 2 and not self.tier2:
            tier = 1
        if self.client is None:
            tier = 0
        if self.principals is not None and agent.id not in self.principals:
            tier = 0

        if tier == 0:
            self.tier_counts[0] += 1
            return brain.choose(world, agent, rng, witness_count, violence)

        model = TIER2_MODEL if tier == 2 else TIER1_MODEL
        self.attempts[tier] += 1
        rendered = prompt.render(world, agent, nearby, _visible(world, agent), brief)
        # The utility AI already evaluates every precondition to score its own
        # options, so its candidate set is the authoritative list of what this
        # agent can actually do this tick. Deriving the tool schema from it means
        # the model is never offered an action the engine will refuse.
        possible = {verb for _, verb, _ in
                    brain.candidates(world, agent, witness_count, violence)}
        tools = prompt.tool_schema(
            allow_violence=self.allow_violence and violence,
            has_company=bool(nearby),
            can_reproduce=agent.can_reproduce(world.tick),
            allowed=possible)
        payload = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "system": rendered["system"],
            "tools": tools,
            "messages": [{"role": "user", "content": rendered["user"]}],
        }

        try:
            response = self.client.complete(payload)
        except Exception as exc:                       # CacheMiss, API errors
            if self.on_cache_miss == "error":
                raise
            self.fallbacks += 1
            log.emit(world.tick, "routing", agent=agent.id, tier=tier,
                     stakes=round(score, 3), model=model, outcome="fallback",
                     reason=type(exc).__name__)
            self.tier_counts[0] += 1
            return brain.choose(world, agent, rng, witness_count, violence)

        chosen = _parse(response)
        self.tier_counts[tier] += 1
        log.emit(world.tick, "routing", agent=agent.id, tier=tier,
                 stakes=round(score, 3), model=model,
                 outcome="chose" if chosen else "no_tool_call",
                 verb=chosen[0] if chosen else None)

        if chosen is None:
            self.invalid += 1
            return brain.choose(world, agent, rng, witness_count, violence)

        verb, params = chosen
        return self._normalize(world, agent, verb, params)

    # Verbs by the parameter they take. Kept as data so adding a verb to the
    # tool schema without teaching the normalizer about it is impossible.
    NODE_VERBS = ("move", "work")
    TARGET_VERBS = ("steal", "harm", "coerce", "speak", "teach", "form_bond", "give")

    def _normalize(self, world, agent, verb, params):
        """Map the model's arguments onto engine parameters.

        Every verb that takes an argument is listed. An earlier version covered
        only move/work/steal/harm, so `speak` arrived with empty params and the
        engine raised KeyError mid-run — the model was behaving correctly and
        the harness was not.

        Arguments that name something absent are passed through unchanged: the
        engine refuses them and the action simply fails, which is behaviour
        worth measuring rather than a bug worth repairing.
        """
        if verb in self.NODE_VERBS:
            return verb, {"node_id": params.get("node_id", "")}
        if verb == "give":
            return verb, {"target_id": params.get("target_id", ""),
                          "resource": params.get("resource", "food")}
        if verb in self.TARGET_VERBS:
            return verb, {"target_id": params.get("target_id", "")}
        return verb, {}

    def report(self) -> dict:
        decisions = sum(self.tier_counts.values()) or 1
        attempted = self.attempts[1] + self.attempts[2]
        return {
            "decisions": decisions,
            "tier0": self.tier_counts[0],
            "tier1": self.tier_counts[1],
            "tier2": self.tier_counts[2],
            "attempted_t1": self.attempts[1],
            "attempted_t2": self.attempts[2],
            # The cost lever: what fraction of ticks reached for a model at all.
            "escalation_rate": round(attempted / decisions, 4),
            "served_by_model": self.tier_counts[1] + self.tier_counts[2],
            "fallbacks": self.fallbacks,
            "no_tool_call": self.invalid,
        }
