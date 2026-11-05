"""
agents.py: create the roster of simulated participants.

Where it fits
-------------
STEP 3 of the pipeline. Decides, before any model call, which agent sees
which image and (with the student persona) which gender each agent is told.

What goes in and out
--------------------
In:  Config (seed, run sizes, persona settings) and a run label
     (smoke, main, diagnostic or robustness).
Out: a list of Agent records: agent_id, condition, neutral image file and
     hash, persona mode and gender.

Design choices (and why)
------------------------
* Between-subjects: each agent gets exactly ONE condition and ONE image.
* Conditions are split as evenly as possible (77 -> 39 high, 38 low; the
  extra agent goes to "high"), then shuffled with a seeded random generator
  so the order is random but reproducible.
* Gender quota (student persona): 49% male is applied WITHIN each condition,
  so gender cannot be confounded with condition. With n = 77 this gives
  19 of 39 (high) and 19 of 38 (low) male: 38 of 77 = 49.4% overall.
* Reproducibility: the same seed always gives the same roster. The roster is
  also written into every data row (condition, gender), so the exact
  assignment is preserved even if a future Python version shuffles differently.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from gp4.config import Config, ConfigError, RUN_LABELS


@dataclass(frozen=True)
class Agent:
    """One simulated participant.

    agent_id:     e.g. "M001" (prefix from the run label, then a number)
    run_label:    smoke, main, diagnostic or robustness
    condition:    "high" or "low" saturation (never shown to the model)
    stim_file:    neutral image name, e.g. "stim_A.png"
    stim_sha256:  fingerprint of that image
    persona_mode: "student" or "none"
    gender:       "male", "female", or "" when there is no persona
    """

    agent_id: str
    run_label: str
    condition: str
    stim_file: str
    stim_sha256: str
    persona_mode: str
    gender: str


def split_counts(n: int) -> tuple[int, int]:
    """Return (n_high, n_low), as equal as possible; any odd agent goes to high.

    Example: 77 -> (39, 38); 823 -> (412, 411); 4 -> (2, 2).
    """
    n_high = (n + 1) // 2
    return n_high, n - n_high


def assign_conditions(n: int, rng: random.Random) -> list[str]:
    """Return a shuffled list of n conditions ("high"/"low").

    Why this exists: random assignment, as in the original experiment, but
    reproducible because rng is seeded.
    """
    n_high, n_low = split_counts(n)
    conditions = ["high"] * n_high + ["low"] * n_low
    rng.shuffle(conditions)
    return conditions


def male_count(group_size: int, pct_male: float) -> int:
    """Number of male personas in a group of this size (rounded to nearest).

    Python's round() rounds exact halves to the nearest even number; that only
    matters for tiny groups and is reproducible either way.
    """
    return round(group_size * pct_male)


def assign_genders(conditions: list[str], pct_male: float, rng: random.Random) -> list[str]:
    """Return one gender per agent, applying the male quota within each condition.

    Inputs:  the shuffled conditions list; share of males (e.g. 0.49); seeded rng.
    Output:  list of "male"/"female", aligned with conditions.
    """
    genders = [""] * len(conditions)
    for condition in ("high", "low"):
        positions = [i for i, c in enumerate(conditions) if c == condition]
        n_male = male_count(len(positions), pct_male)
        labels = ["male"] * n_male + ["female"] * (len(positions) - n_male)
        rng.shuffle(labels)
        for position, label in zip(positions, labels):
            genders[position] = label
    return genders


def make_agent_id(prefix: str, number: int, n_total: int) -> str:
    """Build an ID like M001 or R0823 (zero-padded so IDs sort correctly)."""
    width = max(3, len(str(n_total)))
    return f"{prefix}{number:0{width}d}"


def build_roster(
    config: Config,
    run_label: str,
    stimulus_key: dict[str, dict[str, str]],
    n_agents: int | None = None,
) -> list[Agent]:
    """Create every agent for one run.

    Inputs:
      config        checked settings (seed, run sizes, persona)
      run_label     smoke, main, diagnostic or robustness
      stimulus_key  {condition: {file, sha256}} from config.verify_stimuli()
      n_agents      optional override of the run size (tests only)
    Output: list of Agent, in agent_id order.
    """
    if run_label not in RUN_LABELS:
        raise ConfigError(f"Unknown run label {run_label!r}. Use one of {', '.join(RUN_LABELS)}.")
    n = n_agents if n_agents is not None else config.run_sizes[run_label]

    # One seeded generator, used in a fixed order: conditions first, then genders.
    rng = random.Random(config.seed)
    conditions = assign_conditions(n, rng)
    if config.persona_mode == "student":
        genders = assign_genders(conditions, config.pct_male, rng)
    else:
        genders = [""] * n

    prefix = config.agent_id_prefix[run_label]
    roster: list[Agent] = []
    for index, (condition, gender) in enumerate(zip(conditions, genders), start=1):
        stim = stimulus_key[condition]
        roster.append(
            Agent(
                agent_id=make_agent_id(prefix, index, n),
                run_label=run_label,
                condition=condition,
                stim_file=stim["file"],
                stim_sha256=stim["sha256"],
                persona_mode=config.persona_mode,
                gender=gender,
            )
        )
    return roster
