"""
test_validate.py: answer parsing, range checks and the retry rule.

Why this exists
---------------
Every agent's answer passes through validate.check_response. These tests
prove it accepts good answers (including code-fenced JSON) and rejects
anything a paper form would not allow: out-of-range values, decimals, text,
missing or extra keys.
"""

import json

import pytest

from gp4.validate import attention_mean, check_response, should_retry

GOOD = '{"screen_size": 15, "attention_getting": 5, "capture_attention": 4, "arousal": 6, "mood": 5}'


def test_valid_json_passes():
    result = check_response(GOOD, arousal_max=9)
    assert result.valid and result.errors == []
    assert result.answers["screen_size"] == 15


def test_code_fenced_json_passes():
    fenced = f"```json\n{GOOD}\n```"
    assert check_response(fenced, arousal_max=9).valid


def test_plain_fence_and_surrounding_text_pass():
    assert check_response(f"```\n{GOOD}\n```", arousal_max=9).valid
    assert check_response(f"Here are my answers: {GOOD} Thanks.", arousal_max=9).valid


@pytest.mark.parametrize(
    "key,bad_value",
    [("screen_size", 9), ("screen_size", 21), ("attention_getting", 0), ("capture_attention", 8),
     ("arousal", 10), ("arousal", 0), ("mood", 10)],
)
def test_out_of_range_rejected(key, bad_value):
    answers = json.loads(GOOD)
    answers[key] = bad_value
    result = check_response(json.dumps(answers), arousal_max=9)
    assert not result.valid
    assert any(key in e and "outside" in e for e in result.errors)


def test_arousal_max_7_rejects_8():
    answers = json.loads(GOOD)
    answers["arousal"] = 8
    assert check_response(json.dumps(answers), arousal_max=9).valid
    assert not check_response(json.dumps(answers), arousal_max=7).valid


@pytest.mark.parametrize("bad_value", ["15", 15.0, 15.5, True, None])
def test_non_integers_rejected(bad_value):
    answers = json.loads(GOOD)
    answers["screen_size"] = bad_value
    result = check_response(json.dumps(answers), arousal_max=9)
    assert not result.valid
    assert any("whole number" in e for e in result.errors)


def test_missing_key_rejected():
    text = '{"screen_size": 15, "attention_getting": 5, "capture_attention": 4, "arousal": 6}'
    result = check_response(text, arousal_max=9)
    assert not result.valid and any("missing keys: mood" in e for e in result.errors)


def test_extra_key_rejected_in_main_run():
    text = GOOD[:-1] + ', "explanation": "red is eye-catching"}'
    result = check_response(text, arousal_max=9, diagnostic=False)
    assert not result.valid and any("unexpected keys" in e for e in result.errors)


def test_diagnostic_requires_explanation():
    assert not check_response(GOOD, arousal_max=9, diagnostic=True).valid
    with_expl = GOOD[:-1] + ', "explanation": "The laptop looks like a standard model."}'
    assert check_response(with_expl, arousal_max=9, diagnostic=True).valid
    empty_expl = GOOD[:-1] + ', "explanation": "  "}'
    assert not check_response(empty_expl, arousal_max=9, diagnostic=True).valid


@pytest.mark.parametrize("raw", [None, "", "   ", "I cannot help with that.", "[1, 2, 3]", "{screen_size: 15}"])
def test_unparseable_rejected(raw):
    result = check_response(raw, arousal_max=9)
    assert not result.valid and result.errors


def test_python_dict_style_rejected():
    """The instructor's prompt asked for a Python dictionary; single quotes are not JSON."""
    py_dict = "{'screen_size': 15, 'attention_getting': 5, 'capture_attention': 4, 'arousal': 6, 'mood': 5}"
    assert not check_response(py_dict, arousal_max=9).valid


def test_retry_rule():
    assert should_retry(attempts_so_far=1, max_attempts=3, last_valid=False)
    assert should_retry(attempts_so_far=2, max_attempts=3, last_valid=False)
    assert not should_retry(attempts_so_far=3, max_attempts=3, last_valid=False)  # limit reached
    assert not should_retry(attempts_so_far=1, max_attempts=3, last_valid=True)   # already valid


def test_attention_mean():
    assert attention_mean(5, 4) == 4.5
