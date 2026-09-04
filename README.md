# Kestrel

Headless simulation of a world of agents with private, heterogeneous goals.
Design: [DESIGN.md](DESIGN.md). Spectator mockup: `mockup/spectator.html`.

**Status: M0 and M2 complete**, plus the §4.5 event deck. No LLM anywhere.
Every agent runs on utility AI over its drive vector — this is the permanent non-LLM
control arm from §7.5, not a placeholder to be replaced. M1 (cognition) has not
started.

M0 asked one question: **does the economy produce non-degenerate outcomes with no
cognition at all?** Answered yes. Population self-regulates (mean 5.9, range 0–15,
sd 4.2 across 20 seeds), action entropy holds at 0.77, deck probabilities swing 7× on
world state, and outcomes diverge widely by seed. Extinction is reachable — 4/20 seeds
at t=2000, 8/20 at t=8000 — and that is left in deliberately; see the gate note below.

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
| `world/deck.py` | Event deck — state-weighted draws, mixed valence, non-starvation death |
| `world/sim.py` | Tick loop, drive dynamics, starvation |
| `world/log.py` | Append-only JSONL event log, SHA-256 digest |
| `world/indices.py` | The measurable slice of the §7.1 index vector |
| `world/profiles.py` | Per-agent behavioral profiles, luck, attribution (§7.2–3) |
| `world/stats.py` | Gini, entropy, Cohen's d, standardized OLS — no dependencies |
| `gate.py` | The M0 gate (retired; kept as the record of what M0 tested) |
| `study.py` | Experiment harness: indices, ablation, attribution, replay |

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

## The event deck

Six events (§4.5), each with a base probability and a weight function of world state,
rolled independently every tick. Sickness follows density, frost follows overharvest,
a good cut follows a healthy commons, findings follow exploration. Every draw logs the
probability it fired at, so the deck is auditable — §7.5's threat #3 is that the deck's
weighting is a designer's theory of causation smuggled in as randomness, and the answer
is to publish it.

Probabilities move substantially with state: over one 2000-tick run, fever ranged
0.0020–0.0140 at the moment of draw, a 7× swing driven by density alone.

Mortality is no longer monotype — 48 starvations, 9 fevers, 3 injuries in that run.
Set `deck: False` in the config for the §7.3 no-deck ablation arm. The deck draws from
its own PRNG stream, so changing deck parameters does not reshuffle the jitter in agent
decisions; ablations stay comparable.

### Ablation: what the deck actually does

I predicted the deck would fix the bistability. It does not. Measured, 10 seeds each:

```
  regen   deck  meanpop  extinct
  0.012  False     0.00   10/10
  0.012   True     0.00   10/10      <- below threshold, deck cannot rescue
  0.016  False     0.10    9/10
  0.016   True     1.60    7/10
  0.020  False     0.00   10/10
  0.020   True     3.40    5/10      <- deck rescues marginal worlds
  0.025  False     5.40    0/10
  0.025   True     5.20    3/10      <- deck kills comfortable ones
```

The deck **converts the cliff into a gradient**, and it cuts both ways: `good_cut` and
`finding` rescue worlds that would have collapsed, while `fever`, `injury` and `storm`
kill worlds that would have held. It does not make worlds safer; it makes outcomes
depend on luck. That is §2.2 working as specified, and it is a different claim from the
one I made before measuring it.

Default `regen_rate` is 0.025 — the last value chosen by a viability sweep rather than
to satisfy a gate criterion. See below for why that distinction ended up mattering.

## Why the gate was retired

The gate earned its keep once, decisively, in run 1: it caught a world where 89% of all
actions were `work` and every seed reached an identical terminal state. It has given
diminishing returns since, and by the end it was failing outcomes the design explicitly
wants reachable — a world going extinct at t=4000, a world stripping its commons, both
named in §7.6 as phenomena worth studying.

Two structural problems, recorded rather than patched:

**1. The criteria are per-seed; the degeneracy they were built to catch is
distributional.** Run 1's real signature was that mean node stock was 44.6% in *all
twenty seeds* — identical. Each seed passed a "stock off floor and ceiling" check on its
own. Per-seed criteria are blind to the exact failure mode they exist to detect. Only
across-seed variance sees it.

**2. Entropy has stopped discriminating.** Measured at t=2000, 20 seeds:

```
                              entropy        stock sd    extinct
default   (regen 0.025)       0.772 ±0.04      0.215      4/20
below cliff (regen 0.012)     0.786 ±0.04      0.198     19/20
glut      (regen 0.120)       0.723 ±0.01      0.119      0/20
```

Entropy reads the same in a living world and in one where 19 of 20 seeds die. It now
measures that agents did varied things before dying. Stock spread barely separates them
either. Population is the only criterion still carrying information.

**The deeper lesson, which cost three parameter changes to learn.** Of the changes made
to the world this milestone, exactly one was a modeling fix: shelter upkeep, because
`work` had no cost and wood had no use, so the world had a single attractor and
randomness was inert. The three `regen_rate` moves (0.012 → 0.025 → 0.030 → 0.025) were
not fixes — each was made to satisfy a criterion. That is tuning the world to fit the
instrument, it pushes the world toward one where collapse cannot happen, and it
invalidates every prior run. Real indices are M2's job; the gate should not have been
asked to stand in for them.

`gate.py` is kept as-is, unmodified, as the record of what M0 actually tested.

**Known limit.** The tool schema still has no verb for violence or theft — see the open
question in §12, which governs what the norm-compliance index can mean.


## M2 — measurement

Five of the ten §7.1 indices are computable from the M0 world. The other five are
listed in `indices.UNAVAILABLE` with the reason, and a test asserts they are never
silently emitted — a proxy would let a result be reported for something the
simulation cannot actually measure. Same discipline for the six behavioral-profile
fields that need M1's social verbs.

```
index                   mean       sd      min      max
population             5.900    4.218     0.00    15.00
material_output      812.811  913.136   157.52  2877.47
inequality             0.175    0.133     0.00     0.39
drive_diversity        0.797    0.399     0.00     1.00
life_expectancy      217.280   17.437   189.00   256.30
```

### Ablation: the deck, 20 paired seeds

```
index                     on       off     delta   cohen d
population             5.900     6.050    -0.150     -0.04
material_output      812.811   302.549   510.262      0.79
inequality             0.175     0.245    -0.070     -0.59
drive_diversity        0.797     0.996    -0.199     -0.71
life_expectancy      217.280   206.240    11.040      0.32
```

The deck has almost no effect on how many agents there are (d = −0.04) and a large
effect on everything else. It nearly triples material output, and it *reduces* both
inequality and drive diversity. The diversity result was not predicted: shared shocks
appear to homogenize the population, plausibly because frost and storms move every
agent's survival drive in the same direction at the same time. Stated as a hypothesis —
testing it needs the per-drive time series, which is M3 work.

### Attribution: what determines how long an agent lives

`lifespan ~ endowment + luck + policy`, standardized betas, 20 seeds × 4000 ticks,
2312 agents lived, n = 1537 after exclusions, R² = 0.295.

```
  luck               0.4573  ##################
  policy             0.3376  #############
  endowment          0.0698  ##
```

Luck outweighs policy, and both dwarf endowment. This is §7.2's decomposition working
as designed: the engine dealt the deck, so each agent's realized luck is *known*, not
inferred — the counterfactual that field social science cannot get.

**The first version of this analysis was wrong, and the way it was wrong is worth
recording.** Policy initially scored 1.60 against luck's 0.24, with R² = 0.70. The
cause was that `specialization` was computed as `1 − entropy(verb counts)` over an
agent's whole life: an agent that dies young takes fewer actions, touches fewer distinct
verbs, and therefore scores as more specialized *because it died*. The predictor was
partly the outcome. Policy is now measured over each agent's first 100 actions only,
agents that did not survive that window are excluded, and R² fell to 0.295 — most of the
original explanatory power was the artifact. `test_policy_window_is_bounded` guards it.
