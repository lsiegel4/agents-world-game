"""Tests for §8's narrative extraction.

The selection of what is worth telling is engine-side and free; these guard it.
"""

import unittest

from world import narrative
from world.sim import run


def _run(seed=42, ticks=2500):
    world, log = run(seed, ticks, {"worldgen": "generated"})
    ids = {a.id for a in world.agents}
    names = {a.id: a.name for a in world.agents}
    return world, log, ids, names


class TestSalience(unittest.TestCase):
    def test_rare_events_outrank_common_ones(self):
        _, log, ids, _ = _run()
        scored = narrative.score(log.records, ids)
        by_kind = {}
        for event in scored:
            by_kind.setdefault(event["kind"], []).append(event["salience"])
        self.assertIn("work", by_kind)
        routine = max(by_kind["work"])
        for rare in ("killed", "discovery"):
            if rare in by_kind:
                self.assertGreater(max(by_kind[rare]), routine * 10)

    def test_participants_excludes_places(self):
        """`target` is a node id on move/work and an agent id on the social
        verbs. Without filtering, a resource node becomes a character and every
        arc that touched it merges into one."""
        _, log, ids, _ = _run()
        for event in narrative.score(log.records, ids):
            for who in event["who"]:
                self.assertIn(who, ids)


class TestThreading(unittest.TestCase):
    def test_threads_are_bounded_not_one_blob(self):
        """Threading every event links everyone through shared resource use and
        collapses a whole run into a single arc of thousands."""
        _, log, ids, _ = _run()
        threads = narrative.thread(narrative.score(log.records, ids))
        self.assertGreater(len(threads), 10)
        for arc in threads:
            self.assertLessEqual(len(arc["events"]), narrative.MAX_THREAD)
            self.assertGreaterEqual(len(arc["events"]), narrative.MIN_THREAD)

    def test_routine_actions_never_seed_an_arc(self):
        _, log, ids, _ = _run()
        threads = narrative.thread(narrative.score(log.records, ids))
        for arc in threads:
            for event in arc["events"]:
                self.assertNotIn(event["kind"], narrative.ROUTINE)

    def test_arc_members_are_connected_by_people(self):
        _, log, ids, _ = _run()
        for arc in narrative.thread(narrative.score(log.records, ids)):
            self.assertTrue(arc["who"])
            self.assertLessEqual(arc["last_tick"] - arc["first_tick"],
                                 narrative.THREAD_WINDOW * len(arc["events"]))


class TestProse(unittest.TestCase):
    def test_cause_precedes_consequence_within_a_tick(self):
        """A death is logged on the same tick as the blow that caused it, so
        tick order alone renders 'X was killed by Y. Y attacked X.'"""
        _, log, ids, names = _run()
        threads = narrative.thread(narrative.score(log.records, ids))
        for entry in narrative.chronicle(threads, names, limit=12):
            text = entry["text"]
            if "was killed by" in text and "attacked" in text:
                self.assertLess(text.index("attacked"), text.index("was killed by"))

    def test_birth_and_death_name_the_right_people(self):
        """Field meanings differ by kind: on a death `agent` is the victim and
        `by` the killer; on a birth `agent` is the child. One shared mapping
        produced 'X was born to X'."""
        _, log, ids, names = _run()
        scored = narrative.score(log.records, ids)
        for event in scored:
            text = narrative._render_event(event, names)
            if event["kind"] == "birth" and " was born to " in text:
                child, parent = text.split(" was born to ")
                self.assertNotEqual(child, parent.rstrip("."))

    def test_names_are_distinct_enough_to_follow(self):
        """Every child taking the parent's name collapsed all lineages onto one
        word and made a chronicle unreadable."""
        world, _, _, names = _run()
        self.assertGreater(len(set(names.values())), len(names) * 0.5)


class TestPersonalFeed(unittest.TestCase):
    def test_feed_is_partial(self):
        """An agent learns what happened to it, not what happened (§8)."""
        world, log, ids, names = _run()
        scored = narrative.score(log.records, ids)
        agent = next(a for a in world.agents if a.cause_of_death)
        feed = narrative.personal_feed(agent.id, scored, names)
        self.assertTrue(feed)
        self.assertLess(len(feed), len(scored))

    def test_feed_only_contains_events_the_agent_was_party_to(self):
        world, log, ids, names = _run()
        scored = narrative.score(log.records, ids)
        agent = world.agents[0]
        mine = {id(e) for e in scored if agent.id in e["who"]}
        for entry in narrative.personal_feed(agent.id, scored, names):
            match = [e for e in scored if e["tick"] == entry["tick"]
                     and narrative._render_event(e, names) == entry["text"]]
            self.assertTrue(any(id(e) in mine for e in match))


if __name__ == "__main__":
    unittest.main()
