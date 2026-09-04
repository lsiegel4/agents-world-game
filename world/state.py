"""World and agent state.

Everything here is plain data plus the minimum mechanics that operate on it.
No cognition, no randomness — the tick loop owns the PRNG (see sim.py).
"""

from dataclasses import dataclass, field

FOOD = "food"
WOOD = "wood"
RESOURCE_KINDS = (FOOD, WOOD)

# Drive names for the walking skeleton. The full set in DESIGN.md §5.1 adds
# status, belonging, autonomy, legacy.
DRIVES = ("survival", "mastery", "curiosity")

HARVEST_RATE = 2.0          # units removed from a node per work action
OVERHARVEST_THRESHOLD = 0.3  # node stock fraction below which harvesting degrades it
DEGRADATION_STEP = 0.05
DEGRADATION_CAP = 0.8
DEGRADATION_RECOVERY = 0.005

HUNGER_PER_TICK = 1.0
HUNGER_PER_MEAL = 12.0
STARVATION_THRESHOLD = 40.0

MAX_CARRY = 12.0            # per resource kind; hoarding has to terminate somewhere
SHELTER_DECAY = 0.02        # shelter lost per tick
SHELTER_PER_WOOD = 0.15     # shelter restored per unit of wood spent repairing
EXPOSURE_PENALTY = 1.4      # hunger multiplier at zero shelter

# Reproduction. A child inherits its parent's *current* drive vector plus noise,
# not the archetype baseline — so generational drift is measurable and DESIGN.md
# §7.6's value lock-in test (founder cohort vs later generations) is runnable.
REPRO_MIN_AGE = 60
REPRO_MIN_FOOD = 9.0
REPRO_FOOD_COST = 6.0       # paid by the parent
REPRO_CHILD_FOOD = 3.0      # of which the child is endowed with this much
REPRO_MIN_SHELTER = 0.6
REPRO_COOLDOWN = 80
DRIVE_INHERIT_NOISE = 0.06

# --- Violence (§5.5, §5.6) -------------------------------------------------
# There is no aggression drive. The harm verbs draw their utility from drives
# that already exist, and `restraint` scales that utility down. Restraint takes
# its value from nature (baseline + noise), upbringing (inherited from the
# parent's *current* value), and environment (eroded by hunger, victimization
# and habituation; recovers toward baseline during stability).
RESTRAINT_BASE = 0.60
RESTRAINT_NOISE = 0.15           # nature: spread at world creation
RESTRAINT_INHERIT_NOISE = 0.08   # upbringing: spread around the parent's value
RESTRAINT_RECOVERY = 0.010       # per tick, toward the hunger-adjusted target
RESTRAINT_HUNGER_EROSION = 0.45  # how far sustained hunger pulls the target down
HABITUATION = 0.030              # committing harm lowers your own restraint
VICTIM_RESTRAINT_LOSS = 0.055    # being wronged lowers it further

INTERACT_RADIUS = 1              # who you can reach
WITNESS_RADIUS = 2               # who can see it

STEAL_AMOUNT = 3.0
HARM_SHELTER_LOSS = 0.40
HARM_HUNGER = 10.0
HARM_DEATH_P = 0.15
GRUDGE_PER_OFFENSE = 1.0
GRUDGE_DECAY = 0.0015

# --- Social verbs (§5.5, M1 slice 2) ---------------------------------------
GIVE_AMOUNT = 3.0
FAVOR_PER_GIFT = 1.0
FAVOR_DECAY = 0.0010
BOND_RADIUS = 1            # you must be beside someone to bond with them
COERCE_TAKE = 3.0
MESSAGE_TTL = 600          # ticks a left message stays legible
MAX_BELIEFS = 12


@dataclass
class ResourceNode:
    id: str
    kind: str
    x: int
    y: int
    amount: float
    capacity: float
    regen_rate: float           # fraction of capacity restored per tick when undamaged
    degradation: float = 0.0    # 0..1, raised by overharvest, suppresses regen

    def stock_fraction(self) -> float:
        return self.amount / self.capacity if self.capacity else 0.0

    def harvest(self) -> float:
        """Remove up to HARVEST_RATE. Harvesting a depleted node degrades it."""
        taken = min(self.amount, HARVEST_RATE)
        self.amount -= taken
        if self.stock_fraction() < OVERHARVEST_THRESHOLD:
            self.degradation = min(DEGRADATION_CAP, self.degradation + DEGRADATION_STEP)
        return taken

    def regenerate(self) -> None:
        """State-dependent regen: a degraded node recovers more slowly (DESIGN.md §4.4)."""
        effective = self.regen_rate * (1.0 - self.degradation)
        self.amount = min(self.capacity, self.amount + effective * self.capacity)
        self.degradation = max(0.0, self.degradation - DEGRADATION_RECOVERY)


@dataclass
class Agent:
    id: str
    name: str
    x: int
    y: int
    drives: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    hunger: float = 0.0
    shelter: float = 1.0
    age: int = 0
    alive: bool = True
    cause_of_death: str = ""
    parent: str = ""
    generation: int = 0
    last_birth: int = -10**6
    restraint: float = RESTRAINT_BASE
    restraint_base: float = RESTRAINT_BASE
    grudges: dict = field(default_factory=dict)   # agent_id -> accumulated offence
    memory: object = None                         # world.memory.Memory, lazily attached
    goal: dict = field(default_factory=dict)      # private; never in another agent's view
    goal_history: list = field(default_factory=list)   # every goal held, in order
    counters: dict = field(default_factory=dict)  # tallies goals are scored against
    techniques: set = field(default_factory=set)  # what this agent knows how to do
    favors: dict = field(default_factory=dict)    # agent_id -> kindness owed; grudge's mirror
    bonds: set = field(default_factory=set)       # agent_ids this agent is tied to
    beliefs: list = field(default_factory=list)   # [{claim, about, source, tick}]

    def has(self, kind: str) -> float:
        return self.inventory.get(kind, 0.0)

    def can_reproduce(self, tick: int) -> bool:
        return (self.alive
                and self.age >= REPRO_MIN_AGE
                and self.has(FOOD) >= REPRO_MIN_FOOD
                and self.shelter >= REPRO_MIN_SHELTER
                and tick - self.last_birth >= REPRO_COOLDOWN)

    def grudge_against(self, other_id: str) -> float:
        return self.grudges.get(other_id, 0.0)

    def favor_from(self, other_id: str) -> float:
        return self.favors.get(other_id, 0.0)

    def standing(self, other_id: str) -> float:
        """Net regard: kindness received minus wrongs done. Bonds add to it."""
        base = self.favor_from(other_id) - self.grudge_against(other_id)
        return base + (1.5 if other_id in self.bonds else 0.0)

    def believe(self, claim: str, about: str, source: str, tick: int) -> None:
        for b in self.beliefs:
            if b["claim"] == claim and b["about"] == about:
                b["tick"] = tick
                return
        self.beliefs.append({"claim": claim, "about": about,
                             "source": source, "tick": tick})
        if len(self.beliefs) > MAX_BELIEFS:
            self.beliefs.pop(0)

    def exposure(self) -> float:
        """Hunger multiplier from a decayed shelter. 1.0 when fully sheltered."""
        return 1.0 + EXPOSURE_PENALTY * (1.0 - self.shelter)


@dataclass
class World:
    width: int
    height: int
    nodes: list = field(default_factory=list)
    agents: list = field(default_factory=list)
    tick: int = 0
    last_disaster: int = 0
    messages: list = field(default_factory=list)  # [{x, y, claim, about, by, tick}]

    def node_by_id(self, node_id: str):
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def living_agents(self) -> list:
        return [a for a in self.agents if a.alive]
