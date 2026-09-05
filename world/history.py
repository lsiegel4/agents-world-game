"""Passes 4-6 of §4.1: history, culture, and myth.

Template-driven and seeded, so a world generates offline, deterministically, and
free. §4.1 calls for a model here and a model produces better prose — but a
generator that *requires* one cannot be replayed years later, cannot run in the
Tier 0 control arm, and cannot be tested without a key. The model enriches this;
it does not supply it.

Two rules from §4.1, both load-bearing:

  History is not uniformly known.  Every fact carries a `visibility`: common,
  local, specialist, or lost. Agents can only query what they could plausibly
  know, and recovering a lost fact is a goal in its own right.

  Myth may contradict history.  Pass 6 deliberately distorts pass 4. Agents act
  on myth. The gap between what happened and what is believed is a measurable
  quantity — see `myth_divergence` — and it is where most of the story lives.
"""

VISIBILITIES = ("common", "local", "specialist", "lost")

ERA_KINDS = ("founding", "growth", "conflict", "plague", "collapse",
             "migration", "recovery", "famine", "flood", "schism",
             "boom", "isolation", "reckoning")

# What can plausibly follow what. A recovery needs something to recover from,
# and a founding happens once. Without this the generator emits sequences like
# "the Founding, the Recovery" — grammatical, and nonsense.
SUCCESSION = {
    "founding":  ("growth", "conflict", "migration", "boom", "isolation"),
    "growth":    ("boom", "conflict", "plague", "migration", "schism", "famine"),
    "boom":      ("schism", "conflict", "growth", "famine", "reckoning"),
    "conflict":  ("collapse", "recovery", "migration", "plague", "reckoning",
                  "schism"),
    "schism":    ("conflict", "migration", "isolation", "reckoning"),
    "plague":    ("collapse", "recovery", "migration", "isolation", "famine"),
    "famine":    ("migration", "collapse", "conflict", "recovery"),
    "flood":     ("collapse", "recovery", "migration", "famine"),
    "collapse":  ("migration", "recovery", "isolation"),
    "migration": ("founding", "growth", "conflict", "boom"),
    "isolation": ("recovery", "schism", "famine", "growth"),
    "reckoning": ("recovery", "isolation", "growth", "schism"),
    "recovery":  ("growth", "boom", "conflict", "plague", "flood"),
}

# Eras are named for what they felt like, not what a chronicler classified them
# as. Several candidates per kind so two worlds rarely read the same.
ERA_NAMES = {
    "founding":  ("the Founding", "the First Stones", "the Coming",
                  "the Staking", "the Break of Ground"),
    "growth":    ("the Long Summers", "the Full Years", "the Widening",
                  "the Green Decades", "the Spreading"),
    "boom":      ("the Fat Years", "the Overflowing", "the Loud Years",
                  "the Glut", "the Bright Season"),
    "conflict":  ("the Water Wars", "the Breaking", "the Years of Knives",
                  "the Quarrel", "the Hard Words"),
    "schism":    ("the Parting", "the Two Halls", "the Split Word",
                  "the Falling-Out", "the Divided Table"),
    "plague":    ("the Fever Years", "the Sealing", "the Quiet Years",
                  "the Thinning", "the Shut Doors"),
    "famine":    ("the Hungry Years", "the Thin Harvests", "the Long Want",
                  "the Empty Stores", "the Winter That Stayed"),
    "flood":     ("the Great Wash", "the Rising", "the Year Underwater",
                  "the Drowning of the Low Ground", "the Broken Weir"),
    "collapse":  ("the Falling", "the Abandonment", "the Undoing",
                  "the End of the Old Order", "the Scattering"),
    "migration": ("the Walking", "the Coming of Strangers", "the Emptying",
                  "the Long Road", "the Exchange of Peoples"),
    "isolation": ("the Closed Years", "the Turning Inward", "the Shut Basin",
                  "the Silence", "the Years Without News"),
    "reckoning": ("the Reckoning", "the Accounting", "the Settling of Debts",
                  "the Judgement", "the Old Scores"),
    "recovery":  ("the Rebuilding", "the Second Kindling", "the Relearning",
                  "the Return", "the Slow Mending"),
}

ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth")

ERA_EVENTS = {
    "founding":  ["{people} settled at {place} and dug the first well",
                  "the boundary stones were laid at {place}",
                  "{place} and {other} agreed where one ended and the other began",
                  "the first {craft} in the basin was worked at {place}",
                  "a child was born at {place} before the roof was finished"],
    "growth":    ["the {craft} of {place} became known beyond the basin",
                  "{place} raised a hall large enough to hold everyone",
                  "the road between {place} and {other} was cut and kept",
                  "{place} took in more families than it had beds for",
                  "three good harvests running were counted at {place}"],
    "boom":      ["{place} traded {craft} for more than it was worth",
                  "everyone at {place} was owed something by someone",
                  "the hall at {place} was rebuilt twice in a decade",
                  "{other} sent people to learn the {craft} of {place}"],
    "conflict":  ["{place} and {other} fought over the water rights at {place}",
                  "the {craft} guild of {place} was broken up by force",
                  "{other} burned the standing crop at {place}",
                  "a killing at {place} went unanswered for a year",
                  "the boundary stones between {place} and {other} were moved at night"],
    "schism":    ["half of {place} would no longer sit with the other half",
                  "the {craft} workers of {place} kept their method to themselves",
                  "two halls stood at {place} where one had been",
                  "{place} stopped sending word to {other}"],
    "plague":    ["a fever took a third of {place} in one winter",
                  "the wells at {place} were sealed and not reopened",
                  "no one went between {place} and {other} for two years",
                  "the {craft} of {place} died with the last who knew it",
                  "the burial ground at {place} was extended twice"],
    "famine":    ["the stores at {place} were empty before midwinter",
                  "{place} ate the seed corn and had none to sow",
                  "{other} refused grain to {place} and was remembered for it",
                  "the herds of {place} were slaughtered early"],
    "flood":     ["the river took the low ground at {place}",
                  "the weir above {place} was overtopped in a night",
                  "{place} moved uphill and left its foundations behind",
                  "the ford between {place} and {other} was impassable for a season"],
    "collapse":  ["{place} was abandoned within a single season",
                  "the weir above {place} gave way and was never rebuilt",
                  "nothing was harvested at {place} that year or the next",
                  "the last families of {place} walked out without saying where"],
    "migration": ["the people of {place} walked east and did not return",
                  "newcomers took the empty ground at {place}",
                  "half of {other} arrived at {place} in one summer",
                  "{people} came up the river and stayed"],
    "isolation": ["{place} let the road to {other} grow over",
                  "no stranger was admitted at {place} for a generation",
                  "the {craft} of {place} drifted from how it was done elsewhere",
                  "{place} kept its own count of the years"],
    "reckoning": ["the debts of {place} were called in at once",
                  "{place} put its elders to answer for the {craft} guild",
                  "what {other} did at {place} was finally spoken aloud",
                  "the boundary stones were walked and disputed at {place}"],
    "recovery":  ["{place} was resettled by people who did not know its name",
                  "the {craft} of {place} was worked out a second time",
                  "the road between {place} and {other} was opened again",
                  "the wells at {place} were unsealed and found sweet",
                  "someone at {place} wrote down what had nearly been lost"],
}

CRAFTS = ("salt-glaze", "reed-thatching", "coppicing", "kiln-firing",
          "weir-building", "bone-setting", "fish-smoking", "withy-weaving",
          "charcoal-burning", "dye-setting", "horn-working", "malting",
          "drystone-walling", "tanning", "rope-laying", "bell-founding")

# Combinatorial rather than a fixed list: 18 x 14 gives 252 possible names, so
# two worlds sharing a place name is a coincidence rather than the norm.
PLACE_PREFIX = ("Low", "High", "Beck", "Ash", "Kestrel", "Nine", "Stone",
                "Tallow", "Ord", "Marsh", "Elder", "Cold", "Fair", "Grey",
                "Thorn", "Wold", "Har", "Bram")
PLACE_SUFFIX = ("marsh", "with", "ry", " Ford", " Wells", "cross", "cote",
                "bury", "hollow", " Reach", "gate", "fell", "mere", "stead")

# How a myth bends the fact it came from.
DISTORTIONS = (
    ("blames", "{subject} is remembered as the cause, though the record says otherwise"),
    ("inflates", "the loss is remembered as far greater than it was"),
    ("diminishes", "it is remembered as a small thing that troubled nobody"),
    ("relocates", "it is remembered as happening at {elsewhere}"),
    ("moralizes", "it is remembered as a punishment rather than an accident"),
    ("erases", "the people who suffered it are not remembered at all"),
    ("inverts", "the ones who fled are remembered as the ones who stayed"),
    ("personifies", "it is remembered as the work of one named person"),
    ("predates", "it is remembered as far older than it is"),
    ("merges", "it is remembered as the same event as something at {elsewhere}"),
)


def _visibility(rng, age_fraction: float) -> str:
    """Older facts are likelier to have been lost. Recent ones are common."""
    roll = rng.random() * (1.0 + age_fraction * 2.2)
    if roll < 0.35:
        return "common"
    if roll < 0.75:
        return "local"
    if roll < 1.35:
        return "specialist"
    return "lost"


def generate_history(sites: list, rng, years: int = 600) -> dict:
    """Pass 4. Eras, and the facts inside them, each with a visibility.

    Measured in seasons. The engine has no year (§4.3) — the tick is primitive
    and a season is a named multiple of it, so the past is counted in the same
    unit as the present rather than in a second clock nothing converts to.
    """
    places = []
    while len(places) < max(1, len(sites)):
        name = (rng.choice(PLACE_PREFIX) + rng.choice(PLACE_SUFFIX))
        if name not in places:
            places.append(name)
    eras, facts = [], []
    year, era_index = 0, 0

    # Always begins with a founding; each era after it is drawn from what could
    # plausibly follow the one before.
    sequence = ["founding"]
    for _ in range(rng.randint(4, 7)):
        sequence.append(rng.choice(SUCCESSION[sequence[-1]]))

    seen_kinds, used_names = {}, set()
    for kind in sequence:
        span = max(25, int(years / len(sequence) * (0.6 + rng.random() * 0.8)))
        seen_kinds[kind] = seen_kinds.get(kind, 0) + 1
        # Named for what it felt like. Repeats of a kind get distinct names
        # where possible, and fall back to an ordinal only if they collide.
        options = [n for n in ERA_NAMES[kind] if n not in used_names]
        if options:
            name = rng.choice(options)
        else:
            ordinal = ORDINALS[min(seen_kinds[kind] - 1, len(ORDINALS) - 1)]
            name = f"the {ordinal} {kind.title()}"
        used_names.add(name)
        era = {"kind": kind, "from": year, "to": min(years, year + span),
               "name": name}
        eras.append(era)

        # Not every era leaves the same amount of record behind.
        templates = list(ERA_EVENTS[kind])
        rng.shuffle(templates)
        for template in templates[:rng.randint(2, len(templates))]:
            place = rng.choice(places)
            other = rng.choice([p for p in places if p != place] or [place])
            claim = template.format(place=place, other=other,
                                    craft=rng.choice(CRAFTS),
                                    people=rng.choice(("hill people", "the river folk",
                                                       "families from the east")))
            age_fraction = 1.0 - (era["to"] / years)
            facts.append({"claim": claim, "year": era["from"] + rng.randrange(span),
                          "place": place, "era": era["name"],
                          "visibility": _visibility(rng, age_fraction),
                          "true": True})
        year = era["to"]
        era_index += 1

    return {"seasons": years, "eras": eras, "facts": facts, "places": places}


def generate_culture(history: dict, rng) -> dict:
    """Pass 5. Derived from what happened — taboos follow disasters."""
    kinds = [era["kind"] for era in history["eras"]]
    taboos, festivals = [], []

    if "plague" in kinds:
        taboos.append("never draw from a sealed well")
    if "conflict" in kinds:
        taboos.append("no blade is carried into a hall")
    if "collapse" in kinds:
        taboos.append("a weir is repaired before it is needed, never after")
    if "migration" in kinds:
        taboos.append("a stranger is fed before being asked their business")
    if not taboos:
        taboos.append("the first cut of the season is left standing")

    festivals.append({"name": "the Feast of Nine Wells",
                      "when": rng.randrange(history["seasons"]) % 4,
                      "for": "the dead of " + rng.choice(history["eras"])["name"]})

    return {"naming": rng.choice(("patronymic", "place-bound", "craft-bound")),
            "taboos": taboos, "festivals": festivals,
            "staple": rng.choice(("reed-flour", "river fish", "barley", "goat"))}


def generate_myth(history: dict, rng, count: int = 5) -> list:
    """Pass 6. Stories the world tells about itself, deliberately distorted.

    Each myth points at a real fact and bends it. Agents act on the myth; the
    record still holds the fact. That gap is the measurable part.
    """
    myths = []
    pool = [f for f in history["facts"] if f["visibility"] != "common"] or history["facts"]
    for _ in range(min(count, len(pool))):
        fact = pool[rng.randrange(len(pool))]
        name, phrasing = DISTORTIONS[rng.randrange(len(DISTORTIONS))]
        elsewhere = rng.choice([p for p in history["places"] if p != fact["place"]]
                               or history["places"])
        myths.append({
            "about": fact["claim"],
            "distortion": name,
            "as_told": phrasing.format(subject=fact["place"], elsewhere=elsewhere),
            "believed_by": "common",
            "true": False,
        })
    return myths


def myth_divergence(history: dict, myths: list) -> float:
    """Fraction of remembered facts that the myths have bent.

    §4.1: "The gap between recorded history and believed myth is a measurable
    quantity and a rich source of story." This is that quantity.
    """
    if not history["facts"]:
        return 0.0
    distorted = {m["about"] for m in myths}
    return len(distorted) / len(history["facts"])


def knowable(history: dict, place: str = "") -> list:
    """What an agent could plausibly know: common knowledge everywhere, local
    knowledge where they are. Specialist knowledge needs a specialist; lost
    knowledge needs recovering."""
    out = []
    for fact in history["facts"]:
        if fact["visibility"] == "common":
            out.append(fact)
        elif fact["visibility"] == "local" and fact["place"] == place:
            out.append(fact)
    return out
