# Kestrel

Headless simulation of a world of agents with private, heterogeneous goals.
Design: [DESIGN.md](DESIGN.md). Spectator mockup: `mockup/spectator.html`.

**Status: M0-M4 complete.** All findings re-measured at 120 founders on 2026-09-04; three were retracted. Read that section before trusting any number elsewhere in this file. One live recording run done for $0.41. **All ten
§7.1 indices and all ten §7.3 behavioural-profile fields now compute** — both
`UNAVAILABLE` maps are empty.
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
| `world/knowledge.py` | Technique graph, discovery, transmission (§7.1 depth/breadth) |
| `world/goals.py` | Private goals: generation, evaluation, revision, inheritance (§5.3) |
| `world/terrain.py` | §4.1 passes 1-3: terrain, deep time, settlement siting |
| `world/history.py` | §4.1 passes 4-6: history, culture, myth |
| `world/worldgen.py` | §4.1 passes 7-9 and assembly of all nine |
| `world/memory.py` | Episodic memory: salience, decay, ranked recall (§5.4) |
| `world/prompt.py` | State -> prompt rendering and the API tool schema (§5.2) |
| `world/cognition.py` | Stakes scoring, tier routing, model-driven action choice (§5.8) |
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
§5.8's "most ticks are not model calls" and would run roughly $1,400/month for a
200-agent shared world. The cause was that any nearby agent added a flat +0.30, and
agents cluster at resource nodes constantly. Proximity on its own is not a decision; it
matters when something is at stake — an unsettled grudge, or a hungry agent standing next
to someone carrying food. Reshaped that way, escalation sits near 11% and the same world
costs about $220/month.

A related accounting bug is worth recording: fallbacks were counted as Tier 0 decisions,
so the report showed **0% escalation while 228 escalations had fired**. A fallback still
rendered a prompt and still would have cost money on a live run. Attempts are counted
before the call now.


## M1 slice 2 — the social verbs

`give`, `teach`, `form_bond`, `speak`, `leave_message`, `coerce` are in, at Tier 0 and in
the LLM tool schema. Fourteen verbs total. This is what closed most of `UNAVAILABLE`:
`knowledge_depth`, `knowledge_breadth`, `institution_density` and `reciprocity` are all
measured now, and the behavioural profile carries `giving_rate`, `teaching_rate`,
`information_sharing_rate` and `coalition_participation`.

**Knowledge is a shallow dependency graph** (`world/knowledge.py`): `gleaning` and
`coppicing` at depth 1, `drying` and `joinery` at depth 2, `kiln` at depth 3 needing both.
Techniques raise harvest yield, meal value, and repair value. Discovery is rare and
curiosity-weighted; transmission is `teach`. Depth 3 is deliberately out of reach for a
single agent working alone in one lifetime, so a world that gets there got there by
teaching.

### The `teach` ablation — 20 seeds, 2000 ticks

The study §11 named as the first one, finally runnable:

```
             population   depth   breadth   total harvested   extinct
teach ON          11.40    2.85      8.38              5378      1/20
teach OFF          6.05    1.25      1.10              4294      3/20
```

Teaching nearly doubles population, triples knowledge depth, and cuts extinction. It is
the strongest single lever measured so far — a first answer to design question 1.

**The per-capita trap, caught a second time.** Output *per capita* reads 385 with teaching
and 738 without, which says teaching halves productivity. It does not. Total extraction
rises 25% (5378 vs 4294) while population rises 88%, so the per-capita ratio falls because
the denominator grew. `material_output_total` is now reported alongside, and the
docstring on `material_output` carries this case as the warning.

### Reciprocity could not bootstrap

`give` fired **zero** times in 2000 ticks and 170 of 173 bond offers were refused. Both
utilities were scored on existing standing — but standing is *created* by giving. You
needed regard to be generous, and generosity was what earned regard, so neither ever
started. Both now have a floor independent of standing, and a test guards it. After the
fix: institutions 1.05 per world, reciprocity 0.24, and `give` fires.

### What predicts a long life, with social strategies in the model

12 seeds x 3000 ticks, 1056 agents, R2 = 0.29:

```
  policy             0.5743  ######################
  luck               0.4416  #################
  endowment          0.1150  ####

  coalition_participation  -0.2187   bonding correlates with dying sooner
  move_share               -0.1174
  giving_rate              -0.0965   generosity is individually costly
  teaching_rate            +0.0735   teaching is individually cheap and pays
```

Policy overtakes luck once social strategies enter the model, which is what you would
hope. The signs are the interesting part: **teaching helps the teacher and the world;
giving and bonding cost the individual while helping the world.** That is the non-zero-sum
structure §2.1 asks for, appearing without being designed in.

Read the coalition figure cautiously — bonding requires proximity, and proximity is also
where violence happens, so it may partly proxy for exposure rather than cause harm.

### Two more unbounded-string bugs

Agent names compounded a patronymic every generation —
`Bastianssonssonssonssonssonsson` — the same class of bug as the child ids, and it costs
prompt tokens once rendered. Fixed. And `oldest agent: 1239 ticks` surfaced a real gap:
§4.3 says agents age and die, but **no mortality is attached to age at all**. A third
generation sharing the world with its founders is not a succession, which matters for the
§7.6 lock-in test. Logged in §12 next to the archetype work.


## M1 slice 3 — private goals

Every agent carries a private goal drawn from a generator weighted by its current drives.
Eight kinds — `accumulate`, `master`, `teach`, `bond`, `lineage`, `outlive`, `provide`,
`avenge`. Goals are **structured, not free text**, so `goal_attainment` is computed from
engine state with no model in the loop (§7.5 threat #5).

Goals are private in the strong sense: an agent's goal is rendered only into its own
prompt, never into anyone else's observation. A test plants a token in one agent's goal
and asserts it cannot appear in another's prompt.

**Revision** happens at the three §5.3 thresholds — achieved, proven impossible, or a
life event — and the old goal is kept in `goal_history`. Nothing asks the agent to change
its mind: the engine restates the goal and the next prompt renders from the new state.
Measured across 12 seeds x 3000 ticks, agents that revise at all hold **6.13 goals over a
lifetime**, and 42.6% of all goals ever held were met.

**Inheritance** gives children the *shape* of the parent's goal, not its progress —
§5.3's goal-acquisition case, and what §7.6's lock-in test will eventually read.

Goals bias behaviour through a modest `GOAL_PULL` on the matching verb. Deliberately
modest: a goal should bias a life, not override hunger.

### Two measurement traps in one slice

**Attainment measured on a snapshot reads ~0 in a world where goals are met constantly.**
A goal is revised the instant it is reached, so almost nobody is ever caught at 100%. The
first implementation reported `goal_attainment 0.0` alongside `goal_progress 0.33`; it was
measuring the revision rule, not attainment. It now reads the lifetime record: 0.426.

**Adding a PRNG draw to the shared stream silently re-randomises every world.** Goal
generation initially drew from the decision RNG, so every seed produced a different world
and extinction appeared to rise from 1/20 to 4/20. Nothing had got worse — the comparison
was simply not paired. Goals now have their own stream (`seed ^ 0x6041`), matching the
deck's. Properly paired, goals *improved* viability: **mean population 9.80 -> 13.50,
extinctions 1/20 -> 0/20**, via the reinforcement from meeting one.

That is the second time separate PRNG streams have earned their keep, and the rule is
worth stating plainly: **any new source of randomness gets its own stream, or every
prior result silently becomes incomparable.**

### Memory consolidation closes M1

Repeated episodes fold into semantic beliefs (§5.4): four wrongs from the same person
stop being four memories and become a belief about that person. It is **rule-based, not
model-driven** — this runs in the Tier 0 control arm, and a control arm that needs an API
key is not a control. The LLM version layers on top and gets compared against it rather
than substituted for it.

Consolidation is lossy on purpose. Beliefs outlive the episodes behind them, which is how
a grudge survives forgetting the incidents that caused it — asserted by a test.


## M3 — world generation

All nine §4.1 passes, **template-driven and offline**. §4.1 calls for a model at passes
4-6 and a model writes better prose, but a generator that *requires* one cannot be
replayed later, cannot run in the Tier 0 control arm, and cannot be tested without a key.
The model enriches this; it does not supply it.

```
python3 run.py --seed 42 --ticks 2000        # flat world (M0 placement, still default)
```

Set `worldgen: "generated"` in the config for the nine-pass world. **The flat generator
remains the default on purpose** — every result recorded before M3 was measured against
`genesis.py`, and changing the default would silently invalidate all of them. A test
asserts it.

### The two rules that make it worth building

**History is not uniformly known.** Every fact carries a visibility — common, local,
specialist, or lost. Agents are told common knowledge and the local knowledge of where
they are; specialist and lost facts are withheld, which is what makes recovering them
worth doing.

**Myth contradicts history.** Pass 6 points at real facts from pass 4 and bends them, via
ten distortion modes — `blames`, `inflates`, `erases`, `inverts`, `predates`, `merges`
and others. Myths are rendered into prompts *flat beside the history, unlabelled*,
because an agent has no way to tell which is which. `myth_divergence` measures the gap.

### Diversity

Two worlds should not read the same. Across ten seeds: **29+ distinct era names, 24+
place names, era counts varying 5-8, fact counts 17-27.**

- 13 era kinds with a **succession table** — a recovery needs something to recover from.
  Without it the generator emitted "the Founding, the Recovery": grammatical, and nonsense.
- 5 candidate names per kind, chosen for what an era felt like rather than how a
  chronicler would classify it: *the Quiet Years*, *the Years of Knives*, *the Shut
  Doors*, *the Winter That Stayed*.
- 4-5 event templates per kind, a random subset used per era, so eras differ in how much
  record they leave behind.
- Place names built combinatorially from 18 prefixes x 14 suffixes — 252 possibilities,
  so a shared name between worlds is a coincidence rather than the norm.

A representative arc: *the Founding -> the Quarrel -> the Scattering -> the Relearning ->
the Green Decades -> the Coming of Strangers -> the Overflowing -> the Reckoning.*

### The regression this introduced, and the fix

Generated worlds initially ran **mean population 6.83 with 4/12 extinct**, against the
flat generator's 12.75 and 0/12. Cause: node capacity was multiplied by biome quality, and
since marsh food scores 0.7 and wood-biome food 0.5, the generated world simply contained
less food than a flat one. Biome quality should decide *where* resources sit and how they
differ from each other, not how much exists in total. Normalised against the mean quality
of chosen sites, generated worlds now run **14.75 with 0/12 extinct**, and node capacities
still vary 24-48 — the heterogeneity §4.4 asks for, without the silent shrinkage.


## Re-measurement at scale (2026-09-04) — three findings retracted

Every social result in the sections above was measured with **5 founders**. §12 puts the
design's target population at 100-300. Re-running every study at **120 founders, 20 seeds
x 2000 ticks** took 30 minutes and cost nothing, and it invalidated three conclusions.

The scale condition is `study.SCALE`; pass `--scale` to any `study.py` command.

### Retracted

**1. "Institutions only exist at scale."** Drawn from a single-seed comparison. Across 20
seeds, small worlds average 2.0 institutions and 0.371 reciprocity — not zero. Per capita
the density is **0.146 at scale against 0.148 small**: institutions scale proportionally
with population and do not emerge from density. The one seed I looked at happened to have
none.

**2. "Theft is redistributive."** At 5 founders, inequality read 0.166 with violence on
against 0.231 off (d = -0.50), and I described a mechanism: theft moving food from those
who had accumulated it to those with none. At 120 founders the effect is **0.001,
d = 0.02**. The original was an artifact of small-N Gini — with 13 agents a handful of
thefts shifts a real share of total holdings; with 60 the same per-capita rate is noise.
The life-expectancy effect (-0.50) vanished the same way (0.02).

At scale, violence is uniformly costly: goal attainment d = -1.66, total output -1.12,
knowledge breadth -0.74, population -0.53, institutions -0.41. No upside anywhere.

**3. "Policy overtakes luck."** The attribution decomposition reverses at scale
(n = 6,482 agents, R2 = 0.37):

```
              at scale    5 founders
  luck          0.5343         0.442
  policy        0.4873         0.574
  endowment     0.1728         0.115
```

What held: `giving_rate` and `coalition_participation` still carry negative signs and
`teaching_rate` positive — generosity and bonding cost the individual, teaching pays.

### Strengthened

**Teaching is the strongest lever in the project, by a wide margin**, and at scale it
turns out to drive far more than knowledge:

```
  teach ablation                   on        off     cohen d
  goal_attainment               0.380      0.142        7.76
  knowledge_depth               3.000      2.000        4.47
  knowledge_breadth            39.970      4.565        3.45
  institution_density           8.900      1.350        2.32
  reciprocity                   0.314      0.179        1.31
  population                   60.750     42.850        1.17
  material_output_total     15305.893  13872.974        1.04
  life_expectancy             205.880    211.150       -0.45
```

The chain is only visible at scale: teaching creates favours owed, favours make bonds
acceptable, bonds are institutions. Goal attainment nearly triples — the largest effect
size measured anywhere in this project.

And teaching slightly *shortens* mean life while improving everything collective. Not a
contradiction with individual teachers living longer: it supports 18 more people on
similar ground, so the average falls. A composition effect, not a reversal.

### Scale changes the world's character

```
  index                      at scale  5 founders
  population                   60.750     13.500
  knowledge_breadth            39.970     10.570
  material_output_total     15305.893   2741.310
  life_expectancy             205.880    223.320
  violence_rate                 7.527      5.540
  inequality                    0.303      0.254
  goal_attainment               0.380      0.426
  reciprocity                   0.314      0.371
```

More people, far more produced, and **worse lives**: shorter, more violent, more unequal,
fewer goals met. That is §7.1's tradeoff surface in real numbers, and the reason the
design refuses to collapse the vector into one score.

The deck shows the same shape from the other direction — at scale it *raises* population
(+0.38) and output (+1.48) while cutting life expectancy by 19.5 ticks (-1.78) and
reciprocity by a full standard deviation (-1.06). Disruption churns a population: more
born, more dead, more produced, each life shorter and the favour economy repeatedly reset
because favours die with the people who owed them.

### One index is broken

`knowledge_depth` reads **3.000 with zero variance** in both conditions, because the
technique graph stops at depth 3. It is pinned at its ceiling and cannot discriminate
between worlds. Either the graph needs more depth or the index needs retiring — as it
stands the `teach` ablation's depth result was measuring headroom that barely existed.


## Two index fixes (2026-09-04)

**`knowledge_depth` was pinned at its ceiling.** The technique graph stopped at depth 3,
so the index read 3.000 with zero variance in every condition while being one of the
measures behind the project's headline finding. The graph now runs to depth 6 —
`cooperage` (carry more), `stewardship` (harvesting wears a node down less; the only
technique whose benefit lands on the commons), `irrigation` — and the index discriminates
properly: **5.83 with teaching against 2.17 without.**

**Scale is now the default for every study.** `study.py` runs the 120-founder condition
unless `--small` is passed, and every study prints its population in the header. Three
findings were retracted because 5 founders was the path of least resistance; leaving the
artifact-producing configuration as the default guarantees a repeat.

### What the fixes exposed

Extending the technique graph broke two goal tests, and both were real:

**Goals had collapsed to a single kind.** Every agent alive at t=1500 held `outlive` —
§2.1's global objective arriving by the back door. Fast goals complete and cycle; `outlive`
takes 600+ ticks, so survivors drained into it and never left. §5.3 names three revision
triggers — achieved, impossible, life event — and only two were implemented. Stale goals
are now abandoned.

**Progress was measured from zero instead of from where the agent started.** `outlive`
sets its threshold to `age + 600` and scored progress as `age / threshold`, so an agent
aged 1000 began at 0.62 progress and could never go stale. Progress is now measured from
the goal's starting baseline for every kind.

`outlive` still dominates, and that part is a design issue rather than a bug — a goal that
completes by doing nothing will always win in a population that survives. Logged in §12
with the goals-against-lore work.

## Archetypes (2026-09-04)

§6.1 named six from the start and none of them existed — the archetype was a string on the
agent that nothing read. Every agent sampled one drive baseline, which had two
consequences: `drive_diversity` was meaningless, and §7.6's value lock-in test could not
run, because comparing "the founder cohort" to a later generation requires the founders to
be a cohort rather than one distribution sampled twice.

`world/archetypes.py` gives each of artisan, broker, scholar, steward, wanderer and zealot
its own drive vector, restraint baseline, endowment multiplier, verb affinities, and a
locked scaffold for the LLM arm. Founders are assigned round-robin so a cohort contains
every kind; children inherit with 15% drift, so lineages are neither sealed nor erased.

**Drives relax toward the agent's own archetype baseline, not a global one.** Relaxing
everyone toward one baseline erases archetypes within a few hundred ticks — the
differences would exist at creation and be gone before anything measured them, which is
indistinguishable from not having them.

### A third broken index

`drive_diversity` used normalised entropy across each drive's values. Normalised entropy
over N similar positive numbers is ~1 whatever the spread, so the index read **0.997 with
sd 0.001 across every condition ever run** — including after six genuinely different
archetypes were introduced. It was measuring the number of agents, not their variety.

Rewritten as mean pairwise distance between drive vectors and validated against an
all-scholar control: **0.162 for six archetypes against 0.087 for one, a 1.87x separation
where the old index gave 1.00x.**

That is three indices found broken in one day — `knowledge_depth` at a ceiling,
`drive_diversity` measuring population size, and `norm_compliance` earlier in the session
with an empty denominator. Each was reported in results before anyone noticed. The pattern
is worth naming: **an index that never varies is not a stable finding, it is a broken
instrument**, and sd across conditions is the cheapest test for it.

### Open

In one seed, scholars were 82 of 108 survivors — archetype selection may be strong enough
to collapse diversity over time. Not measured across seeds yet, and worth doing before
archetypes are called finished. The scaffolds are written but not yet wired into
`prompt.py`, so the LLM arm does not see them.


## Archetype selection, and what it revealed (2026-09-05)

Archetypes were built to create pluralism. Measured across 6 seeds and 720 founders, they
create a **winner** instead: scholars go from 17% of founders to 62% of survivors.

### Two wrong diagnoses before the right one

**Not violence avoidance.** The survival order matched the harm affinities exactly, so the
first theory was that declining violence pays. A vigilance mechanic was built on it —
being robbed or witnessing a robbery makes an agent watchful, and a watchful target is
harder to rob, so predation should stop paying once common. It engaged at a mean vigilance
of **0.022**: violence is already too rare in the baseline for anyone to become watchful.
The mechanic is kept — it is sound on its own terms and should matter in violent worlds —
but it did not explain the result.

**Not production efficiency.** Zealots are the *most* productive archetype at 70% of
actions, and hold 3% of survivors. Scholars spend 42% of their turns walking and win.

**It is technique accumulation.** Scholars hold 5.45 techniques to a zealot's 2.07 and
have twice the children. Techniques multiply yield, nutrition, carry and repair, so a
scholar needs fewer work actions and each one pays more.

The reason it never self-corrects: **techniques are not inherited.** Every generation
relearns from scratch, and learning required someone to actively teach you — so the
archetype best at acquisition wins permanently, no matter how much the world already knows.

### Ambient learning

A technique everyone around you uses is not taught, it is absorbed. Prevalence is squared,
so only genuinely common things transmit passively: a rare craft still needs a teacher, and
the scholar's edge is real while knowledge is scarce and fades as it saturates.

Effect: scholars 62% -> 55%, and every archetype gained techniques. Real, and modest.

### Does the world change who wins?

Six conditions, 4 seeds each:

```
condition          arti  brok  scho  stew  wand  zeal   pop
baseline            24%    3%   58%   10%    2%    3%   129
scarce               5%    5%   62%   21%    2%    5%    64
abundant            33%    3%   52%    7%    3%    3%   222
no teaching         21%    5%   42%   21%    5%    5%    51
no deck             17%    4%   59%   13%    3%    4%   113
harsh + violent      9%    7%   66%   11%    4%    2%    30
```

**Conditions reorder second place decisively.** Under scarcity the artisan collapses
24% -> 5% while the steward doubles to 21%: when food is tight, mending and hoarding beat
making. Abundance inverts it exactly. Violence lets the broker climb.

**But scholars win all six**, 42% to 66%, and are most dominant in the harshest condition.

The reason is that every condition tested varies *resources*; none of them touch the
*status of knowledge*. Scarcity, abundance, disruption and crowding all change how much
there is to go around. None makes knowing things costly, so techniques compound in all of
them.

Dethroning the scholar needs a world where knowledge is dangerous or useless — a basin
that persecutes the wise, a collapse that destroys the technique graph, an environment
where yield bonuses stop mattering. Nothing in the current world can express any of that.
Logged in §12: the generated world needs to reach into the fitness landscape, not only
into flavour.

## Goals now point at the world (2026-09-05)

`outlive` is removed. It completed by doing nothing, so it never went stale and always
eventually succeeded — an absorbing state that held 21 of 22 survivors by t=3000.

Two kinds replace it, both pointing at what the §4.1 generator produced:

- **`recover`** — learn a technique almost nobody alive still holds. §4.1 makes recovering
  lost knowledge a first-class goal; this is the version the engine can evaluate.
- **`pilgrimage`** — stand where something happened, at a named ruin. Arrival is the whole
  of it.

Goal diversity among the living went from **one kind to six**, and all nine kinds now get
completed: teach 62, master 43, avenge 34, provide 32, pilgrimage 29, bond 25, lineage 22,
accumulate 18, recover 12, with 41 abandonments.


## Time, senescence, and why people starve (2026-09-05)

### One clock

The engine has no "year". The tick is primitive and a **season is 50 ticks**; history is
generated in seasons so the past is counted in the same unit as the present.

No mapping to real time was consistent with the existing rates. Starvation takes 40 ticks
(about right for days), a meal lasts 12 (wrong for days), a life ran 900 (wrong for
anything). Each rate had been tuned for legibility in isolation, so they never shared a
clock. Declaring the tick primitive is honest; pretending it is a day would buy realism
the rates cannot honour.

### Fertility is now a fraction of a life

`REPRO_MIN_AGE` was 60 and `LIFESPAN_MEAN` was 900 — a **15:1 ratio**, set a milestone
apart with nothing tying them together. An agent was fertile for 840 of its 900 ticks and
**eleven generations coexisted** where a population should carry three or four.

`FERTILE_FROM = 0.33` now derives fertility from lifespan, so the two cannot drift apart
again. Lifespan is 400 ticks (~8 seasons), fertility begins at 132 (~2.6 seasons).

```
                        before    after
generations coexisting    10.5      5.8
population                 109    111.8
mean age                   275      160
old age, share of deaths     5%      27%
```

Population held — the risk was that agents would die before reaching a much later
fertility age, and enough of them get there. Senescence went from an edge case to a real
force. The residual overlap above 3-4 is explicable: mean age at death (160) is barely
above the fertility threshold (132), so the average agent never breeds while those who do
live to 400+ and keep having children.

**A paired ablation showed senescence was not the cause of generational overlap** —
turning it on moved the span from 9.8 to 10.5, i.e. not at all. The ratio was always the
problem. Worth recording because senescence looked like the obvious fix and was not.

### Why people starve

1,168 starvation deaths, instrumented at the moment of death:

```
food held by other living agents   mean  672.4 units  (median 622.8)
food standing in nodes             mean  948.3 units
distance to nearest food node      mean    7.6 tiles  (median 7)
living agents within 3 with food   mean    2.24

died with someone holding food within 3 tiles:  871/1168  (75%)
died more than 10 tiles from any food node:     309/1168  (26%)
```

**Starvation is a distribution failure, not scarcity.** Three quarters of the starving die
with 2.24 neighbours carrying food within three tiles, while over 1,600 units exist in a
world where one unit would have saved them.

The mechanisms that would fix it are precisely the ones missing: no granary (nobody can
hold surplus for anyone else — `MAX_CARRY` is 12), no way to signal need (there is no
`ask`, so food flows along *standing* rather than along hunger, and a starving stranger is
invisible to the giving rule), and institutions that hold nothing and allocate nothing.

Roughly **3:1 distribution to distance**. Starvation is 42% of all deaths, so redistribution
could plausibly remove most of it. That moves institutional sanction from "§5.6 says it is
required" to the highest-leverage unbuilt mechanic in the world, justified by measurement
rather than by citation.

### Cost reductions

Tool schema is now filtered by affordance — an agent alone is not offered `steal`, `teach`
or `speak` — and the scaffold asks for the tool without preamble. Tools were **70% of every
prompt's input tokens** (1470 of 2115), so not offering impossible actions is the largest
available saving, and it is better modelling besides.

```
input   887 -> 723 tokens/decision   (18%)
output  314 -> 154 tokens/decision   (51%, measured live on 5 calls)
cost    $0.00246 -> $0.00149          (39%)
```

The model still writes a short preamble. Since removing deliberation may change *what* it
chooses and not only how much it says, halving it is the safer trade.


## Persecution (2026-09-05)

An archetype was a disposition toward verbs and held no view of other kinds. That is why
one strategy won in all six world conditions measured: every condition varied *resources*,
and nothing made knowing things costly.

Two layers of regard. **Structural** tension is the same everywhere — a zealot resents a
scholar (certainty against inquiry), a steward distrusts a broker (one mends, the other
prices the mending), artisan and scholar warm to each other. On top of it, **each basin
distrusts a kind**, and which kind is a fact about the world rather than the archetype: in
generated worlds it follows the history, so a collapse or plague blames the scholar for
failing to prevent it, a conflict blames the zealot for starting it, a famine blames the
broker. A third of flat worlds suspect nobody — the control.

No new verb. Being distrusted means fewer gifts, refused bonds, less teaching, and a
higher chance of being struck. Personal history still dominates: someone who has fed you
outweighs what people say about their sort.

### It closes the §2.1 violation

```
mean survival share when distrusted : 0.038
mean survival share when trusted    : 0.186     (~5x penalty)

winner by world: scholar 8, artisan 2           (was scholar in 6 of 6)
```

The decisive case is the world where scholars are the suspect kind: their share falls from
the usual ~55% to **0.018** and the artisan takes the basin. The scholar is still a strong
strategy — it wins where it is not distrusted — but "one strategy wins regardless of the
world" is now false, which is what §2.1 forbids.

### A world dies of distrust, not of violence

Persecution costs a world about 38% of its population. Splitting it:

```
neither (baseline)                 pop 67.5
violence only (no exclusion)       pop 67.0    costs almost nothing
exclusion only (no extra violence) pop 54.3    -20%
persecution as built               pop 41.8    -38%
```

**The killing is nearly free; the refusal to cooperate is what kills.** Distrust suppresses
giving, teaching and bonding, and since teaching is the strongest lever in the project,
cutting transmission through suspicion is what ends a basin. A world that cannot cooperate
cannot absorb a bad season.

### The test this broke

`test_generated_worlds_remain_viable` asserted no generated world ever goes extinct. That
was only true while the sole cause of extinction was a bug — biome quality silently
shrinking the economy. Extinction now has a legitimate cause, and at the 5-founder default
losing one archetype to distrust looks like collapse.

Rewritten as a comparison — generated against flat, with distrust switched off so the
generator is what is under test. Second time today a failing test turned out to encode a
stale assumption rather than catch a regression. **Tests that assert "this never happens"
age badly once the world gains the ability to make it happen legitimately.**


## The granary, and why it failed (2026-09-05)

Starvation was diagnosed as a distribution failure: 42% of all deaths, 75% of them with
2.24 neighbours carrying food within three tiles, while 1,600 units sat in the basin.
Three things were missing — nowhere to hold a surplus for anyone else (`MAX_CARRY` is 12),
no way to signal need, and institutions that held nothing.

`world/institutions.py` adds a **granary**: a place holding food nobody is carrying, and
a rule about who may take it. Three charters — `open` (anyone hungry), `members` (only
contributors), `kindred` (contributors, excluding the basin's suspect kind). The charter
is where politics lives, and it is a variable rather than a constant.

Plus two verbs: **`ask`**, which makes hunger legible (giving followed *standing*, so food
moved along friendship and a starving stranger was invisible to the rule), and
**`contribute`/`withdraw`**.

### It does not work

```
granaries     pop  starved %    stock   taken
0            36.0     59.4%      0.0     0.0
1            37.0     57.3%    145.3     1.2
4            37.2     55.4%    397.1     7.8
12           38.8     55.6%    580.9    42.7
```

Starvation moves 59.4% -> 55.6%. **Twelve granaries are no better than four** — the
prediction that density would fix it was wrong. All that changes is how much piles up:
**580 units sitting in stores while 55.6% of deaths are starvation.**

The granary became a hoard. Contributing is easy: a surplus agent walks over and drops
food. Withdrawing requires a *starving* agent to be standing at the store, and the people
who die are exactly those far from both food nodes and stores. A hungry agent beside a
node works it; one stranded between everything dies between everything.

**Distribution failure here is about attention, not storage.** More warehouses cannot fix
a problem where nobody carries anything to anyone. The store is a prerequisite — you need
somewhere to draw from — but what would save lives is an agent whose role is to carry: the
temple, drawing on another's behalf. That is also the only thing that would make `ask`
mean anything, since agents currently ask ~1,300 times a run and it changes only who a
nearby giver happens to choose.

### Two silent-edit lessons

The granary block was written into `brain.py` and **did nothing** — the anchor text it was
inserted against had been rewritten by an earlier fix, so `.replace()` matched nothing and
failed quietly. Nothing errored; the feature simply was not there. Edits now assert their
anchor exists before writing.

And `worldgen.py` assigned `institutions = generate_institutions(...)`, shadowing the
module of the same name — the "two unrelated things both called institutions" problem
colliding in the namespace. The lore list is now `chartered`.
