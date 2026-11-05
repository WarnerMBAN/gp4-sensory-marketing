"""
validate.py: parse and check each agent's answer; decide whether to retry.

Where it fits
-------------
STEP 6 of the pipeline. run_experiment.py passes the model's raw text here.
The JSON schema sent to OpenAI should already prevent bad answers, but this
module re-checks everything in Python, because a schema is a request to the
model, not a guarantee, and mock or other providers have no schema at all.

What goes in and out
--------------------
In:  raw text returned by the model; the arousal maximum; whether this is a
     diagnostic run (which adds an "explanation" field).
Out: a CheckResult: valid (True/False), the parsed answers, and a list of
     plain-English error messages for the log.

Rules (mirror a paper form, where only valid boxes exist)
---------------------------------------------------------
* Exactly these keys: screen_size, attention_getting, capture_attention,
  arousal, mood (plus explanation in diagnostic runs). No extras.
* Every rating is a whole number (JSON integer; 15.0, "15" and true are
  rejected) within its scale.
* Code fences (```json ... ```) and stray text around the JSON object are
  tolerated: we extract the object. Nothing else is "repaired".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# Rating keys in question order, mapped from the instructor's dictionary keys.
# Instructor key -> our key: "screen size" -> screen_size,
# "attention getting" -> attention_getting, "capture attention" ->
# capture_attention, "arousal" -> arousal, "mood" -> mood.
RATING_KEYS: tuple[str, ...] = (
    "screen_size",
    "attention_getting",
    "capture_attention",
    "arousal",
    "mood",
)
EXPLANATION_KEY: str = "explanation"

# Mood is the affect grid's 9-point pleasure axis in every version so far.
MOOD_MAX: int = 9

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


@dataclass
class CheckResult:
    """Outcome of checking one raw response.

    valid:   True only if every check passed.
    answers: the parsed values (may be partial when invalid).
    errors:  plain-English reasons for failure (empty when valid).
    """

    valid: bool
    answers: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def scale_ranges(arousal_max: int) -> dict[str, tuple[int, int]]:
    """Return {key: (minimum, maximum)} for every rating.

    Why this exists: one place defines the original scales; arousal's top
    comes from the config (open question: 7 or 9).
    """
    return {
        "screen_size": (10, 20),
        "attention_getting": (1, 7),
        "capture_attention": (1, 7),
        "arousal": (1, arousal_max),
        "mood": (1, MOOD_MAX),
    }


def strip_code_fences(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence if present; otherwise return text unchanged."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def extract_json_object(text: str) -> str | None:
    """Return the substring from the first '{' to the last '}', or None if absent.

    Why this exists: some models add a sentence before or after the JSON.
    We keep only the object and let json.loads judge it.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    return text[start : end + 1]


def parse_response(raw_text: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Turn raw model text into a dictionary.

    Output: (dictionary, None) on success, or (None, error message) on failure.
    """
    if raw_text is None or not raw_text.strip():
        return None, "empty response"
    candidate = extract_json_object(strip_code_fences(raw_text.strip()))
    if candidate is None:
        return None, "no JSON object found in the response"
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as err:
        return None, f"invalid JSON: {err.msg} (character {err.pos})"
    if not isinstance(parsed, dict):
        return None, "JSON is not an object"
    return parsed, None


def is_whole_number(value: Any) -> bool:
    """True for a real integer. False for 15.0, "15", True/False or None.

    Why: bool is a subclass of int in Python, so it must be excluded explicitly.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def check_answers(answers: dict[str, Any], arousal_max: int, diagnostic: bool) -> list[str]:
    """Return a list of problems with the parsed answers (empty list = valid)."""
    errors: list[str] = []
    expected = set(RATING_KEYS) | ({EXPLANATION_KEY} if diagnostic else set())

    missing = [k for k in RATING_KEYS if k not in answers]
    if diagnostic and EXPLANATION_KEY not in answers:
        missing.append(EXPLANATION_KEY)
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")

    extra = sorted(set(answers) - expected)
    if extra:
        errors.append(f"unexpected keys: {', '.join(extra)}")

    for key, (low, high) in scale_ranges(arousal_max).items():
        if key not in answers:
            continue
        value = answers[key]
        if not is_whole_number(value):
            errors.append(f"{key} must be a whole number; got {value!r}")
        elif not low <= value <= high:
            errors.append(f"{key}={value} is outside {low}-{high}")

    if diagnostic and EXPLANATION_KEY in answers:
        explanation = answers[EXPLANATION_KEY]
        if not isinstance(explanation, str) or not explanation.strip():
            errors.append("explanation must be non-empty text")
    return errors


def check_response(raw_text: str | None, arousal_max: int, diagnostic: bool = False) -> CheckResult:
    """Parse and check one raw response. The main entry point of this module.

    Inputs:  raw model text; arousal maximum from config; diagnostic flag.
    Output:  CheckResult (valid, answers, errors).
    """
    parsed, parse_error = parse_response(raw_text)
    if parsed is None:
        return CheckResult(valid=False, errors=[parse_error or "could not parse"])
    errors = check_answers(parsed, arousal_max, diagnostic)
    return CheckResult(valid=not errors, answers=parsed, errors=errors)


def should_retry(attempts_so_far: int, max_attempts: int, last_valid: bool) -> bool:
    """Decide whether to call the model again for this agent.

    Inputs:  attempts already made (1 after the first try); the configured
             maximum number of attempts; whether the last answer was valid.
    Output:  True if the last answer was invalid (or the call failed) and
             attempts remain.
    Why this exists: one visible rule for retries, so every agent is treated
    the same and the attempt count in the data means the same thing.
    """
    return (not last_valid) and attempts_so_far < max_attempts


def attention_mean(attention_getting: int, capture_attention: int) -> float:
    """Average of the two attention items, as in the original (attention scale)."""
    return (attention_getting + capture_attention) / 2
