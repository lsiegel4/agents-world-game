# Kestrel

Headless simulation of a world of agents with private, heterogeneous goals.
Design: [DESIGN.md](DESIGN.md). Spectator mockup: `mockup/spectator.html`.

**Status: M0 walking skeleton.** No LLM anywhere. Every agent runs on utility AI
over its drive vector — this is the permanent non-LLM control arm from §7.5, not
a placeholder to be replaced.

## Run

```
python3 run.py --seed 42 --ticks 500          # one world, summary to stdout
python3 run.py --seed 42 --ticks 500 --out runs/
python3 gate.py --seeds 20 --ticks 500        # the M0 gate
python3 -m unittest discover tests            # determinism + invariants
```

No dependencies. Python 3.9+.

## What exists

| Module | Does |
|---|---|
| `world/state.py` | World, Agent, ResourceNode; state-dependent regeneration |
| `world/genesis.py` | M0 world generation stub (§4.1's nine passes arrive in M3) |
| `world/brain.py` | Tier 0 utility AI — scores candidates from drives, no model call |
| `world/actions.py` | `move` `work` `eat` `repair` (of the 12 in §5.5) |
| `world/sim.py` | Tick loop, drive dynamics, starvation |
| `world/log.py` | Append-only JSONL event log, SHA-256 digest |
| `world/indices.py` | Population only; the §7.1 vector arrives in M2 |
| `gate.py` | The M0 gate |

## Mechanics

Two non-fungible resources in different places, both needed. Food answers hunger.
Wood repairs shelter, which decays every tick; an unsheltered agent burns food up
to 2.4× faster. That competition is what stops the economy collapsing into
"stand on one tile and harvest forever" — see the gate history below.

Drives (`survival`, `mastery`, `curiosity`) are floats the engine mutates: sustained
hunger pulls survival up, working raises mastery, moving raises curiosity, and
everything relaxes toward the archetype baseline when pressure is off. Agents never
edit their own drives.

## The gate

M0 exists to answer one question before any inference is paid for: **does the
economy produce non-degenerate outcomes with no cognition at all?**

Criteria, fixed before tuning: population neither extinct nor unbounded; normalized
action entropy ≥ 0.35; mean node stock settles off both floor and ceiling.

**Run 1 — failed 20/20, `monotony`.** 89% of all actions were `work`. Every seed
converged to the *same* terminal state — five food nodes stripped to 0.2% at maximum
degradation, everything else untouched — because `work` had no cost and no satiation
ceiling, and wood had no use. Randomness could not perturb the single attractor.

**Run 2 — 18/20 pass after adding shelter upkeep and a carrying cap.** Entropy rose
from ~0.29 to 0.78–0.91, and outcomes now diverge by seed (final population 0–4,
mean node stock 67–99%). Survivors are the agents that spawned near both a food and a
wood node; the deaths are exposure spirals, where travel to a distant node costs
shelter, which accelerates hunger, which forces more travel. Endowment and spatial
luck drive the outcome spread — the §2.2 dynamic, arriving unprompted.

**Run 3 — reproduction added, and it made things strictly worse: 20/20 extinct.**
Without births, population could only fall, so the survival criterion was unsatisfiable
at any real horizon (extinct 13/20 by t=2000). Adding reproduction — children inherit
the parent's *current* drive vector plus noise, so generational drift is measurable —
collapsed every world instead. Two causes, found in that order:

1. **Synchronized cohorts.** Every founder started at age 0 and crossed the minimum
   breeding age on the same tick, so births arrived in pulses of 3–5, then again one
   cooldown later. Seed 3 stepped 5 → 17 agents and stripped its nodes. Founders now
   start at staggered ages. This was not the main cause.
2. **A commons ratchet.** Degradation rises 0.05 per harvest on a depleted node and
   recovers at 0.005 per tick. Under the extra mouths, nodes crossed into permanent
   degradation and the food supply never came back.

**Run 4 — GATE PASSED, 20/20 at 2000 ticks**, after a sweep over regeneration rate and
node count found the ratchet is a **cliff, not a gradient**:

```
  regen  food_n  meanpop   max  extinct
  0.012       6     0.00     0   10/10     <- the old default
  0.025       6     5.40    12    0/10
  0.045      10    16.80    30    0/10
```

The economy is bistable. Below a regeneration threshold every world dies; above it every
world lives. The default sat just under the cliff. At 0.025 the population is stable and
bounded across horizons — mean 6.05 at t=2000, 7.80 at t=4000, 7.10 at t=8000, range
2–18, zero extinctions — and outcomes vary widely by seed: entropy 0.60–0.88, terminal
node stock 15–78%, degradation 0.18–0.68.

**Known limit.** Starvation is currently the only cause of death, which is precisely why
the system is bistable: population is a pure feedback loop on the commons with nothing to
dampen it. The event deck (§4.5) carries sickness, disaster and injury as
resource-independent mortality and lands in M1. Note also that the tool schema has no
verb for violence or theft — see the open question added to §12, which affects what the
norm-compliance index can mean.
