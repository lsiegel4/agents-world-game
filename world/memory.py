"""Episodic memory with decay and salience-ranked retrieval — DESIGN.md §5.4.

Memory exists so §5.2's prompt can be rendered from state. What an agent is told
about its own past is a retrieval decision, and retrieval is ranked by salience:
affect intensity, recency, and goal relevance. An agent does not get its whole
history, it gets what it would plausibly have in mind.

Consolidation into semantic beliefs is an LLM pass and is left for the second
M1 slice; this is the episodic half, and it needs no model.
"""

CONSOLIDATE_EVERY = 300      # ticks between consolidation passes
CONSOLIDATE_MIN = 4          # episodes about one subject before it becomes a belief
RECENCY_HALFLIFE = 400.0     # ticks
DECAY_FLOOR = 0.02           # below this an episode is forgotten outright
MAX_EPISODES = 60


class Memory:
    def __init__(self):
        self.episodes = []       # [{tick, text, weight, tags}]

    def record(self, tick: int, text: str, weight: float = 1.0, tags=()) -> None:
        self.episodes.append({"tick": tick, "text": text,
                              "weight": weight, "tags": tuple(tags)})
        if len(self.episodes) > MAX_EPISODES:
            # Drop the least salient rather than the oldest: a shock from long
            # ago should outlive yesterday's uneventful harvest.
            self.episodes.sort(key=lambda e: -e["weight"])
            self.episodes = self.episodes[:MAX_EPISODES]
            self.episodes.sort(key=lambda e: e["tick"])

    def salience(self, episode: dict, tick: int) -> float:
        age = max(0, tick - episode["tick"])
        recency = 0.5 ** (age / RECENCY_HALFLIFE)
        return episode["weight"] * recency

    def decay(self, tick: int) -> None:
        self.episodes = [e for e in self.episodes
                         if self.salience(e, tick) >= DECAY_FLOOR]

    def recall(self, tick: int, k: int = 5) -> list:
        ranked = sorted(self.episodes, key=lambda e: -self.salience(e, tick))
        return sorted(ranked[:k], key=lambda e: e["tick"])

    def consolidate(self, agent, tick: int) -> list:
        """Fold repeated episodes into semantic beliefs — §5.4.

        Rule-based rather than model-driven, deliberately: this runs in the
        Tier 0 control arm too, and a control arm that needs an API key is not
        a control. The LLM version in cognition.py layers on top of this and is
        compared against it, not substituted for it.

        The rule is just repetition: four wrongs from the same person is no
        longer four memories, it is a belief about that person. Consolidation
        is lossy on purpose — the belief outlives the episodes it came from,
        which is how a grudge survives forgetting the incidents.
        """
        if tick - getattr(self, "_last_consolidated", 0) < CONSOLIDATE_EVERY:
            return []
        self._last_consolidated = tick

        tallies = {}
        for episode in self.episodes:
            for tag in episode["tags"]:
                if tag not in ("wronged", "helped", "learned", "witnessed"):
                    continue
                subject = episode["text"].split()[0]
                tallies[(tag, subject)] = tallies.get((tag, subject), 0) + 1

        formed = []
        for (tag, subject), count in sorted(tallies.items()):
            if count < CONSOLIDATE_MIN:
                continue
            claim = {"wronged": "dangerous", "helped": "generous",
                     "learned": "knowledgeable", "witnessed": "violent"}[tag]
            agent.believe(claim, subject, "own_experience", tick)
            formed.append((claim, subject))
        return formed
