"""
test_run_experiment.py: the experiment engine and the API client, with no real calls.

Why this exists
---------------
Phase 3 must prove the edge cases work. Each test runs the full engine with
the MockClient (or a fake OpenAI server) and checks the saved data:
  * every agent giving the same answer (zero variance) is saved correctly;
  * out-of-range answers trigger a retry; code-fenced JSON is accepted;
  * a simulated API failure is retried; repeated failures end as valid = False;
  * a fatal error (e.g. a bad key) stops the run at once, keeping partial data;
  * live runs refuse the mock client and unsigned settings;
  * the real client sends ONE image before the text, no file name, the
    approved settings, and drops temperature if the model rejects it.
All output goes to a temporary folder, never data/real or data/mock.
"""

import dataclasses
import json
from types import SimpleNamespace

import httpx2
import openai
import pandas as pd
import pytest

from gp4.config import ConfigError, load_config, verify_stimuli
from gp4.llm_client import FatalClientError, LLMRequest, MockClient, OpenAIClient, build_json_schema
from gp4.run_experiment import run_experiment


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def stim_key():
    return verify_stimuli()


def dry(config, stim_key, tmp_path, scenario, n=8, label="main"):
    """Run a small dry run and return (outputs, data frame)."""
    out = run_experiment(config, label, MockClient(config, scenario, stim_key), dry_run=True,
                         n_agents=n, echo=False, out_dir=tmp_path)
    return out, pd.read_csv(out.csv_path)


def test_identical_answers_saved_with_zero_variance(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "identical")
    assert df.valid.all() and (df.attempts == 1).all()
    assert df.screen_size.nunique() == 1 and df.screen_size.iloc[0] == 15
    assert df.dry_run.all()


def test_out_of_range_triggers_one_retry(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "out_of_range")
    assert df.valid.all() and (df.attempts == 2).all()
    assert df.errors.str.contains("screen_size=27 is outside 10-20").all()
    assert df.screen_size.between(10, 20).all()


def test_code_fenced_json_accepted_first_time(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "code_fenced")
    assert df.valid.all() and (df.attempts == 1).all()
    assert df.raw_output.str.startswith("```json").all()


def test_api_failure_is_retried(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "api_failure")
    assert df.valid.all() and (df.attempts == 2).all()
    assert df.errors.str.contains("simulated server error").all()


def test_repeated_failure_kept_as_invalid(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "always_fail")
    assert (~df.valid).all() and (df.attempts == config.max_attempts).all()
    assert df[["screen_size", "attention", "arousal", "mood"]].isna().all().all()
    assert out.n_valid == 0 and out.n_agents == 8


def test_jsonl_has_every_attempt(config, stim_key, tmp_path):
    out, _ = dry(config, stim_key, tmp_path, "out_of_range", n=4)
    records = [json.loads(line) for line in out.jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 4
    assert all(len(r["attempt_log"]) == 2 for r in records)
    assert all(r["attempt_log"][0]["valid"] is False and r["attempt_log"][1]["valid"] is True for r in records)


def test_diagnostic_run_keeps_explanation(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "normal", n=4, label="diagnostic")
    assert df.valid.all() and df.explanation.str.startswith("MOCK explanation").all()
    assert df.agent_id.str.startswith("D").all()
    assert set(df.prompt_sha) <= {"339c649a4799", "ab9cdc6257d4"}


def test_snapshot_records_settings_and_prompts(config, stim_key, tmp_path):
    out, df = dry(config, stim_key, tmp_path, "normal", n=4)
    snap = json.loads(out.config_path.read_text(encoding="utf-8"))
    assert snap["dry_run"] is True and snap["settings"]["model"] == "gpt-4o-mini"
    assert set(snap["prompt_variants"]) == set(df.prompt_sha)
    assert "MOCK DATA, NOT RESULTS" in out.log_path.read_text(encoding="utf-8")


class FatalOnThirdCall(MockClient):
    """Behaves normally, then raises a fatal error (like a revoked key)."""

    def __init__(self, *args):
        super().__init__(*args)
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        if self.calls >= 3:
            raise FatalClientError("AuthenticationError: simulated bad key")
        return super().complete(request)


def test_fatal_error_stops_run_and_keeps_partial_data(config, stim_key, tmp_path):
    one_worker = dataclasses.replace(config, workers=1)
    client = FatalOnThirdCall(one_worker, "normal", stim_key)
    with pytest.raises(FatalClientError, match="stopped early"):
        run_experiment(one_worker, "main", client, dry_run=True, n_agents=10, echo=False, out_dir=tmp_path)
    csv = next(tmp_path.glob("*.csv"))
    assert len(pd.read_csv(csv)) == 2  # the two agents that finished are saved
    assert "ABORTED" in next(tmp_path.glob("*_run.log")).read_text(encoding="utf-8")
    assert client.calls == 3  # no further calls after the fatal error


def test_live_run_refuses_mock_client(config, stim_key, tmp_path):
    with pytest.raises(ConfigError, match="cannot use the MockClient"):
        run_experiment(config, "smoke", MockClient(config, "normal", stim_key), dry_run=False,
                       echo=False, out_dir=tmp_path)


def test_live_run_refuses_unsigned_config(config, stim_key, tmp_path):
    unsigned = dataclasses.replace(config, signed_off=False)
    with pytest.raises(ConfigError, match="not signed off"):
        run_experiment(unsigned, "smoke", MockClient(unsigned, "normal", stim_key), dry_run=False,
                       echo=False, out_dir=tmp_path)


# ---------------------------------------------------------------------------
# The real OpenAI client, against a fake server (no network, no cost)
# ---------------------------------------------------------------------------

GOOD = '{"screen_size": 15, "attention_getting": 5, "capture_attention": 4, "arousal": 6, "mood": 5}'


class FakeResponses:
    """Records each request; can reject temperature on the first call."""

    def __init__(self, reject_temperature=False):
        self.calls = []
        self.reject_temperature = reject_temperature

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_temperature and "temperature" in kwargs:
            response = httpx2.Response(400, request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))
            raise openai.BadRequestError("Unsupported parameter: 'temperature' is not supported with this model.",
                                         response=response, body=None)
        usage = SimpleNamespace(input_tokens=3000, output_tokens=40)
        return SimpleNamespace(output_text=GOOD, id="resp_fake", usage=usage, status="completed",
                               incomplete_details=None)


def fake_client(config, monkeypatch, reject_temperature=False):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    client = OpenAIClient(config)
    fake = FakeResponses(reject_temperature)
    client._client = SimpleNamespace(responses=fake)
    return client, fake


def make_request(config, stim_key, diagnostic=False):
    from gp4.config import STIMULI_DIR
    from gp4.prompts import assemble_prompt

    prompt = assemble_prompt(config, "female", diagnostic)
    image = (STIMULI_DIR / stim_key["high"]["file"]).read_bytes()
    return LLMRequest("T001", 1, prompt.system_text, prompt.user_text, image, "image/png", diagnostic)


def test_openai_request_layout(config, stim_key, monkeypatch):
    client, fake = fake_client(config, monkeypatch)
    result = client.complete(make_request(config, stim_key))
    sent = fake.calls[0]
    system_msg, user_msg = sent["input"]
    assert system_msg["role"] == "system"
    parts = user_msg["content"]
    assert [p["type"] for p in parts] == ["input_image", "input_text"]  # ONE image, BEFORE the text
    assert parts[0]["image_url"].startswith("data:image/png;base64,")
    assert parts[0]["detail"] == "low"
    everything_text = json.dumps(sent).lower()
    for leak in ("stim_a", "stim_b", ".png\"", "saturation", "high-saturation"):
        assert leak not in everything_text.replace("data:image/png", "")
    assert sent["model"] == "gpt-4o-mini" and sent["temperature"] == 1.0 and sent["store"] is False
    assert sent["text"]["format"]["strict"] is True
    assert "previous_response_id" not in sent and "conversation" not in sent
    assert result.raw_text == GOOD and result.temperature_sent == 1.0 and result.input_tokens == 3000


def test_temperature_rejected_is_dropped_and_noted(config, stim_key, monkeypatch):
    client, fake = fake_client(config, monkeypatch, reject_temperature=True)
    result = client.complete(make_request(config, stim_key))
    assert len(fake.calls) == 2 and "temperature" not in fake.calls[1]
    assert result.temperature_sent is None and result.raw_text == GOOD
    assert "rejected the temperature parameter" in client.temperature_note


def test_schema_enforces_original_scales():
    schema = build_json_schema(arousal_max=9, diagnostic=False)
    props = schema["properties"]
    assert props["screen_size"]["enum"] == list(range(10, 21))
    assert props["attention_getting"]["enum"] == list(range(1, 8))
    assert props["arousal"]["enum"] == list(range(1, 10))
    assert schema["additionalProperties"] is False and len(schema["required"]) == 5
    assert "explanation" in build_json_schema(9, diagnostic=True)["required"]


def test_fatal_error_with_parallel_workers_stops_quickly(config, stim_key, tmp_path):
    """With 4 workers, at most the calls already in flight finish; the rest never start."""
    client = FatalOnThirdCall(config, "normal", stim_key)
    with pytest.raises(FatalClientError):
        run_experiment(config, "main", client, dry_run=True, n_agents=40, echo=False, out_dir=tmp_path)
    assert client.calls <= 3 + (config.workers - 1)
