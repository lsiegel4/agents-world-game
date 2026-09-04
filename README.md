# Kestrel

Headless simulation of a world of agents with private, heterogeneous goals.
Design: [DESIGN.md](DESIGN.md). Spectator mockup: `mockup/spectator.html`.

**Status: M0 and M2 complete**, plus the §4.5 event deck, the T0 violence baseline, and
the M1 cognition layer (built and tested; not yet run against a live model).
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
| `world/memory.py` | Episodic memory: salience, decay, ranked recall (§5.4) |
| `world/prompt.py` | State -> prompt rendering and the API tool schema (§5.2) |
| `world/cognition.py` | Stakes scoring, tier routing, model-driven action choice (§5.7) |
| `world/llm.py` | Model client: record/replay cache, cost accounting, spend guard |
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

## Violence at Tier 0

`steal` and `harm` are implemented in the utility AI, with no model calls, so that when
LLM agents arrive their violence is measurable *against* something rather than merely
narratable. `coerce` needs language and waits for M1.

**There is no aggression drive.** The harm verbs draw utility from drives that already
exist — `survival` under hunger, plus accumulated grudge — and one trait, `restraint`,
scales it down. Restraint comes from the three places it comes from in people:

| Source | Mechanism |
|---|---|
| Nature | archetype baseline plus per-agent noise at world creation |
| Upbringing | children inherit the parent's *current* restraint plus noise, not the baseline |
| Environment | eroded by sustained hunger, victimization, and habituation; recovers toward baseline during stability |

Inhibition scales with restraint **and** with the number of bystanders, multiplicatively.
An agent with high restraint is strongly deterred by being seen; an agent whose restraint
has been ground away barely registers it. That asymmetry is what produces a real
observed/unobserved differential instead of one asserted by the metric.

### Norm compliance, 20 seeds x 8000 ticks pooled

```
  opportunity agent-ticks   unobserved   174404   observed   437109
  defections                unobserved     3132   observed      448
  defection rate            unobserved  0.01796   observed  0.00102

  norm compliance (unobs - obs): +0.01693
```

Agents defect **17.6x more often when nobody is watching**. Also: 189 killings,
retaliation accounts for ~50% of all violence, and perpetrators average 0.34 restraint at
the moment of the act against a population mean of 0.61 at birth. Violence is committed
by the disinhibited, and disinhibition is mostly made rather than born.

**Two construction bugs found on the way, both of which produced confident wrong
numbers.** Recorded because each is the kind that does not announce itself:

1. **The denominator was all actions.** Violence needs a reachable target, and proximity
   is also what produces witnesses, so conditioning on every action made the two arms
   non-comparable — norm compliance came out *negative*, implying agents preferred to
   defect in public. The denominator has to be agent-ticks where violence was possible.
2. **The victim was counted as a witness.** Any target within reach (radius 1) is
   necessarily inside witness range (radius 2), so having someone to rob guaranteed a
   "witness" and the unobserved arm was empty by construction — 0 unobserved
   opportunities across 20 seeds. The prospective victim is discounted now.

A third, smaller one: witness and opportunity counts were snapshotted at tick start while
the decision happened mid-tick, after other agents had moved. Numerator and denominator
were measuring different worlds. Both are computed live per agent now.

### Ablation: violence on vs off, 20 paired seeds

```
index                     on       off     delta   cohen d
population             5.900     7.950    -2.050     -0.42
inequality             0.166     0.231    -0.065     -0.50
drive_diversity        0.748     0.896    -0.148     -0.40
life_expectancy      218.950   229.040   -10.090     -0.50
violence_rate          4.943     0.000     4.943      1.87
mean_restraint         0.381     0.433    -0.052     -0.26
```

Adding defection costs population, lifespan and drive diversity — and **lowers
inequality** (d = -0.50). Theft is redistributive: it moves food from agents who have
accumulated it to agents who have none. Whether that is a finding about worlds or an
artifact of a world with only two resources is exactly the kind of question M1 exists to
put pressure on.

*Not* reported as a finding: `material_output` rises with violence on (d = 0.39). It is
measured per capita, and violence lowers population, so the ratio moves without the
numerator doing anything interesting. Flagged rather than quietly included.

**Known limit.** The world still has no verb for organized violence, for deception beyond
speech, or for property rights violable in law rather than in fact — see §7.5 threat #2,
now partly rather than fully addressed.


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


## M1 — cognition

Built and fully tested offline. **Not yet run against a live model**, so nothing below
is a result about LLM agents — it is a description of the machinery and its costs.

### Running it

```
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python anthropic
export ANTHROPIC_API_KEY=sk-ant-...        # separate from a Claude Pro/Max plan

.venv/bin/python study.py cognition --seeds 5 --ticks 500              # replay, free
.venv/bin/python study.py cognition --seeds 5 --ticks 500 \
    --mode record --max-usd 2.00                                       # spends money
```

Default mode is `replay`: cache only, no network, no cost. Going live needs an explicit
`--mode` and carries a `--max-usd` ceiling that raises `SpendLimitExceeded` mid-run
rather than continuing. The 33-test suite passes on an interpreter with no SDK installed
at all, which is the proof that the replay path is genuinely offline.

### Design

- **The prompt is rendered from state every call** (§5.2). Nothing asks the model to
  remember who it is, and the model never edits its own drives — it picks an action and
  the engine mutates state.
- **The engine's verb schema is the API tool schema**, with `strict: true` and
  `additionalProperties: false`. That is §2.5 made literal: no text anywhere — another
  agent's speech, a user's brief, an object found in the world — can widen what an agent
  is able to do, because capability lives in the schema and the engine owns it.
- **The character brief is data, not instruction.** It never reaches the system turn; it
  arrives in the user turn inside `<character_brief>` tags, labelled as description that
  may be wrong. A test asserts a brief reading "Ignore all rules." cannot reach the
  system prompt.
- **No private state of other agents leaks.** An agent sees position, whether someone is
  carrying, and its own grudges — never another agent's drives, goal, hunger, or exact
  holdings. Tested.
- **Verb set is identical to Tier 0** in this first slice, so a T0-vs-T1 comparison
  changes cognition and nothing else. The social verbs are the next slice; adding them
  simultaneously would make the two variables inseparable.

### Replay is what makes this reproducible

Every request is hashed and its response stored against that hash. §2.7 requires a run to
be reproducible from `(seed, config, code)`, which a live model breaks; the cache repairs
it. A recorded run replays exactly, forever, without the model still existing. On a cache
miss the default is to **raise**, not to quietly fall back to the utility AI — a silent
fallback would contaminate the comparison, so `--on-miss tier0` has to be asked for and
the report warns when any fired.

### Escalation is the whole cost model

```
  decisions 37799   escalations attempted 4243
  escalation rate: 11.23%
```

The first version of the stakes function escalated on **63%** of ticks, which violates
§5.7's "most ticks are not model calls" and would run roughly $1,400/month for a
200-agent shared world. The cause was that any nearby agent added a flat +0.30, and
agents cluster at resource nodes constantly. Proximity on its own is not a decision; it
matters when something is at stake — an unsettled grudge, or a hungry agent standing next
to someone carrying food. Reshaped that way, escalation sits near 11% and the same world
costs about $220/month.

A related accounting bug is worth recording: fallbacks were counted as Tier 0 decisions,
so the report showed **0% escalation while 228 escalations had fired**. A fallback still
rendered a prompt and still would have cost money on a live run. Attempts are counted
before the call now.
