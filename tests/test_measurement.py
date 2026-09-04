"""Tests for the M2 measurement layer.

The statistics are hand-rolled, so they get checked against cases with known
answers. The profile tests guard the confound that made policy look three times
more important than it is.
"""

import random
import unittest

from world import indices, profiles, stats
from world.sim import run


class TestStats(unittest.TestCase):
    def test_gini_bounds(self):
        self.assertAlmostEqual(stats.gini([5, 5, 5, 5]), 0.0)
        self.assertGreater(stats.gini([0, 0, 0, 20]), 0.7)
        self.assertEqual(stats.gini([]), 0.0)
        self.assertEqual(stats.gini([0, 0]), 0.0)

    def test_entropy_bounds(self):
        self.assertAlmostEqual(stats.entropy([1, 1, 1, 1]), 1.0)
        self.assertLess(stats.entropy([10, 1, 1, 1]), 0.7)
        self.assertEqual(stats.entropy([5]), 0.0)

    def test_ols_recovers_known_coefficients(self):
        rng = random.Random(1)
        xs, ys = [], []
        for _ in range(300):
            a, b, c = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
            xs.append([a, b, c])
            ys.append(3 * a - 1 * b + 0.2 * c + rng.gauss(0, 0.4))
        fit = stats.ols(xs, ys)
        self.assertGreater(fit["r2"], 0.9)
        b0, b1, b2 = fit["betas"]
        self.assertAlmostEqual(b0 / b1, -3.0, delta=0.4)   # true ratio 3:-1
        self.assertGreater(abs(b0), abs(b2))

    def test_ols_survives_collinear_predictors(self):
        """Near-collinear predictors must not silently return all-zero betas."""
        rng = random.Random(2)
        xs, ys = [], []
        for _ in range(200):
            a = rng.gauss(0, 1)
            xs.append([a, 2 * a, rng.gauss(0, 1)])
            ys.append(2 * a + rng.gauss(0, 0.3))
        fit = stats.ols(xs, ys)
        self.assertGreater(fit["r2"], 0.5)
        self.assertTrue(any(abs(b) > 0.01 for b in fit["betas"]))


class TestIndices(unittest.TestCase):
    def test_vector_is_complete_and_in_range(self):
        world, log = run(3, 1000)
        vec = indices.vector(world, log)
        self.assertEqual(set(vec), {"population", "material_output", "inequality",
                                    "drive_diversity", "life_expectancy",
                                    "violence_rate", "mean_restraint",
                                    "norm_compliance"})
        self.assertGreaterEqual(vec["inequality"], 0.0)
        self.assertLessEqual(vec["inequality"], 1.0)
        self.assertGreaterEqual(vec["drive_diversity"], 0.0)
        self.assertLessEqual(vec["drive_diversity"], 1.0)

    def test_unmeasurable_indices_are_declared_not_faked(self):
        for key in ("knowledge_depth", "trust_network", "goal_attainment"):
            self.assertIn(key, indices.UNAVAILABLE)
            self.assertNotIn(key, indices.vector(*run(1, 200)))


class TestViolence(unittest.TestCase):
    def test_restraint_is_inherited_not_reset(self):
        """§5.6 upbringing: a child starts near its parent's *current* restraint,
        not at the archetype baseline."""
        world, log = run(7, 3000)
        by_id = {a.id: a for a in world.agents}
        checked = 0
        for r in log.records:
            if r["kind"] != "birth":
                continue
            child, parent = by_id.get(r["agent"]), by_id.get(r["parent"])
            if child is None or parent is None:
                continue
            self.assertEqual(child.restraint_base, parent.restraint_base)
            checked += 1
        self.assertGreater(checked, 0)

    def test_restraint_stays_in_range(self):
        world, _ = run(7, 3000)
        for a in world.agents:
            self.assertGreaterEqual(a.restraint, 0.0)
            self.assertLessEqual(a.restraint, 1.0)

    def test_violence_can_be_ablated(self):
        _, on = run(11, 3000, {"violence": True})
        _, off = run(11, 3000, {"violence": False})
        viol = lambda lg: sum(1 for r in lg.records
                              if r["kind"] == "action" and r["verb"] in ("steal", "harm"))
        self.assertEqual(viol(off), 0)
        self.assertGreater(viol(on), 0)

    def test_norm_compliance_needs_opportunity(self):
        """The denominator must be agent-ticks where violence was possible.
        Conditioning on all actions makes the observed/unobserved arms
        non-comparable, because proximity produces both targets and witnesses."""
        _, log = run(7, 3000)
        for r in log.records:
            if r["kind"] == "action" and r["verb"] in ("steal", "harm"):
                self.assertGreaterEqual(r.get("opp", 0), 1)


class TestProfiles(unittest.TestCase):
    def test_every_agent_is_profiled(self):
        world, log = run(5, 1000)
        prof = profiles.build(log)
        self.assertEqual(len(prof), len(world.agents))

    def test_policy_window_is_bounded(self):
        """Policy must be measured over the early window only — the whole point
        of the correction. An agent that lived far longer must still have its
        shares computed from at most POLICY_WINDOW actions."""
        _, log = run(5, 2000)
        for a in profiles.build(log).values():
            self.assertLessEqual(a["n_early"], profiles.POLICY_WINDOW)
            if a["n_actions"] > profiles.POLICY_WINDOW:
                self.assertEqual(a["n_early"], profiles.POLICY_WINDOW)

    def test_luck_comes_from_the_deck_not_inference(self):
        _, log = run(5, 2000)
        prof = profiles.build(log)
        logged = 0
        for r in log.records:
            if r["kind"] == "deck":
                logged += len(r.get("valence") or {})
        touched = sum(a["helped"] + a["harmed"] for a in prof.values())
        self.assertEqual(touched, logged)

    def test_attribution_excludes_censored_agents(self):
        _, log = run(5, 2000)
        prof = profiles.build(log)
        res = profiles.attribution(prof)
        eligible = sum(1 for a in prof.values()
                       if not a["censored"] and a["n_early"] >= profiles.POLICY_WINDOW)
        self.assertEqual(res["n"], eligible)


if __name__ == "__main__":
    unittest.main()
