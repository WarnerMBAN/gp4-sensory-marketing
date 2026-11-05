"""
test_assignment.py: the seeded assignment of conditions and personas.

Why this exists
---------------
Random assignment must (1) give 39 high and 38 low for n = 77, (2) give the
same roster every time with the same seed, (3) keep gender balanced within
each condition, and (4) map each condition to the right neutral image.
"""

import dataclasses

import pytest

from gp4.agents import build_roster, split_counts
from gp4.config import load_config, verify_stimuli


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def stim_key():
    return verify_stimuli()


def count(roster, **match):
    """Count agents whose fields equal every value in match."""
    return sum(all(getattr(a, k) == v for k, v in match.items()) for a in roster)


def test_main_run_is_39_high_38_low(config, stim_key):
    roster = build_roster(config, "main", stim_key)
    assert len(roster) == 77
    assert count(roster, condition="high") == 39
    assert count(roster, condition="low") == 38


@pytest.mark.parametrize("n,expected", [(4, (2, 2)), (20, (10, 10)), (77, (39, 38)), (823, (412, 411))])
def test_split_counts(n, expected):
    assert split_counts(n) == expected


def test_same_seed_same_roster(config, stim_key):
    first = build_roster(config, "main", stim_key)
    second = build_roster(config, "main", stim_key)
    assert first == second


def test_different_seed_different_order(config, stim_key):
    other = dataclasses.replace(config, seed=config.seed + 1)
    a = [x.condition for x in build_roster(config, "main", stim_key)]
    b = [x.condition for x in build_roster(other, "main", stim_key)]
    assert a != b
    assert sorted(a) == sorted(b)  # same 39/38 split, different order


def test_assignment_is_actually_shuffled(config, stim_key):
    """Not simply all highs first: both conditions appear in the first 20 agents."""
    first_20 = {a.condition for a in build_roster(config, "main", stim_key)[:20]}
    assert first_20 == {"high", "low"}


def test_gender_quota_within_each_condition(config, stim_key):
    roster = build_roster(config, "main", stim_key)
    assert count(roster, condition="high", gender="male") == 19  # round(39 * .49) = 19
    assert count(roster, condition="low", gender="male") == 19   # round(38 * .49) = 19
    assert count(roster, gender="male") == 38                    # 38/77 = 49.4%
    assert all(a.gender in ("male", "female") for a in roster)


def test_no_persona_means_blank_gender(config, stim_key):
    none_cfg = dataclasses.replace(config, persona_mode="none")
    roster = build_roster(none_cfg, "main", stim_key)
    assert all(a.gender == "" and a.persona_mode == "none" for a in roster)


def test_conditions_map_to_neutral_images(config, stim_key):
    for agent in build_roster(config, "main", stim_key):
        expected = "stim_A.png" if agent.condition == "high" else "stim_B.png"
        assert agent.stim_file == expected
        assert agent.stim_sha256 == stim_key[agent.condition]["sha256"]


def test_agent_ids_unique_and_prefixed(config, stim_key):
    for label, prefix, first_id in [("main", "M", "M001"), ("smoke", "S", "S001"), ("robustness", "R", "R001")]:
        roster = build_roster(config, label, stim_key)
        ids = [a.agent_id for a in roster]
        assert len(ids) == len(set(ids))
        assert ids[0] == first_id and all(i.startswith(prefix) for i in ids)


def test_robustness_run_split(config, stim_key):
    roster = build_roster(config, "robustness", stim_key)
    assert len(roster) == 823
    assert count(roster, condition="high") == 412
    assert count(roster, condition="low") == 411
