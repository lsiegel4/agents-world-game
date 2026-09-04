"""Narrative extraction — DESIGN.md §8.

The stated product risk is that 300 agents doing errands is noise, not story.
The sim emits an event stream; a spectator needs an account. This turns one into
the other in three stages:

  salience   score every event on how much it matters
  threading  group related events into arcs with a beginning and a payoff
  chronicle  render high-salience threads as prose

The chronicler is template-driven here for the same reason the world generator
is: it has to run offline, replay exactly, and be testable without a key. A model
writes better prose and can be layered on top — but the selection of *what is
worth telling* is the hard part, and that is engine-side and free.
"""

import math

from . import stats

# What an event is worth before any context is applied. Routine production is
# not zero — a harvest matters when it is the one that fails — but it is close.
BASE_WEIGHT = {
    "killed": 12.0, "harm": 8.0, "coerce": 6.0, "steal": 5.0,
    "discovery": 9.0, "teach": 5.0, "form_bond": 4.0, "give": 2.0,
    "leave_message": 3.0, "speak": 1.0,
    "birth": 5.0, "goal_met": 4.0, "goal_abandoned": 5.0,
    "deck": 7.0, "belief": 2.0,
    "starvation": 4.0, "fever": 5.0, "injury": 4.0,
    "work": 0.1, "move": 0.05, "eat": 0.1, "repair": 0.1,
    "reproduce": 3.0, "idle": 0.0,
}

THREAD_WINDOW = 250      # ticks within which events can belong to one arc
MIN_THREAD = 2           # an arc needs at least a beginning and something after
MAX_THREAD = 12          # past this it is a chronicle of everything, not an arc


def _kind_of(record: dict) -> str:
    kind = record["kind"]
    if kind == "action":
        return record["verb"]
    if kind == "death":
        return record.get("cause", "starvation")
    if kind == "goal":
        return "goal_met" if record.get("outcome") == "met" else "goal_abandoned"
    return kind


def participants(record: dict, agent_ids=None) -> set:
    """Everyone an event touches. Threading follows people, not places.

    `target` carries a node id on move/work and an agent id on the social and
    violent verbs, so without the agent-id filter a resource node becomes a
    character and every arc that touched that node merges into one.
    """
    who = set()
    for field in ("agent", "target", "parent", "by", "about"):
        value = record.get(field)
        if isinstance(value, str) and value:
            who.add(value)
    for agent_id in (record.get("deaths") or []):
        who.add(agent_id)
    if isinstance(record.get("valence"), dict):
        who.update(record["valence"])
    if agent_ids is not None:
        who &= agent_ids
    return who


# Threading runs on events worth telling, not on everything. Routine production
# is scored (a harvest matters when it is the one that fails) but never seeds or
# extends an arc — otherwise every agent shares a node with every other and the
# whole run collapses into a single thread of thousands of events.
ROUTINE = {"work", "move", "eat", "repair", "idle", "speak"}

# Consequences are logged on the same tick as their cause, so tick order alone
# renders "X was killed by Y. Y attacked X." Deaths sort last within a tick.
WITHIN_TICK = {"killed": 3, "starvation": 3, "fever": 3, "injury": 3,
               "goal_met": 2, "goal_abandoned": 2, "birth": 1}


def score(records: list, agent_ids=None) -> list:
    """Salience for every event: base stakes, discounted by how common that kind
    of thing is in this world, raised by how many people it touched.

    Rarity matters more than it looks. The first killing in a peaceful world is
    a different event from the fortieth in a violent one, and a chronicle that
    weights them the same reads as a ledger.
    """
    counts = {}
    for record in records:
        kind = _kind_of(record)
        counts[kind] = counts.get(kind, 0) + 1

    scored = []
    for record in records:
        kind = _kind_of(record)
        base = BASE_WEIGHT.get(kind, 0.5)
        if base <= 0.0:
            continue
        rarity = 1.0 / math.sqrt(counts[kind])
        reach = 1.0 + 0.35 * max(0, len(participants(record, agent_ids)) - 1)
        witnessed = 1.25 if record.get("observed") else 1.0
        scored.append({"record": record, "kind": kind,
                       "salience": base * rarity * reach * witnessed,
                       "tick": record.get("tick", 0),
                       "who": participants(record, agent_ids)})
    scored.sort(key=lambda e: (-e["salience"], e["tick"]))
    return scored


def thread(scored: list, window: int = THREAD_WINDOW) -> list:
    """Group events into arcs: same people, close in time.

    An arc is not a topic, it is a set of people something happened between. A
    theft, the grudge it leaves, and the retaliation two hundred ticks later are
    one story; two unrelated harvests are not a story at all.
    """
    ordered = sorted((e for e in scored if e["kind"] not in ROUTINE),
                     key=lambda e: e["tick"])
    threads = []

    for event in ordered:
        placed = False
        for arc in threads:
            if event["tick"] - arc["last_tick"] > window:
                continue
            if len(arc["events"]) >= MAX_THREAD:
                continue
            if arc["who"] & event["who"]:
                arc["events"].append(event)
                arc["who"] |= event["who"]
                arc["last_tick"] = event["tick"]
                arc["salience"] += event["salience"]
                placed = True
                break
        if not placed:
            threads.append({"events": [event], "who": set(event["who"]),
                            "first_tick": event["tick"], "last_tick": event["tick"],
                            "salience": event["salience"]})

    threads = [t for t in threads if len(t["events"]) >= MIN_THREAD]
    threads.sort(key=lambda t: -t["salience"])
    return threads


# --------------------------------------------------------------------- prose

DECK_PHRASING = {
    "fever": "a sickness", "late_frost": "a late frost", "good_cut": "a good cutting",
    "finding": "an unexpected find", "injury": "a season of accidents",
    "storm": "a storm",
}

PHRASING = {
    "steal": "{a} took food from {b}",
    "harm": "{a} attacked {b}",
    "coerce": "{a} demanded food from {b}",
    "killed": "{victim} was killed by {killer}",
    "teach": "{a} taught {tech} to {b}",
    "give": "{a} gave to {b}",
    "form_bond": "{a} and {b} bound themselves to each other",
    "discovery": "{a} worked out {tech} alone",
    "birth": "{child} was born to {parent}",
    "goal_met": "{a} finished what they had set out to do",
    "goal_abandoned": "{a} gave up on what they had set out to do",
    "leave_message": "{a} left word behind",
    "starvation": "{a} starved",
    "fever": "{a} died of fever",
    "injury": "{a} died of an injury",
    "speak": "{a} told {b} what they thought of {c}",
    "deck": "{event} came to the basin",
}


def _render_event(event: dict, names: dict) -> str:
    """Render one event.

    Field meanings differ by kind and cannot share one mapping: on a death
    `agent` is the victim and `by` the killer; on a birth `agent` is the child
    and `parent` the parent. Collapsing them produced "X was born to X" and
    named killers as their own victims.
    """
    record = event["record"]
    name = lambda i: names.get(i, i) if i else "someone"
    template = PHRASING.get(event["kind"])
    if not template:
        return ""
    return template.format(
        a=name(record.get("agent")),
        b=name(record.get("target")),
        c=name(record.get("about")),
        victim=name(record.get("agent")),
        killer=name(record.get("by")),
        child=name(record.get("agent")),
        parent=name(record.get("parent")),
        tech=record.get("technique", "something"),
        event=DECK_PHRASING.get(record.get("event", ""), "something"))


def chronicle(threads: list, names: dict, limit: int = 5) -> list:
    """Prose for the highest-salience arcs. One paragraph per arc."""
    out = []
    for arc in threads[:limit]:
        lines = [_render_event(e, names) for e in
                 sorted(arc["events"],
                        key=lambda e: (e["tick"], WITHIN_TICK.get(e["kind"], 0)))]
        lines = [line for line in lines if line]
        if len(lines) < MIN_THREAD:
            continue
        # Sentences start with a capital. Deck phrasings begin lowercase by
        # design ("a good cutting") so they read inside a clause too.
        sentences = [line[0].upper() + line[1:] if line else line for line in lines]
        out.append({
            "from": arc["first_tick"], "to": arc["last_tick"],
            "who": sorted(names.get(i, i) for i in arc["who"]),
            "salience": round(arc["salience"], 2),
            "text": ". ".join(sentences) + ".",
        })
    return out


def personal_feed(agent_id: str, scored: list, names: dict, limit: int = 8) -> list:
    """What one agent would know about, from where they were standing.

    Deliberately partial. An agent learns it was betrayed at the same time and in
    the same distorted way the agent did (§8) — events they were not party to and
    did not witness simply do not appear.
    """
    mine = [e for e in scored if agent_id in e["who"]]
    mine.sort(key=lambda e: -e["salience"])
    return [{"tick": e["tick"], "salience": round(e["salience"], 2),
             "text": _render_event(e, names)}
            for e in mine[:limit] if _render_event(e, names)]


def summary(records: list, agent_ids=None) -> dict:
    scored = score(records, agent_ids)
    threads = thread(scored)
    return {
        "events_scored": len(scored),
        "threads": len(threads),
        "mean_thread_length": round(
            stats.mean([len(t["events"]) for t in threads]), 2) if threads else 0.0,
        "top_salience": round(threads[0]["salience"], 2) if threads else 0.0,
    }
