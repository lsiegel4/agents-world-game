"""The M0 determinism gate.

DESIGN.md §2.7: a run that cannot be reproduced from (seed, config, code) is
anecdote, not data. These tests are the thing that keeps that true.

    python3 -m unittest discover tests
"""

import unittest

from world.sim import run


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_log(self):
        _, a = run(seed=42, ticks=300)
        _, b = run(seed=42, ticks=300)
        self.assertEqual(a.digest(), b.digest())
        self.assertEqual(a.lines(), b.lines())

    def test_different_seed_different_log(self):
        _, a = run(seed=42, ticks=300)
        _, b = run(seed=43, ticks=300)
        self.assertNotEqual(a.digest(), b.digest())

    def test_replay_across_many_seeds(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                _, a = run(seed=seed, ticks=150)
                _, b = run(seed=seed, ticks=150)
                self.assertEqual(a.digest(), b.digest())


class TestLogIsAppendOnly(unittest.TestCase):
    """An append-only log that changes after the fact is not a log (§2.7).

    `emit` stored references to mutable arguments, so `drives=child.drives`
    kept the live object: the agent went on mutating it for hundreds of ticks
    and the birth record ended up reporting that agent's *final* drives. Nothing
    crashed and the numbers looked plausible. It surfaced only because streaming
    to disk serialises on write, so the two modes disagreed.
    """

    def test_emit_copies_mutable_arguments(self):
        from world.log import EventLog
        log = EventLog()
        drives = {"survival": 0.4, "mastery": 0.3}
        log.emit(1, "birth", agent="a", drives=drives)
        drives["survival"] = 0.99          # the agent lives on and changes
        self.assertEqual(list(log.records)[-1]["drives"]["survival"], 0.4)

    def test_emit_copies_sequences(self):
        from world.log import EventLog
        log = EventLog()
        members = ["a", "b"]
        log.emit(1, "cast", members=members)
        members.append("c")
        self.assertEqual(len(list(log.records)[-1]["members"]), 2)


class TestStreamingLog(unittest.TestCase):
    """Streaming exists because the log is otherwise held entirely in memory —
    ~100k records per 800-tick world at 120 agents, which exhausted RAM and
    killed two experiment runs. A world that never ends cannot hold its log at
    all."""

    def test_streamed_and_memory_logs_agree(self):
        import os
        import tempfile
        from world.sim import run
        with tempfile.TemporaryDirectory() as d:
            _, memory = run(4, 250)
            _, streamed = run(4, 250, {"log_path": os.path.join(d, "ev.jsonl")})
            self.assertEqual(memory.digest(), streamed.digest())
            self.assertEqual(len(memory.records), len(streamed.records))

    def test_streamed_records_are_readable_and_counted(self):
        import os
        import tempfile
        from world.sim import run
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ev.jsonl")
            _, log = run(4, 200, {"log_path": path})
            self.assertTrue(os.path.getsize(path) > 0)
            # len() must not require reading the file back
            self.assertEqual(len(log.records), sum(1 for _ in log.records))
            self.assertEqual(next(iter(log.records))["kind"], "header")

    def test_streaming_does_not_change_the_world(self):
        import os
        import tempfile
        from world.sim import run
        with tempfile.TemporaryDirectory() as d:
            w1, _ = run(6, 300)
            w2, _ = run(6, 300, {"log_path": os.path.join(d, "ev.jsonl")})
            self.assertEqual(len(w1.living_agents()), len(w2.living_agents()))
            self.assertEqual([a.id for a in w1.agents], [a.id for a in w2.agents])


class TestWorldState(unittest.TestCase):
    def test_nodes_never_go_negative(self):
        world, _ = run(seed=7, ticks=400)
        for node in world.nodes:
            self.assertGreaterEqual(node.amount, 0.0)
            self.assertLessEqual(node.amount, node.capacity)

    def test_degradation_stays_in_range(self):
        world, _ = run(seed=7, ticks=400)
        for node in world.nodes:
            self.assertGreaterEqual(node.degradation, 0.0)
            self.assertLessEqual(node.degradation, 0.8)

    def test_drives_stay_in_range(self):
        world, _ = run(seed=7, ticks=400)
        for agent in world.agents:
            for name, value in agent.drives.items():
                self.assertGreaterEqual(value, 0.05, name)
                self.assertLessEqual(value, 0.99, name)


if __name__ == "__main__":
    unittest.main()
