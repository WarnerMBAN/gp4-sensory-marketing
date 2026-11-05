"""
analyze.py: run the full analysis on a saved run CSV; write tables, figures and a summary.

Where it fits
-------------
After a run (dry or live). Re-running it on the same CSV always gives the same
tables, figures and numbers (the bootstrap is seeded from the config).

How to run (from the project folder, with .venv active)
-------------------------------------------------------
    python scripts/analyze.py data/real/gp4_main_<run_id>.csv
    python scripts/analyze.py --latest real        # newest live main run
    python scripts/analyze.py --latest mock        # newest dry-run main run

What goes in and out
--------------------
In:  one run CSV and config/config_v1.json.
Out (live data):   data/real/<stem>_comparison.csv and reports/figures/<stem>_fig*.png,
                   plus data/real/<stem>_analysis/ with every table and summary.md.
Out (mock data):   everything goes to data/mock/<stem>_analysis/ (git-ignored),
                   so mock figures can never end up in the report folder.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make "import gp4" work when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from gp4.analysis import analyze, load_results, summary_lines  # noqa: E402
from gp4.config import DATA_DIR, PROJECT_ROOT, load_config  # noqa: E402
from gp4.plots import save_report_figures  # noqa: E402

FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"


def latest_csv(kind: str, run_label: str) -> Path:
    """Newest gp4_<label>_*.csv in data/real or data/mock (analysis tables excluded)."""
    folder = DATA_DIR / kind
    candidates = sorted(p for p in folder.glob(f"gp4_{run_label}_*.csv") if not p.stem.endswith("_comparison"))
    if not candidates:
        sys.exit(f"No gp4_{run_label}_*.csv found in {folder}. Run an experiment first.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def to_jsonable(value):
    """Make numpy numbers, tuples and NaN safe for JSON (NaN becomes null)."""
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


def main() -> None:
    """Parse arguments, analyse, write outputs, print the summary."""
    parser = argparse.ArgumentParser(description="Analyse a GP4 run CSV.")
    parser.add_argument("csv", nargs="?", help="path to a run CSV")
    parser.add_argument("--latest", choices=("real", "mock"), help="use the newest run in data/real or data/mock")
    parser.add_argument("--run-label", default="main", help="with --latest: which run label (default main)")
    args = parser.parse_args()
    if not args.csv and not args.latest:
        parser.error("give a CSV path or --latest real|mock")

    csv_path = (Path(args.csv) if args.csv else latest_csv(args.latest, args.run_label)).resolve()
    config = load_config()
    frame = load_results(csv_path)
    result = analyze(frame, config)
    is_mock = result.quality["is_mock"]
    stem = csv_path.stem

    # Mock outputs stay inside data/mock; real outputs go to the report folders.
    tables_dir = csv_path.parent / f"{stem}_analysis"
    figures_dir = tables_dir if is_mock else FIGURES_DIR
    tables_dir.mkdir(parents=True, exist_ok=True)

    result.descriptives.to_csv(tables_dir / "descriptives.csv", index=False)
    result.anova.to_csv(tables_dir / "anova.csv", index=False)
    result.reading.to_csv(tables_dir / "plain_reading.csv", index=False)
    result.comparison.to_csv(tables_dir / "comparison.csv", index=False)
    if not is_mock:
        result.comparison.to_csv(csv_path.parent / f"{stem}_comparison.csv", index=False)
    details = {"quality": result.quality, "tost_size": result.tost_size, "mood_placebo": result.mood,
               "outcome": result.outcome, "mediation": result.mediation, "settings": result.settings,
               "source_csv": csv_path.name}
    (tables_dir / "details.json").write_text(json.dumps(to_jsonable(details), indent=2), encoding="utf-8")
    lines = summary_lines(result)
    (tables_dir / "summary.md").write_text(
        f"# Analysis summary: {csv_path.name}\n\n" + "\n".join(f"- {l}" for l in lines) + "\n", encoding="utf-8")
    figure_paths = save_report_figures(frame, result, figures_dir, stem)

    print("\n".join(lines))
    with pd.option_context("display.width", 200, "display.max_colwidth", 90):
        print("\nPlain-English reading:")
        print(result.reading.to_string(index=False))
    print(f"\nTables: {tables_dir.relative_to(PROJECT_ROOT)}")
    print(f"Figures ({len(figure_paths)}): {figures_dir.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
