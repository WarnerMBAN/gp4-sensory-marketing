"""
show_prompt.py: print the exact prompt one agent would receive. No API call.

Where it fits
-------------
An inspection tool. Use it to review the wording before a live run, or to
copy the exact text into the report or slides.

How to run (from the project folder, with .venv active)
-------------------------------------------------------
    python scripts/show_prompt.py                      # agent 1 of the main run
    python scripts/show_prompt.py --agent 5            # agent 5 of the main run
    python scripts/show_prompt.py --run-label diagnostic --agent 1

What goes in and out
--------------------
In:  config/config_v1.json, prompts/v1/, stimuli/stimulus_key.json.
Out: printed to the screen: the agent's assignment (for YOUR eyes only; the
     model never sees the condition or file name), the system text, where
     the image goes, the user text, and the prompt hash.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make "import gp4" work when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gp4.agents import build_roster  # noqa: E402
from gp4.config import RUN_LABELS, load_config, verify_stimuli  # noqa: E402
from gp4.prompts import assemble_prompt  # noqa: E402

RULE = "-" * 78


def main() -> None:
    """Parse arguments, build the roster, and print one agent's prompt."""
    parser = argparse.ArgumentParser(description="Show the exact prompt one agent receives.")
    parser.add_argument("--run-label", choices=RUN_LABELS, default="main")
    parser.add_argument("--agent", type=int, default=1, help="agent number within the run (1 = first)")
    args = parser.parse_args()

    config = load_config()
    roster = build_roster(config, args.run_label, verify_stimuli())
    if not 1 <= args.agent <= len(roster):
        sys.exit(f"--agent must be between 1 and {len(roster)} for the {args.run_label} run.")
    agent = roster[args.agent - 1]
    prompt = assemble_prompt(config, agent.gender, diagnostic=(args.run_label == "diagnostic"))

    print(RULE)
    print(f"AGENT {agent.agent_id}  (run: {agent.run_label}, config {config.config_version}, "
          f"prompt {config.prompt_version})")
    print(f"  Assignment, NOT sent to the model: condition={agent.condition}, "
          f"image={agent.stim_file}, persona gender={agent.gender or '(none)'}")
    print(RULE)
    print("[SYSTEM TEXT]")
    print(prompt.system_text)
    print(RULE)
    print(f"[USER MESSAGE, part 1: IMAGE]  {agent.stim_file} sent as base64, "
          f"detail={config.image_detail}, sha256={agent.stim_sha256[:12]}...")
    print("[USER MESSAGE, part 2: TEXT]")
    print(prompt.user_text)
    print(RULE)
    print(f"prompt_sha (stored on the data row): {prompt.prompt_sha}")
    print(f"full SHA-256: {prompt.prompt_sha_full}")
    print(RULE)


if __name__ == "__main__":
    main()
