"""
costs.py: estimate the cost of a live run before it starts, and report the real cost after.

Where it fits
-------------
Used by scripts/run_live.py. Before any money is spent, it prints the
expected and worst-case cost; afterwards it adds up the tokens actually used
(every attempt, from the *_raw.jsonl log) and prices them.

What goes in and out
--------------------
In:  config/pricing.json (prices and image token cost), the Config, the
     assembled prompt, and the number of agents.
Out: a CostEstimate (tokens and US dollars), or the actual cost of a finished run.

Honesty about precision
-----------------------
Text tokens are estimated (about 4 characters per token). The image cost is
exact per OpenAI's documentation (a flat token count at low detail). The
estimate is a planning figure; the actual cost comes from the API's own
token counts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gp4.config import CONFIG_DIR, Config, ConfigError

PRICING_PATH: Path = CONFIG_DIR / "pricing.json"
SCHEMA_OVERHEAD_TOKENS = 150   # JSON schema and message formatting (estimate)
OUTPUT_TOKENS_MAIN = 40        # five integers in JSON
OUTPUT_TOKENS_DIAGNOSTIC = 120 # plus a two- or three-sentence explanation


@dataclass(frozen=True)
class CostEstimate:
    """Planning figures for one run."""

    n_agents: int
    input_tokens_per_call: int
    output_tokens_per_call: int
    expected_calls: int
    max_calls: int
    expected_usd: float
    max_usd: float


def load_pricing(model: str) -> dict[str, Any]:
    """Prices for one model from config/pricing.json; fails helpfully if missing."""
    data = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    if model not in data["models"]:
        raise ConfigError(
            f"No price for model {model!r} in {PRICING_PATH.name}.\n"
            f"Fix: add its prices (from the OpenAI pricing page) before a live run."
        )
    return {**data["models"][model], "checked_on": data["checked_on"], "sources": data["sources"]}


def image_tokens(prices: dict[str, Any], image_detail: str) -> int:
    """Tokens charged for one image at the configured detail (auto treated as the higher figure)."""
    if image_detail == "low":
        return int(prices["image_tokens_low_detail"])
    return int(prices["image_tokens_high_detail_one_tile"])  # high, or auto (worst case)


def estimate_run(config: Config, system_text: str, user_text: str, n_agents: int, diagnostic: bool) -> CostEstimate:
    """Expected cost (one call per agent) and worst case (every agent uses every attempt)."""
    prices = load_pricing(config.model)
    text_tokens = (len(system_text) + len(user_text)) // 4 + SCHEMA_OVERHEAD_TOKENS
    input_per_call = text_tokens + image_tokens(prices, config.image_detail)
    output_per_call = OUTPUT_TOKENS_DIAGNOSTIC if diagnostic else OUTPUT_TOKENS_MAIN
    per_call_usd = price(prices, input_per_call, output_per_call)
    max_calls = n_agents * config.max_attempts
    return CostEstimate(n_agents, input_per_call, output_per_call, n_agents, max_calls,
                        n_agents * per_call_usd, max_calls * per_call_usd)


def price(prices: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    """US dollars for a given number of input and output tokens."""
    return (input_tokens * prices["input_usd_per_million"] + output_tokens * prices["output_usd_per_million"]) / 1e6


def actual_cost(jsonl_path: Path, model: str) -> dict[str, Any]:
    """Add up tokens from EVERY attempt in a run's JSONL log and price them.

    Failed calls that returned no usage count as zero tokens (OpenAI does not
    charge for requests that fail before processing).
    """
    prices = load_pricing(model)
    input_total = output_total = calls = 0
    for line in Path(jsonl_path).read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for attempt in record.get("attempt_log", []):
            calls += 1
            input_total += attempt.get("input_tokens") or 0
            output_total += attempt.get("output_tokens") or 0
    return {"calls": calls, "input_tokens": input_total, "output_tokens": output_total,
            "usd": price(prices, input_total, output_total), "prices_checked_on": prices["checked_on"]}
