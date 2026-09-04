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
