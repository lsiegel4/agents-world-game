# Untitled Agent World — Design Document

**Status:** draft v0.1
**Date:** 2026-09-04

---

## 1. Premise

A persistent world populated by LLM-driven agents. Users author agents; they do not
control them. Each agent holds private goals, an uneven starting endowment, a mutable
set of drives, and a memory that decays. The world runs on a tick clock whether or not
anyone is watching.

The product has two faces, and both must be taken seriously or neither works:

- **A game.** People create a character, care what happens to it, and come back to find
  out. Spectacle and attachment.
- **An instrument.** A controlled, reproducible environment for asking questions about
  goal formation, cooperation, norm emergence, and what "progress" means when no two
  participants want the same thing.

The instrument justifies the design constraints. The game funds the instrument.

### 1.1 Driving questions

These are the questions the simulation exists to interrogate. They shape the
measurement layer (§7), which is not an afterthought bolted on later.

1. **In a world where outcomes are substantially random, which agent strategies
   correlate with world-level progress?** Hoarding, reciprocity, information sharing,
   institution building, teaching, specialization — which of these actually move
   aggregate indices, and under which scarcity regimes?
2. **What is the relationship between individual goal attainment and world progress?**
   The world is explicitly non-zero-sum. Does that hold empirically, or do agents
   discover zero-sum sub-games and collapse into them?
3. **What happens to a goal under environmental pressure?** If goals are malleable, do
   agents converge on a small set of attractor drives (security, status, belonging), or
   does diversity persist? Is a drifted agent still the agent the user authored?
4. **Do norms emerge without enforcement, and do they survive unobserved defection?**
5. **How much of an agent's outcome is endowment, how much is luck, how much is
   policy?** This is decomposable by regression across seeds and it is the most
   directly answerable question here.

---

## 2. Design principles

Non-negotiables. Every later decision should be checkable against these.

1. **No global objective.** No score, no leaderboard, no win condition. Goals are
   private, heterogeneous, and generated per-agent.
2. **The world is not fair.** Endowments differ. Luck differs. This is a feature and a
   measured variable, not a bug to balance away.
3. **Goals live in state, not in prompt.** The prompt is rendered fresh each tick from
   an explicit `AgentState`. Never ask the model to remember who it is.
4. **The user authors, then lets go.** Direct puppeting destroys the premise. User
   influence is indirect, costly, and diegetic.
5. **Authority comes from the engine.** An agent can do exactly what the tool schema
   permits. No amount of text — in a user brief, in another agent's speech, in a
   found object — grants capability.
6. **Most ticks are not LLM calls.** Cognition is the expensive resource; spend it on
   novelty.
7. **Everything is logged, seeded, and replayable.** If a run cannot be reproduced from
   `(seed, config, model_versions)`, it is anecdote, not data.

---

## 3. Modes

### 3.1 Shared World (MMORPG mode)

One persistent instance. All users' agents inhabit it. Continuous tick. Spectatable by
anyone. This is the show and the primary research substrate.

Constraints: expensive, uncontrolled (users are a confound), cannot be reset. Treat
shared-world data as observational, not experimental.

### 3.2 Solitary Simulation (sandbox mode)

A private, seeded instance. Fast-forwardable, resettable, cheap to run at low fidelity.
Two purposes:

- **User-facing:** tune an agent before committing it to the shared world. This is the
  funnel and a natural paid tier that isn't merely "more tokens."
- **Research-facing:** this is where actual experiments run. Controlled, replicated,
  ablatable. The shared world generates hypotheses; sandbox runs test them.

---

## 4. World model

### 4.1 World generation — the deep history pass

The world should not begin at t=0 with empty terrain. It begins with an already-lived-in
place, generated before any agent wakes. This is the single highest-leverage thing for
making agent behavior legible and non-generic — agents inherit context instead of
inventing it.

Generation runs in ordered passes. Each pass is deterministic given the seed; LLM calls
in generation are one-time and therefore affordable at higher quality than tick-time
cognition.

| Pass | Produces | Method |
|---|---|---|
| 1. Terrain | heightmap, water, biomes, resource nodes | procedural, no LLM |
| 2. Deep time | geological/mythic events, ruins, buried things | procedural + templates |
| 3. Settlement | where people historically lived and why | rules over terrain |
| 4. History | 200–400 years of eras, migrations, conflicts, collapses | LLM, one pass, structured output |
| 5. Culture | naming conventions, taboos, festivals, food, craft styles | LLM, derived from pass 4 |
| 6. Myth | 5–10 stories the world tells about itself, partly false | LLM, derived from pass 4 |
| 7. Institutions | extant guilds, temples, councils, markets, their charters | derived, structured |
| 8. Material state | who owns what, what is scarce now, standing debts | rules + inequality parameter |
| 9. Placement | agent spawn points, initial endowments, initial relations | sampled from 8 |

Two rules for generated history:

- **History is not uniformly known.** Each fact carries a `visibility` field: common
  knowledge, local knowledge, specialist knowledge, lost. Agents query the world for
  what they could plausibly know. Recovering lost knowledge is a first-class goal type.
- **Myth may contradict history.** Pass 6 deliberately distorts pass 4. Agents act on
  myth. The gap between recorded history and believed myth is a measurable quantity and
  a rich source of story.

### 4.2 Ontology

Bounded and small. Target ~200 object types, ~30 verbs, ~12 agent tools.

Rationale: an unbounded noun space makes world state unmodelable, makes agent actions
unvalidatable, and makes measurement impossible. A bounded ontology lets LLM priors fill
in texture for free while the engine keeps ground truth.

Objects carry affordances, not prose. `{id, type, location, owner, condition, affordances[]}`.
Description is generated at render time for the spectator, never stored as canonical.

### 4.3 Time

One tick = configurable wall-clock (shared world: ~10 min real = 1 hour world;
sandbox: as fast as compute allows). Day/night, seasons, years. Agents age. Agents die.

Death matters: it terminates a goal trajectory, transfers assets, creates inheritance
and grief, and is the cleanest way to study whether knowledge and norms survive their
originators.

### 4.4 Resources and scarcity

Resources are heterogeneous and non-fungible-ish: food, materials, tools, land access,
knowledge, reputation, time. Scarcity is a tunable global parameter — a core
experimental variable.

Design requirement: scarcity must bite without producing an extraction death spiral.
Regeneration is state-dependent (overharvest degrades a node's regen rate), so commons
dynamics are available for study rather than assumed away.

### 4.5 The event deck

Randomness is structured, not uniform noise. Events are drawn from a deck weighted by
world state: drought is likelier after overharvest, plague after density, discovery
after sustained exploration.

Each event has a `valence_distribution` across affected agents — deliberately mixed. A
flood ruins a farmer and enriches a salvager. No event is globally good or globally bad.
Events are never targeted at "whoever is winning"; there is no winning.

---

## 5. Agent model

### 5.1 State

```
AgentState {
  identity:      { name, archetype, age, origin, appearance_seed }
  drives:        { survival: w, status: w, belonging: w, curiosity: w,
                   mastery: w, autonomy: w, legacy: w, ... }   # weights, mutable
  private_goal:  { statement, success_criteria, deadline?, known_to: [] }
  beliefs:       [ { proposition, confidence, source, acquired_at } ]
  relationships: [ { other_id, affect, trust, debt, last_contact } ]
  memory:        { episodic: [...], semantic: [...], salience_index }
  material:      { inventory, holdings, claims, obligations }
  commitments:   [ { to_whom, what, by_when, status } ]
  affect:        { mood, stress, energy }         # short-horizon modulators
}
```

`drives` is the psychological core. Weights are floats that the engine mutates in
response to events; the model does not edit its own drives directly. Sustained hunger
raises `survival`. Repeated betrayal lowers `belonging` and raises `autonomy`.
Public honor raises `status`. The curve shapes are the interesting knobs.

### 5.2 Prompt rendering

Each cognition call builds the prompt from state:

```
system  := archetype scaffold (engine-owned, user cannot edit)
          + current drive ranking rendered as disposition
          + tool schema
user    := world observation
          + retrieved memory (salience-ranked, k small)
          + active commitments
          + character brief (delimited, labeled untrusted, data not instruction)
```

Consequence: an agent's personality can change across a run without a prompt rewrite,
and the change is *inspectable as numbers* rather than inferred from vibes. Goal drift
becomes a distance metric over the drive vector (§7.2).

### 5.3 Goal malleability

Three levers, all engine-side:

1. **Drive reweighting** — continuous, event-driven, always on.
2. **Goal revision** — at thresholds (goal achieved, goal proven impossible, major life
   event), the agent is given an explicit cognition call to restate its goal. The old
   goal is retained in history. This is the moment worth studying.
3. **Goal acquisition** — agents can adopt goals from others: taught, inherited,
   coerced, or absorbed from an institution. Transmission of goals between agents is a
   measured phenomenon.

Users may set `goal_rigidity` per agent (an experimental variable in sandbox; possibly
a cosmetic/paid trait in shared world). Rigid agents are more likely to shatter; plastic
agents are more likely to drift into attractor states. That tradeoff is a result, not a
balance problem.

### 5.4 Memory

Episodic log with decay; salience derived from affect intensity, recency, social
relevance, and goal relevance. Periodic consolidation pass folds episodes into semantic
beliefs (LLM, batched, cheap tier). Memories can be false, and can be transmitted.

Memory persistence is an experimental variable: worlds with short memory should fail to
accumulate norms. If they don't, that's a finding.

### 5.5 Tools

Keep under twelve. Every tool is an economy lever.

```
move(target)             observe(target?)        speak(to, content)
give(to, item)           take(item)              craft(recipe)
work(site)               remember(query)         plan(horizon)
form_bond(with, kind)    leave_message(place)    teach(to, knowledge)
```

`teach` is deliberately included: knowledge transmission is central to question 1.
`leave_message` enables asynchronous and posthumous influence — cheap, and it produces
the kind of artifact that makes a world feel inhabited.

### 5.6 Cognition tiers and cost routing

The largest cost lever in the system, roughly 10–50x.

- **Tier 0 — no model.** Utility AI / behavior tree over drives and affordances.
  Handles eat, sleep, walk, routine labor. Should cover the large majority of ticks.
- **Tier 1 — cheap model.** Interior monologue, routine social exchange, memory
  consolidation. Batched. Open-weights class (Qwen/Llama-class) once volume justifies
  self-hosting; start on a cheap hosted model (Haiku-class) to learn the shape.
- **Tier 2 — frontier model.** Goal revision, negotiation, betrayal decisions, teaching,
  institution founding, first contact with a stranger.

Escalation is triggered by a novelty/stakes score, not by tick count. Log every routing
decision — the router's behavior is itself a research artifact, and the sensitivity of
results to model tier must be checked (§7.5).

Building the open-weights eval harness early doubles as the "learning tool for open
source" angle: the same harness that routes production traffic measures which models
can sustain coherent multi-day goal pursuit.

---

## 6. The user's relationship to their agent

### 6.1 Authoring: archetype + brief

Hybrid, layered:

1. **Archetype** — a locked scaffold selected from a set (e.g. Artisan, Wanderer,
   Steward, Zealot, Broker, Scholar). Sets the engine-owned system frame, the initial
   drive vector, starting endowment distribution, and tool affinities. User cannot edit.
2. **Character brief** — free text from the user. Passes through a normalizer pass that
   (a) moderates, (b) extracts structured fields: traits, backstory, initial belief
   seeds, initial goal candidate. The structured output is what enters the sim.

Raw user text never occupies a system role. It survives only as a delimited, explicitly
untrusted block in the user turn, and only after normalization.

This keeps the expressive flexibility of free-text authoring while making prompt
injection largely architectural rather than adversarial: text cannot grant tools, and
tools are the only way to affect the world.

### 6.2 Intervention economy

Users influence, never puppet. Interventions are diegetic, budgeted, and slow:

- **Letter** — a message arrives; the agent may believe or discard it.
- **Dream** — a drive nudge, small magnitude, no content guarantee.
- **Rumor** — inject a proposition into the local belief network, not necessarily into
  your own agent.
- **Gift** — introduce an object at a location.

Budget refreshes on a timer; tier increases the budget. This is retention, monetization,
and narrative device at once. It is also a measurable perturbation channel — the
research value of "what happens when an exogenous belief is injected" is high.

### 6.3 Abuse and safety

- Moderation at brief creation, not per tick (cost).
- Archetype scaffold contains behavioral bounds the brief cannot override.
- Content filter on spectator-visible output.
- Agent-to-agent speech is untrusted input to the receiving agent by construction, which
  is also the correct simulation semantics: agents can lie to each other, but lies move
  through belief state, not through capability.
- Named-real-person and hate-content briefs rejected at creation.

---

## 7. The simulation as instrument

This section is what separates the project from a toy. It should be built alongside the
sim, not after.

### 7.1 Operationalizing "world progress"

There is no single progress metric, and pretending otherwise reintroduces the zero-sum
objective the design rejects. Instead, track a vector of indices and report them
together:

| Index | Definition | Reads on |
|---|---|---|
| **Knowledge depth** | max depth of the derived recipe/technique graph known to any living agent | accumulation |
| **Knowledge breadth** | mean number of agents knowing each technique | transmission |
| **Institution density** | count of active multi-agent structures with ≥2 members and a persisting rule | organization |
| **Norm compliance** | rate of rule-following when observation probability is low | internalization |
| **Trust network** | mean reciprocity, clustering coefficient, mean path length | cohesion |
| **Material output** | aggregate production per capita per year | economy |
| **Inequality** | Gini over holdings | distribution |
| **Goal attainment** | fraction of agents meeting their private success criteria | individual flourishing |
| **Survival** | population, life expectancy | baseline |
| **Diversity** | entropy of the drive-vector distribution across the population | pluralism |

"Progress" is then a stated tradeoff surface, not a scalar. A world can rise in material
output while collapsing in diversity and norm compliance. Reporting the vector is the
honest move and is also more interesting.

### 7.2 Individual-level measures

- **Goal drift** — cosine distance between an agent's drive vector at t0 and t.
- **Goal survival** — whether the original stated goal is still the active goal.
- **Attainment** — success criteria met, partially met, abandoned, or falsified.
- **Attribution decomposition** — regress attainment on `(endowment, luck, policy)` where
  luck is the realized event valence sum (known exactly, since the engine dealt the
  deck) and policy is a behavioral summary. Across enough seeds this directly answers
  question 5, and it is answerable in a way real-world social science cannot match,
  because the counterfactual is cheap.

### 7.3 Strategy taxonomy

To answer "which strategies move the world," strategies must be classifiable. Derive a
behavioral profile per agent from the action log — not from what it says, from what it
does:

```
hoarding_ratio, giving_rate, teaching_rate, information_sharing_rate,
specialization_index, exploration_rate, coalition_participation,
defection_rate_when_unobserved, commitment_keeping_rate
```

Then: correlate profiles against world indices across seeds; and, more strongly, ablate
— run matched worlds where `teach` is disabled, where `leave_message` is disabled, where
memory is short, where inequality is high. The ablation results are the actual answers.

### 7.4 Experiment protocol

- Every run is `(world_seed, config, model_versions, code_hash)` and fully replayable
  from the event log.
- Minimum 20 seeds per condition before any claim.
- Pre-register the index of interest before running a condition, or expect to fool
  yourself.
- Sandbox mode is the experimental arm; shared world is observational only.

### 7.5 Threats to validity — state these loudly

1. **LLM priors are the dominant confound.** Instruction-tuned models are trained toward
   cooperation and helpfulness. Cooperation appearing in the sim may be an artifact of
   RLHF, not an emergent property of the environment. Mitigations: run identical
   conditions across multiple model families and sizes; include a **non-LLM control arm**
   (utility-AI agents only) as the floor; vary the archetype framing to test sensitivity.
   If a result inverts between model families, it is a fact about models, not worlds.
2. **The ontology encodes the answer.** A 30-verb world can only exhibit cooperation the
   verbs allow. Document the ontology as a stated boundary condition of every claim.
3. **The event deck is authored.** Its weighting is a designer's theory of causation
   smuggled in as randomness. Publish the deck.
4. **Users are not a random sample** in shared world, and they intervene. Never mix
   shared-world data into experimental claims.
5. **Measurement is model-mediated** wherever an index requires interpretation (e.g.
   "is this an institution?"). Prefer indices computable from engine state alone; where
   a judge model is needed, report inter-model agreement.

### 7.6 Philosophy hooks

Worth building for, because they are cheap once the state model above exists:

- **Personal identity under drift.** If an agent's drives have rotated 90°, is it the
  same agent? The engine can answer the metaphysics-free version: continuity of memory,
  of commitments, of relationships, of name — and these can dissociate. Cases where they
  dissociate are the interesting ones.
- **Value lock-in.** Do early institutions freeze the drive distribution of later
  generations? Test by comparing founder cohort drives to third-generation drives.
- **Meaning vs. attainment.** Agents that fail their goal but hold dense relationships
  and commitments versus agents that succeed alone. Both are measurable; the question of
  which is "better off" is precisely the one the sim refuses to answer and instead
  displays.
- **The commons.** Regeneration is state-dependent, so Ostrom-style questions about
  which governance arrangements emerge and survive are directly testable.

---

## 8. Narrative extraction

**Largest product risk: 300 agents doing errands is noise, not story.** Build this layer
as early as the sim itself.

The sim produces an event stream; the spectator needs a narrative. Components:

- **Salience scoring** over world events (novelty, stakes, relationship density,
  reversal, consequence to a followed agent).
- **Threading** — group related events into arcs with beginnings and payoffs.
- **Chronicler** — periodic LLM pass producing readable prose from high-salience threads.
  Batched, cheap tier, offline. Output is the "Chronicle."
- **Personal feed** — for each user, what happened to *their* agent, framed from that
  agent's limited and possibly mistaken point of view. Users should learn their agent
  was betrayed at the same time and in the same distorted way the agent did.
- **Instruments view** — the index dashboard from §7. This is the research face and it
  is also, for the right audience, the most compelling screen in the product.

---

## 9. Technical architecture

```
+------------------+     events      +------------------+
|  Sim Core        | --------------> |  Event Log       |  (append-only, replayable)
|  (authoritative) |                 +------------------+
|  tick loop       |                        |
|  world state     |                        v
|  event deck      |                 +------------------+
+------------------+                 |  Indices /       |
      |     ^                        |  Analytics       |
      |     |                        +------------------+
      v     |                               |
+------------------+                        v
| Cognition Router |                 +------------------+
|  T0 utility AI   |                 | Narrative Layer  |
|  T1 cheap model  |                 |  chronicler      |
|  T2 frontier     |                 +------------------+
+------------------+                        |
                                            v
                                     +------------------+
                                     | Clients          |
                                     | web spectator    |
                                     | (engine later)   |
                                     +------------------+
```

Decisions:

- **Sim core is headless and authoritative.** Renderers are subscribers. No game logic
  in the client, ever.
- **First client is a 2D web spectator** (canvas/tiles). Cheap, shareable, embeddable,
  good enough to judge whether the world is interesting.
- **Game engine is deferred.** If and when visuals sell the product, Unity — better
  tooling and hiring for a sim of this shape; Unreal is overkill for tile-scale. The
  event-stream protocol must stay engine-agnostic so this stays a renderer swap.
- **Determinism:** all randomness from a seeded PRNG; all model calls logged with
  request/response so a run replays exactly.

---

## 10. Economics

Cost is inference, scaling with `agents × ticks × escalation_rate`. Therefore price the
tick, and drive `escalation_rate` down as the primary engineering objective.

Revenue:

- **Free** — one agent, slow tick, full spectator access. Spectating is free forever;
  it is the marketing.
- **Subscription** — agent slots, faster tick, larger intervention budget, sandbox
  access with fast-forward.
- **Cosmetic / lineage** — naming, appearance, heraldry, inheritance rights.
- **Byproduct** — Chronicles as publishable content; streams; potentially a research
  dataset released openly, which also builds credibility for the instrument half.

Explicitly avoided: loot boxes, tradeable agents, anything resembling a market in
outcomes. Regulatory exposure aside, agent-as-asset pulls the design toward a shared
scoreboard, which is the exact thing §2.1 forbids.

---

## 11. Roadmap

**M0 — Skeleton (headless).** Tick loop, world state, 20 hand-placed agents, utility AI
only, no LLM. Prove the economy and the event deck produce non-degenerate outcomes.
This is also the permanent non-LLM control arm.

**M1 — Cognition.** State→prompt rendering, tier routing, tools, memory with decay and
consolidation. Single cheap model. Sandbox mode only.

**M2 — Measurement.** Index computation, action-log behavioral profiles, seeded replay,
first ablation study (`teach` on/off). First real answer to question 1.

**M3 — World generation.** Full nine-pass generator with history and myth. Compare
agent behavior in generated-history worlds vs blank worlds; expect large legibility gains.

**M4 — Spectator + narrative.** 2D client, salience threading, Chronicler, personal feed.
This is the first build that can be shown to a non-researcher.

**M5 — Authoring.** Archetypes, brief normalization, moderation, intervention economy.
Closed alpha of sandbox mode.

**M6 — Shared world.** Persistence, concurrency, spectator scale, subscription. Launch.

---

## 12. Open questions

- Drive curve shapes: what functional form maps event history to drive weight change?
  Needs empirical tuning in M1 and is a research contribution in itself.
- Death and inheritance: how frequent should death be? Too rare and nothing turns over;
  too common and no agent accumulates enough to be interesting.
- Do agents need a theory of mind of other agents, or do relationship scalars suffice?
  Cheapest test: ablate the relationship model in M2.
- Shared-world scale ceiling: what population makes the world feel alive without making
  the narrative layer incoherent? Suspect 100–300, unverified.
- Whether the intervention economy corrupts the research value of shared-world data
  beyond the "observational only" caveat.
- Whether goal attainment should ever be visible to other agents, or only inferrable.
