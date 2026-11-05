"""
test_costs_live.py: cost estimates and the live-run confirmation step (no network, no cost).

Why this exists
---------------
Before money is spent, the estimate must be right and the run must not start
without the exact confirmation phrase.
"""

import json
from pathlib import Path
import sys

import pytest

from gp4.config import PROJECT_ROOT, load_config
from gp4.costs import actual_cost, estimate_run, load_pricing, price
from gp4.prompts import assemble_prompt

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import run_live  # noqa: E402


@pytest.fixture(scope="module")
def config():
    return load_config()


def test_pricing_file_has_the_configured_model(config):
    prices = load_pricing(config.model)
    assert prices["input_usd_per_million"] == 0.15 and prices["image_tokens_low_detail"] == 2833


def test_estimate_is_dominated_by_the_image(config):
    p = assemble_prompt(config, "female")
    est = estimate_run(config, p.system_text, p.user_text, 4, diagnostic=False)
    assert 2833 < est.input_tokens_per_call < 3500
    assert est.max_calls == 4 * config.max_attempts
    assert est.expected_usd == pytest.approx(4 * price(load_pricing(config.model), est.input_tokens_per_call, 40))
    assert est.expected_usd < 0.01 and est.max_usd == pytest.approx(3 * est.expected_usd)


def test_actual_cost_counts_every_attempt(tmp_path, config):
    log = tmp_path / "x_raw.jsonl"
    records = [{"attempt_log": [{"input_tokens": 3000, "output_tokens": 40},
                                {"input_tokens": 3000, "output_tokens": 40}]},
               {"attempt_log": [{"input_tokens": None, "output_tokens": None}]}]
    log.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    cost = actual_cost(log, config.model)
    assert cost["calls"] == 3 and cost["input_tokens"] == 6000
    assert cost["usd"] == pytest.approx((6000 * 0.15 + 80 * 0.60) / 1e6)


@pytest.mark.parametrize("typed,earlier,ok", [
    ("smoke", [], True), ("yes", [], False), ("", [], False), ("SMOKE", [], False),
    ("smoke", [Path("gp4_smoke_old.csv")], False), ("smoke again", [Path("gp4_smoke_old.csv")], True),
])
def test_confirmation_phrase(monkeypatch, typed, earlier, ok):
    monkeypatch.setattr("builtins.input", lambda _prompt: typed)
    assert run_live.confirm("smoke", earlier) is ok


def test_no_input_cancels(monkeypatch):
    def raise_eof(_prompt):
        raise EOFError
    monkeypatch.setattr("builtins.input", raise_eof)
    assert run_live.confirm("main", []) is False
