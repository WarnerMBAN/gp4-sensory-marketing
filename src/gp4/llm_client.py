"""
llm_client.py: send one agent's prompt and image to a model; get raw text back.

Where it fits
-------------
STEP 5 of the pipeline. run_experiment.py calls client.complete(request) once
per attempt. Two clients share the same interface, so the rest of the code
does not care which one is used:

  * OpenAIClient  the real call (OpenAI Responses API, multimodal, JSON schema).
  * MockClient    fake answers for dry runs. No network, no cost.

Swapping provider later (for example a second model) means writing one more
class with the same complete() method. Nothing else changes.

What goes in and out
--------------------
In:  an LLMRequest: system text, user text, image bytes, and whether the
     diagnostic explanation field is expected.
Out: an LLMResult: the raw text returned (or an error message), response id,
     token counts, the temperature actually sent, and a UTC timestamp.
     This module never judges the answer; validate.py does that.

How the image is sent (integrity rule: the real image, multimodal)
------------------------------------------------------------------
One user message with two parts, in this order:
  1. the image, as a base64 data URL ("data:image/png;base64,..."), with the
     configured detail level; the file NAME is never sent;
  2. the task text.
The system text goes in a separate system message. Each call is independent:
no conversation id and no previous_response_id, so agents share no memory.
store=False asks OpenAI not to keep the response on its side.
"""

from __future__ import annotations

import base64
import os
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from gp4.config import PROJECT_ROOT, Config, ConfigError
from gp4.validate import EXPLANATION_KEY, RATING_KEYS, scale_ranges

SCHEMA_NAME = "gp4_response"


# --------------------------------------------------------------------------
# Request and result records
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMRequest:
    """Everything needed for one call. agent_id and attempt are for logging and the mock only."""

    agent_id: str
    attempt: int
    system_text: str
    user_text: str
    image_bytes: bytes
    image_mime: str
    diagnostic: bool


@dataclass
class LLMResult:
    """What came back from one call.

    raw_text:         exact text returned by the model ("" if none)
    error:            None on success; otherwise a short description of the
                      failure (network, rate limit, refusal, empty output)
    response_id:      provider's id for audit ("" for failures and mocks)
    input_tokens, output_tokens: token usage (None when unknown)
    temperature_sent: the temperature actually sent (None if none was sent)
    called_at:        UTC time the call finished, ISO format
    """

    raw_text: str
    error: str | None
    response_id: str
    input_tokens: int | None
    output_tokens: int | None
    temperature_sent: float | None
    called_at: str


class FatalClientError(Exception):
    """A problem that retrying cannot fix (bad key, unknown model, no access).

    Why this exists: without it, a wrong API key would be "retried" 3 times
    for each of 77 agents. Instead the run stops at once with a clear message.
    """


class LLMClient(Protocol):
    """The interface every client follows."""

    model_label: str

    def complete(self, request: LLMRequest) -> LLMResult:
        """Make one call and return the result. Must not raise for ordinary failures."""
        ...


def utc_now() -> str:
    """Current UTC time as an ISO string, e.g. 2026-11-05T21:14:03.123456+00:00."""
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# JSON schema (enforces the original scales at the model's side)
# --------------------------------------------------------------------------

def build_json_schema(arousal_max: int, diagnostic: bool) -> dict[str, Any]:
    """JSON schema for the answer: each rating is an integer from a fixed list.

    Inputs:  arousal maximum (from config); diagnostic flag (adds explanation).
    Output:  a JSON-schema dictionary for OpenAI structured outputs.
    Why this exists: it mirrors a paper form, where only valid boxes exist.
    An "enum" (list of allowed values) is used rather than minimum/maximum
    because enums are supported in strict mode. Python re-checks anyway.
    """
    properties: dict[str, Any] = {}
    for key, (low, high) in scale_ranges(arousal_max).items():
        properties[key] = {"type": "integer", "enum": list(range(low, high + 1))}
    required = list(RATING_KEYS)
    if diagnostic:
        properties[EXPLANATION_KEY] = {"type": "string"}
        required.append(EXPLANATION_KEY)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def image_data_url(image_bytes: bytes, mime: str) -> str:
    """Encode image bytes as a data URL. The file name is deliberately not included."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


# --------------------------------------------------------------------------
# Real client: OpenAI
# --------------------------------------------------------------------------

def get_api_key() -> str:
    """Read OPENAI_API_KEY from the environment (loading .env first if present).

    Locally the key lives in .env. On Streamlit Community Cloud it is entered
    as a secret, which Streamlit exposes as an environment variable.
    The key is never printed or logged.
    """
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or key == "your-key-here":
        raise ConfigError(
            "OPENAI_API_KEY is not set.\n"
            "Fix: copy .env.example to .env in the project folder and paste your key after "
            "OPENAI_API_KEY= (no quotes, no spaces). Dry runs do not need a key."
        )
    return key


class OpenAIClient:
    """Real calls to the OpenAI Responses API.

    Temperature: sent if config.temperature is set. If the model rejects the
    parameter, the client switches it off for the rest of the run, records
    temperature_sent = None, and notes the switch in temperature_note (the run
    log prints it). This happens before any answer is accepted.
    """

    def __init__(self, config: Config) -> None:
        from openai import OpenAI  # imported here so dry runs never need the key

        self._config = config
        self.model_label = config.model
        # max_retries: the library's own retries for network blips and rate
        # limits (with back-off). These are not "attempts" in our sense:
        # an attempt is one complete request that produced an answer or failed.
        self._client = OpenAI(
            api_key=get_api_key(),
            timeout=config.request_timeout_seconds,
            max_retries=2,
        )
        self._lock = threading.Lock()
        self._send_temperature = config.temperature is not None
        self.temperature_note = ""

    def _request_kwargs(self, request: LLMRequest) -> dict[str, Any]:
        """Build the arguments for responses.create (one image, then the task text)."""
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "input": [
                {"role": "system", "content": request.system_text},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": image_data_url(request.image_bytes, request.image_mime),
                            "detail": self._config.image_detail,
                        },
                        {"type": "input_text", "text": request.user_text},
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": SCHEMA_NAME,
                    "schema": build_json_schema(self._config.arousal_max, request.diagnostic),
                    "strict": True,
                }
            },
            "max_output_tokens": self._config.max_output_tokens,
            "store": False,
        }
        with self._lock:
            if self._send_temperature:
                kwargs["temperature"] = self._config.temperature
        return kwargs

    def _disable_temperature(self, message: str) -> None:
        """Stop sending temperature after the model rejects it (thread-safe)."""
        with self._lock:
            if self._send_temperature:
                self._send_temperature = False
                self.temperature_note = (
                    f"Model {self._config.model} rejected the temperature parameter; "
                    f"temperature was not sent and is blank in the data. API message: {message[:200]}"
                )

    def complete(self, request: LLMRequest) -> LLMResult:
        """Make one call. Ordinary failures come back as LLMResult.error; fatal ones raise."""
        import openai

        kwargs = self._request_kwargs(request)
        try:
            response = self._client.responses.create(**kwargs)
        except openai.BadRequestError as err:
            if "temperature" in kwargs and "temperature" in str(err).lower():
                self._disable_temperature(str(err))
                return self.complete(request)  # same attempt, now without temperature
            if "schema" in str(err).lower() or "text.format" in str(err).lower():
                raise FatalClientError(f"The API rejected the JSON schema: {err}") from err
            return self._failure(f"BadRequestError: {err}")
        except (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError) as err:
            raise FatalClientError(
                f"{type(err).__name__}: {err}\n"
                "Fix: check the API key in .env and that this key can use the model in config."
            ) from err
        except openai.APIError as err:  # timeouts, rate limits, server errors after library retries
            return self._failure(f"{type(err).__name__}: {err}")

        usage = getattr(response, "usage", None)
        raw_text = response.output_text or ""
        error = None
        if not raw_text:
            details = getattr(response, "incomplete_details", None)
            error = f"empty output (status={response.status}, details={details})"
        return LLMResult(
            raw_text=raw_text,
            error=error,
            response_id=response.id or "",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            temperature_sent=kwargs.get("temperature"),
            called_at=utc_now(),
        )

    def _failure(self, message: str) -> LLMResult:
        """An LLMResult describing a failed call (to be retried by run_experiment)."""
        return LLMResult("", message[:500], "", None, None, None, utc_now())


# --------------------------------------------------------------------------
# Mock client: dry runs (no network, no cost)
# --------------------------------------------------------------------------

MOCK_SCENARIOS: tuple[str, ...] = (
    "normal",          # random plausible answers, no built-in effect
    "fake_effect",     # random answers with a FAKE high-vs-low effect (to exercise the analysis)
    "identical",       # every agent gives exactly the same answer (zero variance)
    "out_of_range",    # first attempt out of range, second attempt valid (tests retries)
    "code_fenced",     # valid JSON wrapped in ```json fences (tests extraction)
    "api_failure",     # first attempt fails like an API error, then valid
    "always_fail",     # every attempt fails (agent ends with valid = False)
    "mixed",           # each agent randomly gets one of the behaviours above
)


class MockAPIError(Exception):
    """Stand-in for a network or server error in dry runs."""


class MockClient:
    """Fake model for dry runs. Answers are random but reproducible (seeded).

    The mock needs to know the condition only for the "fake_effect" scenario.
    It looks the image hash up in the stimulus key, which a real model never
    sees. This is test scaffolding, not part of the experiment.
    """

    def __init__(self, config: Config, scenario: str, stimulus_key: dict[str, dict[str, str]]) -> None:
        if scenario not in MOCK_SCENARIOS:
            raise ConfigError(f"Unknown mock scenario {scenario!r}. Use one of {', '.join(MOCK_SCENARIOS)}.")
        self._config = config
        self.scenario = scenario
        self.model_label = "MOCK"
        self.temperature_note = ""
        self._condition_by_hash = {info["sha256"]: cond for cond, info in stimulus_key.items()}

    def _rng(self, request: LLMRequest, salt: str = "") -> random.Random:
        """A random generator seeded by agent and attempt, so reruns give identical mock data."""
        return random.Random(f"{self._config.seed}|{request.agent_id}|{request.attempt}|{salt}")

    def _scenario_for(self, request: LLMRequest) -> str:
        """Which behaviour this agent shows (fixed per agent, also under "mixed")."""
        if self.scenario != "mixed":
            return self.scenario
        options = ("normal", "normal", "normal", "out_of_range", "code_fenced", "api_failure", "always_fail")
        return random.Random(f"{self._config.seed}|{request.agent_id}|scenario").choice(options)

    def _answers(self, request: LLMRequest, effect: bool) -> dict[str, Any]:
        """Random answers inside the scales; optionally shifted up for the high image."""
        rng = self._rng(request)
        condition = self._condition_by_hash.get(_sha(request.image_bytes), "low")
        shift = 1 if (effect and condition == "high") else 0
        top_arousal = self._config.arousal_max
        answers: dict[str, Any] = {
            "screen_size": min(20, rng.choice([13, 14, 14, 15, 15, 15, 16]) + shift),
            "attention_getting": min(7, rng.randint(3, 6) + shift),
            "capture_attention": min(7, rng.randint(3, 6) + shift),
            "arousal": min(top_arousal, rng.randint(4, 7) + shift),
            "mood": rng.randint(4, 7),
        }
        if request.diagnostic:
            answers[EXPLANATION_KEY] = "MOCK explanation: this is fake text from a dry run."
        return answers

    def complete(self, request: LLMRequest) -> LLMResult:
        """Return a fake result according to the scenario."""
        import json

        behaviour = self._scenario_for(request)
        if behaviour in ("api_failure", "always_fail") and (behaviour == "always_fail" or request.attempt == 1):
            return LLMResult("", "MockAPIError: simulated server error (dry run)", "", None, None, None, utc_now())

        if behaviour == "identical":
            answers: dict[str, Any] = {"screen_size": 15, "attention_getting": 5, "capture_attention": 5,
                                       "arousal": 6, "mood": 6}
            if request.diagnostic:
                answers[EXPLANATION_KEY] = "MOCK explanation: identical answers."
        else:
            answers = self._answers(request, effect=(behaviour == "fake_effect"))

        if behaviour == "out_of_range" and request.attempt == 1:
            answers["screen_size"] = 27  # outside 10-20: must trigger a retry

        text = json.dumps(answers)
        if behaviour == "code_fenced":
            text = f"```json\n{text}\n```"
        return LLMResult(
            raw_text=text,
            error=None,
            response_id=f"mock-{request.agent_id}-{request.attempt}",
            input_tokens=0,
            output_tokens=0,
            temperature_sent=None,
            called_at=utc_now(),
        )


def _sha(data: bytes) -> str:
    """SHA-256 of bytes (local helper for the mock's image lookup)."""
    import hashlib

    return hashlib.sha256(data).hexdigest()
