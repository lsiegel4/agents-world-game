"""Per-agent behavioral profiles — DESIGN.md §7.3 and §7.2.

Two rules, both load-bearing:

  1. **Policy is derived from what an agent did, not from what it says.** Every
     field here comes off the action log. When agents can speak (M1) that
     distinction stops being free, so the discipline is set now.
  2. **Luck is known exactly.** The engine dealt the deck, so the realized
     valence for each agent is recorded rather than inferred. This is what lets
     §7.2 separate luck from policy in a way field social science cannot.

The available profile is thin because the M0 verb set is thin. The fields that
need M1's social verbs are listed in UNAVAILABLE rather than approximated.
"""

from . import stats

UNAVAILABLE = {
    "commitment_keeping_rate": "needs commitments, which arrive with goals (slice 3)",
}


POLICY_WINDOW = 100   # actions


def build(log, policy_window: int = POLICY_WINDOW) -> dict:
    """agent_id -> {endowment, luck, policy, outcome} for every agent that lived.

    Policy is measured over the agent's FIRST `policy_window` actions only, and
    the outcome over its whole life. Measuring both over the same window makes
    the predictor a proxy for the outcome: an agent that dies young takes fewer
    actions, so it touches fewer distinct verbs, so it scores as more
    specialized purely because it died. That artifact put policy's apparent
    weight at 1.60 against luck's 0.24 in the first version of this analysis.
    """
    agents = {}

    for r in log.records:
        kind = r["kind"]

        if kind in ("spawn", "birth"):
            agents[r["agent"]] = {
                "generation": r.get("generation", 0),
                "start_food": r.get("food", r.get("parent_food", 0.0)),
                "start_age": r.get("age", 0),
                "d_food": r.get("d_food", -1),
                "d_wood": r.get("d_wood", -1),
                "born_tick": r["tick"],
                "restraint_at_t0": r.get("restraint", 0.0),
                "victimized": 0,
                "retaliations": 0,
                "wronged_by": set(),
                "verbs": {},
                "early": {},
                "n_early": 0,
                "luck": 0,
                "helped": 0,
                "harmed": 0,
                "died": False,
                "death_tick": None,
                "cause": "",
                "lifespan": 0,
            }

        elif kind == "action":
            a = agents.get(r["agent"])
            if a is not None:
                if r["verb"] in ("steal", "harm"):
                    victim = agents.get(r.get("target"))
                    if victim is not None:
                        victim["victimized"] += 1
                        victim["wronged_by"].add(r["agent"])
                    # Retaliation: harming someone who wronged you first.
                    if r.get("target") in a["wronged_by"]:
                        a["retaliations"] += 1
                a["verbs"][r["verb"]] = a["verbs"].get(r["verb"], 0) + 1
                if a["n_early"] < policy_window:
                    a["early"][r["verb"]] = a["early"].get(r["verb"], 0) + 1
                    a["n_early"] += 1

        elif kind == "deck":
            for agent_id, v in (r.get("valence") or {}).items():
                a = agents.get(agent_id)
                if a is None:
                    continue
                a["luck"] += v
                if v > 0:
                    a["helped"] += 1
                else:
                    a["harmed"] += 1

        elif kind == "death":
            a = agents.get(r["agent"])
            if a is not None:
                a["died"] = True
                a["death_tick"] = r["tick"]
                a["cause"] = r["cause"]
                a["lifespan"] = r["age"]

    # Derive policy shares. Agents alive at the end have censored lifespans;
    # the flag is kept so analysis can decide rather than quietly mixing them in.
    for a in agents.values():
        total = sum(a["verbs"].values()) or 1
        a["n_actions"] = total
        early_total = a["n_early"] or 1
        violent = (a["verbs"].get("steal", 0) + a["verbs"].get("harm", 0)
                   + a["verbs"].get("coerce", 0))
        a["giving_rate"] = a["verbs"].get("give", 0) / total
        a["teaching_rate"] = a["verbs"].get("teach", 0) / total
        a["information_sharing_rate"] = a["verbs"].get("speak", 0) / total
        a["coalition_participation"] = a["verbs"].get("form_bond", 0) / total
        a["theft_rate"] = a["verbs"].get("steal", 0) / total
        a["harm_rate"] = a["verbs"].get("harm", 0) / total
        a["retaliation_rate"] = a["retaliations"] / violent if violent else 0.0
        a["wronged_by"] = len(a["wronged_by"])
        for verb in ("work", "move", "eat", "repair", "reproduce", "idle"):
            a[f"{verb}_share"] = a["early"].get(verb, 0) / early_total
        # Low entropy = an agent that did one thing. Early window only.
        a["specialization"] = 1.0 - stats.entropy(list(a["early"].values()))
        if not a["died"]:
            a["lifespan"] = a["start_age"] + total  # one action per tick alive
            a["censored"] = True
        else:
            a["censored"] = False

    return agents


ENDOWMENT = ["start_food", "d_food", "d_wood"]
LUCK = ["luck"]
POLICY = ["move_share", "repair_share", "specialization",
          "giving_rate", "teaching_rate", "coalition_participation"]


def attribution(profiles: dict, uncensored_only: bool = True) -> dict:
    """§7.2: regress lifespan on (endowment, luck, policy).

    Standardized betas, so the three groups are directly comparable. Censored
    agents — those still alive when the run ended — are excluded by default,
    since including them would understate the spread of outcomes.
    """
    rows, ys = [], []
    for a in profiles.values():
        if uncensored_only and a.get("censored"):
            continue
        # The agent must have survived the whole policy window, or its policy is
        # measured over a truncated life and the artifact returns.
        if a["n_early"] < POLICY_WINDOW:
            continue
        rows.append([a[f] for f in ENDOWMENT + LUCK + POLICY])
        ys.append(a["lifespan"])

    if len(rows) < 20:
        return {"n": len(rows), "r2": 0.0, "betas": {}, "groups": {}}

    fit = stats.ols(rows, ys)
    names = ENDOWMENT + LUCK + POLICY
    betas = dict(zip(names, [round(b, 4) for b in fit["betas"]]))

    groups = {
        "endowment": round(sum(abs(betas[f]) for f in ENDOWMENT), 4),
        "luck":      round(sum(abs(betas[f]) for f in LUCK), 4),
        "policy":    round(sum(abs(betas[f]) for f in POLICY), 4),
    }
    return {"n": fit["n"], "r2": round(fit["r2"], 4), "betas": betas, "groups": groups}
