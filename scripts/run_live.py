"""
run_live.py: run the experiment with REAL API calls. Spends money; asks first.

Where it fits
-------------
The only entry point that calls the model. Uses the same engine as the dry
run (src/gp4/run_experiment.py) with the real OpenAI client.

How to run (from the project folder, with .venv active and the key in .env)
---------------------------------------------------------------------------
    python scripts/run_live.py --run-label smoke --plan-only   # show plan and cost, no calls
    python scripts/run_live.py --run-label smoke               # 4 agents
    python scripts/run_live.py --run-label main                # 77 agents (39 high, 38 low)
    python scripts/run_live.py --run-label diagnostic          # 20 agents, with explanations
    python scripts/run_live.py --run-label robustness          # 823 agents (replication scale)

Safeguards (in this order)
--------------------------
1. Settings, prompt files and images are verified; the config must be signed off.
2. The API key must be present (it is never printed).
3. The plan is printed: model, settings, number of agents and calls, estimated
   cost (expected and worst case), and where the output goes.
4. If a live run with this label already exists, it is listed. Running again
   is allowed but must be justified: the first run is the one to report unless
   a reason is recorded in CHANGELOG.md (no picking the "best" run).
5. You must type the run label (or "<label> again") to start. Anything else cancels.

What goes in and out
--------------------
In:  config/config_v1.json, config/pricing.json, prompts/v1/, stimuli/, .env.
Out: data/real/gp4_<label>_<run_id>.csv, _raw.jsonl, _config.json, _run.log;
     the actual tokens and cost printed at the end.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make "import gp4" work when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from gp4.agents import build_roster  # noqa: E402
from gp4.config import DATA_DIR, RUN_LABELS, ConfigError, load_config, require_sign_off, verify_stimuli  # noqa: E402
from gp4.costs import actual_cost, estimate_run, image_tokens, load_pricing  # noqa: E402
from gp4.llm_client import FatalClientError, OpenAIClient, get_api_key  # noqa: E402
from gp4.prompts import assemble_prompt  # noqa: E402
from gp4.run_experiment import run_experiment  # noqa: E402

RULE = "=" * 78


def existing_runs(run_label: str) -> list[Path]:
    """Earlier live runs with the same label (analysis outputs excluded)."""
    folder = DATA_DIR / "real"
    return sorted(p for p in folder.glob(f"gp4_{run_label}_*.csv") if not p.stem.endswith("_comparison"))


def print_plan(config, run_label: str) -> None:
    """STEP 3: show exactly what will happen and what it should cost."""
    roster = build_roster(config, run_label, verify_stimuli())
    n_high = sum(a.condition == "high" for a in roster)
    diagnostic = run_label == "diagnostic"
    prompt = assemble_prompt(config, "female", diagnostic)
    estimate = estimate_run(config, prompt.system_text, prompt.user_text, len(roster), diagnostic)
    prices = load_pricing(config.model)
    print(RULE)
    print(f"LIVE RUN PLAN: {run_label.upper()}  (real API calls, real cost)")
    print(RULE)
    print(f"  Model:            {config.model}   [{prices.get('status_note', '')}]")
    print(f"  Temperature:      {config.temperature}  (dropped automatically if the model rejects it)")
    print(f"  Image detail:     {config.image_detail}  (about {estimate.input_tokens_per_call:,} input tokens per call, "
          f"of which the image is {image_tokens(prices, config.image_detail):,})")
    print(f"  Prompt:           {config.prompt_version}  (config {config.config_version}, signed off by "
          f"{config.signed_off_by} on {config.signed_off_date})")
    print(f"  Agents:           {len(roster)}  ({n_high} high, {len(roster) - n_high} low), persona {config.persona_mode}, "
          f"seed {config.seed}")
    print(f"  Calls:            {estimate.expected_calls} expected; at most {estimate.max_calls} "
          f"(up to {config.max_attempts} attempts per agent)")
    print(f"  Estimated cost:   about ${estimate.expected_usd:.4f}; at most ${estimate.max_usd:.4f}  "
          f"(prices checked {prices['checked_on']})")
    print(f"  Output folder:    data/real/")
    if run_label == "robustness":
        print("  NOTE: robustness run (replication scale). Always report it as robustness, separate from main.")
    print(RULE)


def confirm(run_label: str, earlier: list[Path]) -> bool:
    """STEPS 4-5: ask the user to type the label (or '<label> again' if a run already exists)."""
    phrase = run_label
    if earlier:
        print(f"WARNING: {len(earlier)} live '{run_label}' run(s) already exist:")
        for path in earlier:
            print(f"   {path.name}")
        print("The FIRST run is the one to report. Run again only for a reason you will record in CHANGELOG.md.")
        phrase = f"{run_label} again"
    try:
        answer = input(f'Type "{phrase}" to start, or anything else to cancel: ').strip()
    except EOFError:
        answer = ""
    return answer == phrase


def report(out, model: str) -> None:
    """After the run: parse rate, a look at the answers, real tokens and cost."""
    frame = pd.read_csv(out.csv_path)
    cost = actual_cost(out.jsonl_path, model)
    print(RULE)
    print(f"DONE: {out.n_valid} of {out.n_agents} agents valid ({100 * out.n_valid / max(out.n_agents, 1):.0f}% "
          f"parse rate); {out.n_retried} needed a retry; {cost['calls']} calls.")
    print(f"Actual tokens: {cost['input_tokens']:,} input, {cost['output_tokens']:,} output. "
          f"Actual cost: about ${cost['usd']:.4f} (at prices checked {cost['prices_checked_on']}).")
    columns = ["agent_id", "condition", "gender", "screen_size", "attention_getting", "capture_attention",
               "arousal", "mood", "valid", "attempts", "temperature", "input_tokens", "output_tokens"]
    with pd.option_context("display.width", 200):
        print(frame[columns].to_string(index=False))
    print(f"\nFiles: {out.csv_path.name} (+ _raw.jsonl, _config.json, _run.log) in data/real/")
    print(f"Next: python scripts/analyze.py data/real/{out.csv_path.name}")
    print(RULE)


def main() -> None:
    """Verify, plan, confirm, run, report."""
    parser = argparse.ArgumentParser(description="Live run with real API calls (asks for confirmation).")
    parser.add_argument("--run-label", choices=RUN_LABELS, required=True)
    parser.add_argument("--plan-only", action="store_true", help="show the plan and cost estimate; make no calls")
    args = parser.parse_args()

    try:
        config = load_config()            # STEP 1: settings, prompts, images verified
        require_sign_off(config)
        get_api_key()                     # STEP 2: key present (never printed)
    except ConfigError as err:
        sys.exit(f"Cannot start: {err}")

    print_plan(config, args.run_label)    # STEP 3
    if args.plan_only:
        print("Plan only: no API calls were made.")
        return
    if not confirm(args.run_label, existing_runs(args.run_label)):  # STEPS 4-5
        print("Cancelled. No API calls were made.")
        return

    client = OpenAIClient(config)
    try:
        out = run_experiment(config, args.run_label, client, dry_run=False)
    except FatalClientError as err:
        sys.exit(f"STOPPED: {err}\nPartial results (if any) are in data/real/. Nothing was overwritten.")
    if client.temperature_note:
        print("NOTE:", client.temperature_note)
    report(out, config.model)


if __name__ == "__main__":
    main()
