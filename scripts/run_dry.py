"""
run_dry.py: run the whole experiment with MOCK answers. No API calls, no cost.

Where it fits
-------------
Tests the pipeline end to end (roster, prompts, retries, validation, file
writing) before any money is spent. Output goes to data/mock/, which Git
ignores, and every row carries dry_run = True. Mock data is NEVER results.

How to run (from the project folder, with .venv active)
-------------------------------------------------------
    python scripts/run_dry.py                              # main run size (77), mixed behaviours
    python scripts/run_dry.py --scenario normal            # clean random answers
    python scripts/run_dry.py --scenario identical         # every agent answers the same
    python scripts/run_dry.py --scenario out_of_range      # forces retries
    python scripts/run_dry.py --scenario code_fenced       # answers wrapped in ```json fences
    python scripts/run_dry.py --scenario api_failure       # first call fails, retry succeeds
    python scripts/run_dry.py --scenario always_fail       # agents end invalid
    python scripts/run_dry.py --run-label diagnostic       # adds the explanation field
    python scripts/run_dry.py --n 12                       # quick run with 12 agents

What goes in and out
--------------------
In:  config/config_v1.json, prompts/v1/, stimuli/.
Out: data/mock/gp4_<label>_<run_id>.csv, _raw.jsonl, _config.json, _run.log,
     and a short summary plus the first rows printed to the screen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make "import gp4" work when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from gp4.config import RUN_LABELS, load_config, verify_stimuli  # noqa: E402
from gp4.llm_client import MOCK_SCENARIOS, MockClient  # noqa: E402
from gp4.run_experiment import run_experiment  # noqa: E402

PREVIEW_COLUMNS = ["agent_id", "condition", "stim_file", "gender", "screen_size", "attention_getting",
                   "capture_attention", "attention", "arousal", "mood", "valid", "attempts", "prompt_sha", "dry_run"]


def main() -> None:
    """Parse arguments, run the mock experiment, print a summary."""
    parser = argparse.ArgumentParser(description="Dry run with mock answers (no API calls).")
    parser.add_argument("--run-label", choices=RUN_LABELS, default="main")
    parser.add_argument("--scenario", choices=MOCK_SCENARIOS, default="mixed")
    parser.add_argument("--n", type=int, default=None, help="override the number of agents (optional)")
    parser.add_argument("--quiet", action="store_true", help="do not echo the log to the screen")
    args = parser.parse_args()

    config = load_config()
    client = MockClient(config, args.scenario, verify_stimuli())
    out = run_experiment(config, args.run_label, client, dry_run=True, n_agents=args.n, echo=not args.quiet)

    frame = pd.read_csv(out.csv_path)
    print()
    print("=" * 30, "MOCK DATA, NOT RESULTS", "=" * 30)
    print(f"Scenario: {args.scenario} | agents: {out.n_agents} | valid: {out.n_valid} | "
          f"needed a retry: {out.n_retried} | total calls: {out.total_attempts}")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(frame[PREVIEW_COLUMNS].head(8).to_string(index=False))
    print(f"\nFiles written to {out.csv_path.parent}:")
    for path in (out.csv_path, out.jsonl_path, out.config_path, out.log_path):
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
