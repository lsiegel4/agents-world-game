"""Tests for the §4.1 nine-pass generator.

All offline: the generator is template-driven precisely so a world can be built,
replayed and tested without a model or a key.
"""

import random
import unittest

from world import history as history_pass
from world import terrain as terrain_pass
from world.sim import DEFAULT_CONFIG, run
from world.worldgen import make_world


def _world(seed=42, **overrides):
    cfg = dict(DEFAULT_CONFIG)
    cfg["worldgen"] = "generated"
    cfg.update(overrides)
    return make_world(seed, cfg)


class TestTerrain(unittest.TestCase):
    def test_terrain_is_deterministic(self):
        a = terrain_pass.generate_terrain(30, 20, 7)
        b = terrain_pass.generate_terrain(30, 20, 7)
        self.assertEqual(a, b)
        self.assertNotEqual(a, terrain_pass.generate_terrain(30, 20, 8))

    def test_every_biome_appears(self):
        grid = terrain_pass.generate_terrain(40, 26, 7)
        present = {cell for row in grid for cell in row}
        self.assertEqual(present, set(terrain_pass.BIOMES))

    def test_settlement_sites_are_habitable_and_spaced(self):
        grid = terrain_pass.generate_terrain(40, 26, 7)
        sites = terrain_pass.settlement_sites(grid, 4, spacing=5)
        self.assertTrue(sites)
        for _, x, y in sites:
            self.assertNotIn(grid[y][x], (terrain_pass.WATER, terrain_pass.STONE))
        for i, (_, x1, y1) in enumerate(sites):
            for _, x2, y2 in sites[i + 1:]:
                self.assertGreaterEqual(max(abs(x1 - x2), abs(y1 - y2)), 5)

    def test_ruins_avoid_live_settlements(self):
        grid = terrain_pass.generate_terrain(40, 26, 7)
        sites = terrain_pass.settlement_sites(grid, 4)
        occupied = {(x, y) for _, x, y in sites}
        for ruin in terrain_pass.ruins(grid, sites, random.Random(1), 3):
            self.assertNotIn((ruin["x"], ruin["y"]), occupied)


class TestHistory(unittest.TestCase):
    def _history(self, seed):
        grid = terrain_pass.generate_terrain(40, 26, seed)
        sites = terrain_pass.settlement_sites(grid, 4)
        return history_pass.generate_history(sites, random.Random(seed))

    def test_eras_follow_plausible_succession(self):
        """A recovery needs something to recover from. Without the succession
        table the generator emits 'the Founding, the Recovery' — grammatical
        and nonsense."""
        for seed in range(8):
            hist = self._history(seed)
            kinds = [e["kind"] for e in hist["eras"]]
            self.assertEqual(kinds[0], "founding")
            for before, after in zip(kinds, kinds[1:]):
                self.assertIn(after, history_pass.SUCCESSION[before])

    def test_era_names_are_unique_within_a_world(self):
        for seed in range(8):
            names = [e["name"] for e in self._history(seed)["eras"]]
            self.assertEqual(len(names), len(set(names)))

    def test_worlds_are_diverse_across_seeds(self):
        """Two worlds should not read the same. Fixed name lists and fixed era
        counts are how a procedural generator ends up feeling identical."""
        names, places, lengths = set(), set(), set()
        for seed in range(10):
            hist = self._history(seed)
            names.update(e["name"] for e in hist["eras"])
            places.update(hist["places"])
            lengths.add(len(hist["eras"]))
        self.assertGreater(len(names), 20)
        self.assertGreater(len(places), 15)
        self.assertGreater(len(lengths), 1)

    def test_facts_carry_visibility_and_some_are_lost(self):
        seen = set()
        for seed in range(10):
            for fact in self._history(seed)["facts"]:
                self.assertIn(fact["visibility"], history_pass.VISIBILITIES)
                seen.add(fact["visibility"])
        self.assertIn("lost", seen)

    def test_knowable_hides_what_an_outsider_could_not_know(self):
        hist = self._history(3)
        knowable = history_pass.knowable(hist)
        self.assertLess(len(knowable), len(hist["facts"]))
        for fact in knowable:
            self.assertEqual(fact["visibility"], "common")

    def test_myth_contradicts_history(self):
        """§4.1: pass 6 deliberately distorts pass 4, and the gap is measurable."""
        hist = self._history(3)
        myths = history_pass.generate_myth(hist, random.Random(3))
        self.assertTrue(myths)
        claims = {f["claim"] for f in hist["facts"]}
        for myth in myths:
            self.assertIn(myth["about"], claims)   # points at something real
            self.assertFalse(myth["true"])          # and bends it
        self.assertGreater(history_pass.myth_divergence(hist, myths), 0.0)


class TestAssembly(unittest.TestCase):
    def test_all_nine_passes_produce_output(self):
        lore = _world().lore
        for key in ("sites", "ruins", "history", "culture", "myths",
                    "institutions", "material"):
            self.assertTrue(lore[key], key)

    def test_inequality_parameter_widens_site_shares(self):
        """The parameter governs how unevenly the *sites* are endowed (§4.4).

        Asserting on final agent endowments instead is a weak test: archetype
        endowment (§6.1) multiplies on top, and with a handful of agents the two
        can cancel — a rich archetype landing on a poor site and vice versa.
        Test the mechanism the parameter actually controls.
        """
        def spread(level):
            shares = _world(inequality=level, agents=24, sites=8) \
                .lore["material"]["site_shares"]
            return max(shares) - min(shares)
        self.assertAlmostEqual(spread(0.0), 0.0, places=6)
        self.assertGreater(spread(0.9), 0.05)
        self.assertGreater(spread(0.9), spread(0.4))

    def test_archetypes_alone_make_starts_unequal(self):
        level = [a.inventory["food"] for a in _world(inequality=0.0).agents]
        self.assertGreater(len(set(level)), 1)

    def test_generation_is_deterministic(self):
        a, b = _world(), _world()
        self.assertEqual([n.id for n in a.nodes], [n.id for n in b.nodes])
        self.assertEqual(a.lore["history"]["eras"], b.lore["history"]["eras"])

    def test_generated_worlds_remain_viable(self):
        """Biome quality shapes where resources are, not how much exists. Left
        unnormalised it shrinks the whole economy and generated worlds starve
        where flat ones survive."""
        alive = [len(run(s, 1500, {"worldgen": "generated"})[0].living_agents())
                 for s in range(6)]
        self.assertEqual(sum(1 for a in alive if a == 0), 0)

    def test_flat_generator_is_still_the_default(self):
        """Every result recorded before M3 was against genesis.py. Changing the
        default would silently invalidate all of them."""
        self.assertEqual(DEFAULT_CONFIG["worldgen"], "flat")


if __name__ == "__main__":
    unittest.main()
