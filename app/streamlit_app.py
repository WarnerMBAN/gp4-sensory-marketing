"""
streamlit_app.py: the GP4 dashboard (visual aid for the 12-minute presentation).

Where it fits
-------------
The last step. Reads saved run CSVs (data/real or data/mock), analyses them
with gp4.analysis (cached), and shows the results with gp4.plots. It NEVER
calls the API: the optional "Run experiment" page stays hidden unless
enable_run_page is true in the config (default false).

How to run (from the project folder, with .venv active)
-------------------------------------------------------
    streamlit run app/streamlit_app.py
Then open the address it prints (usually http://localhost:8501).

Pages (follow the presentation and the grading rubric)
------------------------------------------------------
  1. Overview              research question, context, headline answer
  2. Original study        design, the two stimuli, human benchmarks
  3. AI-agent system       how agents are built, exact prompt, settings, deviations
  4. Results               each measure by condition, tests, data quality
  5. Human vs AI           forest plot, Fisher-z tests, TOST, plain reading
  6. Explore data          filterable table, CSV download, variable dictionary
  7. Limitations           what to be careful about
  (8. Run experiment       hidden by default)

Mock data
---------
Whenever the selected file contains dry-run rows, a red "MOCK DATA, NOT
RESULTS" banner appears at the top of every page and every chart title.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gp4.analysis import MEASURE_LABELS, AnalysisResult, analyze, load_results  # noqa: E402
from gp4.benchmarks import MEDIATION_ORIGINAL, MOOD_ORIGINAL, ORIGINAL, REPLICATION, SAMPLES  # noqa: E402
from gp4.config import DATA_DIR, STIMULI_DIR, Config, load_config, load_stimulus_key  # noqa: E402
from gp4.llm_client import build_json_schema  # noqa: E402
from gp4.plots import (  # noqa: E402
    CAPTIONS,
    distribution_plotly,
    forest_plotly,
    size_histogram_plotly,
)
from gp4.prompts import assemble_prompt  # noqa: E402

st.set_page_config(page_title="GP4: Colour saturation and AI agents", layout="wide")

PAGES = ["1. Overview", "2. Original study", "3. AI-agent system", "4. Results", "5. Human vs AI",
         "6. Explore data", "7. Limitations"]
# Where run CSVs are read from. GP4_DASHBOARD_DATA lets the automated tests point
# the dashboard at a temporary folder; normally it is the project's data/ folder.
DATA_ROOT = Path(os.environ.get("GP4_DASHBOARD_DATA", str(DATA_DIR)))
MOCK_BANNER = ("MOCK DATA, NOT RESULTS. The selected file comes from a dry run with fake answers. "
               "Nothing on this page may be reported as a finding.")


# ==========================================================================
# Data loading (cached)
# ==========================================================================

@dataclass
class Context:
    """Everything a page needs about the selected run."""

    config: Config
    path: Path
    frame: pd.DataFrame
    result: AnalysisResult
    snapshot: dict[str, Any]

    @property
    def is_mock(self) -> bool:
        return bool(self.result.quality["is_mock"])


@st.cache_resource
def get_config() -> Config:
    """Load and verify the settings once per server."""
    return load_config()


def primary_main(folder: Path) -> Path | None:
    """The FIRST main run in a folder: by the pre-set rule, the one to report."""
    mains = sorted(p for p in folder.glob("gp4_main_*.csv") if not p.stem.endswith("_comparison"))
    return mains[0] if mains else None  # file names sort by run time (YYYYMMDD_HHMMSS)


def list_runs() -> list[Path]:
    """All run CSVs: real before mock. Within each: the primary (first) main run,
    then other main runs, then everything else, newest first.

    Why: the dashboard must open on the result being reported, not on a newer
    repeat run or a 4-agent smoke test.
    """
    runs: list[Path] = []
    for kind in ("real", "mock"):
        folder = DATA_ROOT / kind
        if folder.is_dir():
            found = [p for p in folder.glob("gp4_*.csv") if not p.stem.endswith("_comparison")]
            primary = primary_main(folder)
            newest_first = sorted(found, key=lambda p: p.stem, reverse=True)
            ranked = sorted(newest_first, key=lambda p: (p != primary, not p.stem.startswith("gp4_main_")))
            runs += ranked  # stable sort keeps newest-first within each group
    return runs


def run_label_for(path: Path) -> str:
    """Readable label for the file picker, e.g. 'REAL | main | 2026-11-05 17:26'."""
    kind = "REAL" if path.parent.name == "real" else "MOCK"
    parts = path.stem.split("_")  # gp4, label, YYYYMMDD, HHMMSS
    try:
        when = datetime.strptime(parts[2] + parts[3], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except (IndexError, ValueError):
        when = path.stem
    role = ""
    if parts[1:2] == ["main"] and kind == "REAL":
        role = " | PRIMARY" if path == primary_main(path.parent) else " | repeat (not the primary result)"
    return f"{kind} | {parts[1] if len(parts) > 1 else '?'} | {when}{role}"


@st.cache_data(show_spinner="Analysing the selected run...")
def load_and_analyze(path_text: str, modified: float) -> tuple[pd.DataFrame, AnalysisResult]:
    """Read and analyse one CSV. Cached; 'modified' makes the cache refresh if the file changes."""
    frame = load_results(path_text)
    return frame, analyze(frame, get_config())


def load_snapshot(path: Path) -> dict[str, Any]:
    """The run's _config.json (settings and prompt variants), if present."""
    snap = path.with_name(path.stem + "_config.json")
    return json.loads(snap.read_text(encoding="utf-8")) if snap.is_file() else {}


# ==========================================================================
# Formatting helpers
# ==========================================================================

def fmt(value: Any, digits: int = 2, signed: bool = False) -> str:
    """Number as text; blanks, NaN and infinity become 'n/a'."""
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "n/a"
    return f"{number:+.{digits}f}" if signed else f"{number:.{digits}f}"


def fmt_p(p: Any) -> str:
    """p-value as text, '< .001' for tiny values."""
    if p is None or (isinstance(p, float) and not math.isfinite(p)):
        return "n/a"
    return "< .001" if p < 0.001 else f"{p:.3f}"


def ci_text(low: Any, high: Any, digits: int = 2) -> str:
    """'[low, high]' or 'n/a' when undefined."""
    if fmt(low) == "n/a":
        return "n/a"
    return f"[{fmt(low, digits, True)}, {fmt(high, digits, True)}]"


def chart(fig, caption_key: str) -> None:
    """Show a Plotly chart with its plain-English caption underneath."""
    st.plotly_chart(fig, width="stretch")
    st.caption("What this shows: " + CAPTIONS[caption_key])


def provenance(ctx: Context) -> None:
    """One line saying exactly which data the page is showing."""
    q = ctx.result.quality
    st.caption(f"Data: `{ctx.path.name}` ({'MOCK' if ctx.is_mock else 'REAL'}) | run label: "
               f"{', '.join(q['run_labels'])} | {q['n_agents']} agents, {q['n_valid']} valid | model: "
               f"{', '.join(q['models'])} | prompt_sha: {', '.join(q['prompt_shas'])}")


# ==========================================================================
# Page 1: Overview
# ==========================================================================

def page_overview(ctx: Context) -> None:
    """Research question, marketing context and the headline answer."""
    st.title("Can AI agents see what people see?")
    st.subheader("Colour saturation and perceived product size: Hagtvedt and Brasel (2017), Study 3")
    st.markdown(
        "**Research question.** To what extent can AI agents reproduce the human perceptions, preferences "
        "and sensory marketing effects observed in the original experiment?\n\n"
        "**Marketing context.** Product colour is a cheap, controllable design choice. Hagtvedt and Brasel "
        "found that the *same* laptop looked bigger when its red was more saturated (more vivid), because "
        "saturated colour raises arousal, which draws attention, which inflates perceived size. If true, "
        "colour saturation is a lever for packaging, product design and online product images, and it can "
        "backfire when a product should look small. A large replication (Motoki and Iseki 2022, n = 823) "
        "found the attention and arousal effects but **not** the size effect. We ask whether AI agents, "
        "increasingly proposed as stand-ins for consumer panels, show either pattern."
    )
    outcome = ctx.result.outcome
    left, right = st.columns([1, 2])
    with left:
        st.metric("AI outcome", f"Pattern {outcome['label']}", border=True)
        st.caption(outcome["name"])
    with right:
        rows = []
        for measure in ("size", "attention", "arousal"):
            ai = ctx.result.anova.set_index("measure").loc[measure]
            rows.append({
                "Measure": measure.capitalize(),
                "Original r": f"{ORIGINAL[measure].r_published:+.3f}",
                "Replication r": f"{REPLICATION[measure].r_published:+.3f}",
                "AI r [95% CI]": f"{fmt(ai.get('r'), 3, True)} {ci_text(ai.get('r_ci_low'), ai.get('r_ci_high'))}",
                "AI p": fmt_p(ai.get("p")),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("r is the effect of high vs low saturation (positive = higher for the more saturated laptop). "
                   "Original: all three effects. Replication: attention and arousal only.")
    with st.expander("How the outcome label is decided"):
        st.markdown(
            "- **A** full original pattern: size, attention and arousal all significantly higher for high saturation.\n"
            "- **B** replication pattern: attention and arousal higher, size not.\n"
            "- **C** blind to saturation: no significant effect on any of the three.\n"
            "- **D** exaggerated or halo: mood also differs (humans showed none), or an AI effect is "
            "significantly larger than the original's.\n"
            "- **Mixed**: any other pattern (for example a size effect alone, or an effect in the wrong direction).\n\n"
            "Reasons for this run:\n" + "\n".join(f"- {r}" for r in outcome["reasons"])
        )


# ==========================================================================
# Page 2: Original study
# ==========================================================================

def benchmark_table() -> pd.DataFrame:
    """Original and replication results side by side."""
    rows = []
    for measure in ("size", "attention", "arousal"):
        for source, bench in (("Original", ORIGINAL[measure]), ("Replication", REPLICATION[measure])):
            rows.append({
                "Measure": MEASURE_LABELS[measure] if not (source == "Replication" and measure == "arousal")
                else "Arousal (1-7 in the replication)",
                "Source": f"{source} (n = {bench.n_total})",
                "High M (SD)": f"{bench.high.mean:.2f} ({bench.high.sd:.2f})",
                "Low M (SD)": f"{bench.low.mean:.2f} ({bench.low.sd:.2f})",
                "F": f"F(1,{bench.df_error}) = {bench.f_value:g}",
                "p": bench.p_text,
                "r [95% CI]": f"{bench.r_published:.3f} [{bench.r_ci_published[0]:.3f}, {bench.r_ci_published[1]:.3f}]",
                "Partial eta-sq": f"{bench.eta_sq_published:g}",
            })
    rows.append({"Measure": "Mood (1-9, placebo)", "Source": "Original (n = 77)",
                 "High M (SD)": f"{MOOD_ORIGINAL['mean_high_assumed']} (n/r)",
                 "Low M (SD)": f"{MOOD_ORIGINAL['mean_low_assumed']} (n/r)", "F": "n/r",
                 "p": MOOD_ORIGINAL["p_text"], "r [95% CI]": "n/r", "Partial eta-sq": "n/r"})
    return pd.DataFrame(rows)


def page_original(ctx: Context) -> None:
    """Design, the two stimuli and the human benchmarks."""
    st.title("The original experiment")
    st.markdown(
        f"**Design.** Between-subjects: each participant saw **one** image of a red laptop, either high or low "
        f"in colour saturation (hue 356, value 70; saturation 100 vs 50). **Participants:** "
        f"{SAMPLES['original']['who']}, {SAMPLES['original']['n_analysed']} analysed. **Setting:** "
        f"{SAMPLES['original']['setting']}.\n\n"
        "**Measures, in order:** screen-size estimate (whole inches, 10 to 20); two attention items, "
        "\"The laptop is attention-getting\" and \"The laptop captures my attention\" (1 = Not at all, "
        "7 = Definitely; averaged); arousal and mood on the 9 x 9 affect grid (1 to 9 each)."
    )
    key = load_stimulus_key()
    left, right = st.columns(2)
    for column, condition in ((left, "high"), (right, "low")):
        with column:
            st.image(str(STIMULI_DIR / key[condition]["file"]), width=360,
                     caption=f"Condition: {condition} saturation ({key[condition]['file']})")
    st.caption("Condition labels are shown on this page only. The AI agents never see a label or file name.")
    st.subheader("Human results: two benchmarks that disagree")
    st.dataframe(benchmark_table(), hide_index=True, width="stretch")
    st.caption("n/r = not reported. Per-cell n assumed (39/38 original, 411/412 replication). 95% CIs for r "
               "from the replication paper's summary table. The replication measured arousal on a 7-point "
               "scale, so its arousal means are not comparable with 9-point answers; its r is. Mood means: "
               "the paper does not say which belongs to which condition (order assumed high, low).")
    st.subheader("Proposed mechanism (original only)")
    st.markdown(
        f"Saturation -> arousal -> attention -> perceived size ({MEDIATION_ORIGINAL['model']}). Total indirect "
        f"effect B = {MEDIATION_ORIGINAL['total_indirect_B']}, 95% CI "
        f"[{MEDIATION_ORIGINAL['total_indirect_CI95'][0]}, {MEDIATION_ORIGINAL['total_indirect_CI95'][1]}]. "
        "The replication skipped mediation because its size effect was not significant."
    )


# ==========================================================================
# Page 3: AI-agent system
# ==========================================================================

PIPELINE_DOT = """
digraph G {
  rankdir=LR; node [shape=box, style="rounded", fontname="Helvetica", fontsize=11, color="#52514e"];
  cfg [label="config_v1.json\\n(signed off)"]; roster [label="Roster\\n39 high / 38 low\\nseeded shuffle\\n49% male persona"];
  prompt [label="Prompt v1\\n(verbatim, hashed)"]; call [label="One fresh call per agent\\nsystem text + ONE image\\n+ task text"];
  model [label="gpt-4o-mini\\nJSON schema"]; check [label="Validate in Python\\nretry up to 3 tries"];
  data [label="CSV + JSONL log\\n+ config snapshot"]; analysis [label="Analysis vs\\nhuman benchmarks"];
  cfg -> roster -> call; prompt -> call; call -> model -> check -> data -> analysis;
  check -> call [label="invalid", style=dashed, fontsize=9];
}
"""


def page_system(ctx: Context) -> None:
    """How agents are generated, prompted, called, validated and recorded."""
    st.title("The AI-agent system")
    st.graphviz_chart(PIPELINE_DOT, width="stretch")
    st.caption("What this shows: the path from settings to data. Each agent is an independent call that sees "
               "exactly one image; nothing is shared between agents.")
    cfg = ctx.config
    settings = ctx.snapshot.get("settings", {}) or cfg.as_dict()
    temp_note = ctx.snapshot.get("temperature_note") or ""
    st.subheader("Settings for this run")
    table = pd.DataFrame([
        ("Model", ", ".join(ctx.result.quality["models"]) + (" (mock stand-in for " + cfg.model + ")" if ctx.is_mock else "")),
        ("Temperature", f"{settings.get('temperature')}" + (f" ({temp_note})" if temp_note else "")),
        ("Image", f"one PNG per call, base64, placed before the task text; detail = {settings.get('image_detail')}"),
        ("Persona", f"{settings.get('persona_mode')}: \"You are a male / female undergraduate university student.\" "
                    f"({int(cfg.pct_male * 100)}% male, balanced within each condition)"),
        ("Assignment", f"seeded shuffle (seed {settings.get('seed')}), as equal as possible (77 -> 39 high, 38 low)"),
        ("Validation", f"JSON schema of allowed integers; re-checked in Python; up to {settings.get('max_attempts')} "
                       "attempts; still-invalid agents kept with valid = False and excluded"),
        ("Prompt version / hash", f"{settings.get('prompt_version')} / {', '.join(ctx.result.quality['prompt_shas'])}"),
        ("Config sign-off", f"{cfg.signed_off_by}, {cfg.signed_off_date}" if cfg.signed_off else "NOT signed off"),
    ], columns=["Setting", "Value"])
    st.dataframe(table, hide_index=True, width="stretch")

    st.subheader("Exact prompt (version v1)")
    gender = st.radio("Persona variant to display", ["female", "male"], horizontal=True)
    prompt = assemble_prompt(cfg, gender)
    st.markdown("**System text**")
    st.code(prompt.system_text, language=None, wrap_lines=True)
    st.markdown("**User message:** [the image] then this text")
    st.code(prompt.user_text, language=None, wrap_lines=True)
    st.caption(f"prompt_sha for this variant: {prompt.prompt_sha}. The text never mentions colour, saturation, "
               "conditions, the hypothesis, the paper or a file name (checked in code before every call).")
    with st.expander("JSON schema sent with every call"):
        st.json(build_json_schema(cfg.arousal_max, diagnostic=False))
    with st.expander("Deviations from the original experiment (DEVIATIONS.md)", expanded=False):
        deviations = ROOT / "DEVIATIONS.md"
        st.markdown(deviations.read_text(encoding="utf-8") if deviations.is_file() else "DEVIATIONS.md not found.")


# ==========================================================================
# Page 4: Results
# ==========================================================================

def page_results(ctx: Context) -> None:
    """Each measure by condition, with its test, plus a data-quality panel."""
    st.title("AI results by measure")
    q = ctx.result.quality
    st.subheader("Data quality")
    cols = st.columns(5)
    cols[0].metric("Agents", q["n_agents"], border=True)
    cols[1].metric("Valid", f"{q['n_valid']} ({q['valid_rate']:.0%})", border=True)
    cols[2].metric("Needed a retry", q["n_retried"], border=True)
    cols[3].metric("API calls", q["total_calls"], border=True)
    cols[4].metric("Identical answer sets", f"{q['duplicate_answer_share']:.0%}", border=True,
                   help="Share of valid agents whose five answers exactly match another agent's.")
    st.caption(f"High {q['n_high_valid']} / low {q['n_low_valid']} valid agents. Screen sizes used: "
               f"{', '.join(str(v) for v in q['size_values_used']) or 'none'}.")
    if q["zero_variance_flags"]:
        st.warning("Zero variance: " + "; ".join(q["zero_variance_flags"]) +
                   ". Tests and intervals for these measures are undefined.")

    anova = ctx.result.anova.set_index("measure")
    for tab, measure in zip(st.tabs(["Size", "Attention", "Arousal", "Mood (placebo)"]),
                            ("size", "attention", "arousal", "mood")):
        with tab:
            chart(distribution_plotly(ctx.frame, measure, ctx.is_mock), "distribution")
            if measure == "size":
                chart(size_histogram_plotly(ctx.frame, ctx.is_mock), "size_histogram")
            row = anova.loc[measure]
            desc = ctx.result.descriptives
            st.dataframe(desc[desc.measure == measure].drop(columns="measure").round(2),
                         hide_index=True, width="stretch")
            if row.get("zero_variance"):
                st.info(f"Test: {row['note']}.")
            elif pd.notna(row.get("p")):
                st.markdown(
                    f"**ANOVA:** F(1, {int(row['df_error'])}) = {fmt(row['F'])}, p = {fmt_p(row['p'])}. "
                    f"**Difference** (high - low) = {fmt(row['diff'], 2, True)} {ci_text(row['diff_ci_low'], row['diff_ci_high'])}. "
                    f"**r** = {fmt(row['r'], 3, True)} {ci_text(row['r_ci_low'], row['r_ci_high'], 3)}; "
                    f"**d** = {fmt(row['d'], 2, True)} {ci_text(row['d_ci_low'], row['d_ci_high'])}; "
                    f"**partial eta-squared** = {fmt(row['eta_sq'], 3)} {ci_text(row['eta_ci_low'], row['eta_ci_high'], 3)}. "
                    "All intervals 95%."
                )
            if measure == "mood":
                st.markdown(f"**Placebo check:** {ctx.result.mood['reading']}. Humans: "
                            f"{MOOD_ORIGINAL['mean_high_assumed']} vs {MOOD_ORIGINAL['mean_low_assumed']}, "
                            f"{MOOD_ORIGINAL['p_text']} (order assumed).")


# ==========================================================================
# Page 5: Human vs AI
# ==========================================================================

def comparison_display(ctx: Context) -> pd.DataFrame:
    """Readable version of the comparison table."""
    rows = []
    for _, r in ctx.result.comparison.iterrows():
        rows.append({
            "Measure": r["measure"], "Source": {"original": "Original", "replication": "Replication", "ai": "AI"}[r["source"]],
            "n": int(r["n_total"]) if pd.notna(r["n_total"]) else "n/a",
            "r [95% CI]": f"{fmt(r['r'], 3, True)} {ci_text(r['r_ci_low'], r['r_ci_high'], 3)}",
            "d": fmt(r["d"], 2, True),
            "AI vs original: z, p": (f"{fmt(r.get('z_vs_original'))}, {fmt_p(r.get('p_vs_original'))}"
                                     if r["source"] == "ai" and "z_vs_original" in r and pd.notna(r.get("z_vs_original", float('nan'))) else ""),
            "AI vs replication: z, p": (f"{fmt(r.get('z_vs_replication'))}, {fmt_p(r.get('p_vs_replication'))}"
                                        if r["source"] == "ai" and "z_vs_replication" in r and pd.notna(r.get("z_vs_replication", float('nan'))) else ""),
        })
    return pd.DataFrame(rows)


def levels_table(ctx: Context) -> pd.DataFrame:
    """AI means and spread next to human means where the scales match."""
    rows = []
    anova = ctx.result.anova.set_index("measure")
    for measure in ("size", "attention", "arousal"):
        ai = anova.loc[measure]
        for source, bench in (("Original", ORIGINAL[measure]), ("Replication", REPLICATION[measure])):
            comparable = not (source == "Replication" and measure == "arousal")
            rows.append({
                "Measure": measure, "Human source": source,
                "Human high / low": f"{bench.high.mean:.2f} / {bench.low.mean:.2f}" if comparable else "7-point scale",
                "AI high / low": f"{fmt(ai.get('mean_high'))} / {fmt(ai.get('mean_low'))}",
                "Human SD (avg)": f"{(bench.high.sd + bench.low.sd) / 2:.2f}" if comparable else "n/a",
                "AI SD (avg)": fmt((ai.get('sd_high', float('nan')) + ai.get('sd_low', float('nan'))) / 2),
            })
    return pd.DataFrame(rows)


def page_comparison(ctx: Context) -> None:
    """The central page: does the AI reproduce the human effects?"""
    st.title("Human vs AI: is the effect reproduced?")
    st.info("A similar average does **not** by itself mean the human effect was reproduced. We compare the "
            "direction, the size and the uncertainty of each effect, and test the difference.")
    chart(forest_plotly(ctx.result.comparison, ctx.is_mock), "forest")

    st.subheader("Plain-English reading")
    reading = ctx.result.reading.rename(columns={
        "measure": "Measure", "same_direction": "Same direction?", "similar_magnitude": "Similar magnitude? (Fisher-z)",
        "ai_effect_significant": "Statistical evidence in the AI data?"})
    st.dataframe(reading, hide_index=True, width="stretch")
    st.caption("\"Not significantly different\" with small samples is weak evidence of similarity: the human "
               "intervals are wide (original n = 77).")

    left, right = st.columns(2)
    with left:
        st.subheader("Size: is there truly no effect? (TOST)")
        t = ctx.result.tost_size
        st.markdown(
            f"Equivalence bound: +/-{t['bound']} inch. Difference (high - low) = {fmt(t.get('diff'), 2, True)} in; "
            f"90% CI {ci_text(t.get('ci90_low'), t.get('ci90_high'))}.\n\n**Conclusion:** {t['conclusion']}."
        )
        st.caption("TOST asks whether the difference is small enough to call it zero. For reference: original "
                   "difference 0.87 in; replication 0.04 in.")
    with right:
        st.subheader(f"Outcome: pattern {ctx.result.outcome['label']}")
        st.markdown(ctx.result.outcome["name"] + "\n\n" + "\n".join(f"- {r}" for r in ctx.result.outcome["reasons"]))
        st.markdown(f"**Mood placebo:** {ctx.result.mood['reading']}.")
        med = ctx.result.mediation
        if med.get("ran"):
            st.markdown(f"**Mediation (AI):** total indirect B = {fmt(med['paths']['total_indirect'])}, 95% CI "
                        f"{ci_text(*med['ci95']['total_indirect'])} ({med['bootstrap_samples']} bootstrap samples). "
                        f"Original: B = .53 [.16, 1.01].")
        else:
            st.markdown(f"**Mediation:** {med['reason']}")

    st.subheader("Effect sizes and Fisher-z tests")
    st.dataframe(comparison_display(ctx), hide_index=True, width="stretch")
    st.caption("Fisher-z tests whether two independent r values differ. Human r and CIs as published; human d "
               "from published means and SDs with assumed cell n.")
    st.subheader("Levels and spread")
    st.dataframe(levels_table(ctx), hide_index=True, width="stretch")
    st.caption("If AI SDs are much smaller than human SDs, the agents are more uniform than people.")


# ==========================================================================
# Page 6: Explore data
# ==========================================================================

def page_explore(ctx: Context) -> None:
    """Filterable table, CSV download and the variable dictionary."""
    st.title("Explore the agent data")
    frame = ctx.frame
    c1, c2, c3 = st.columns(3)
    conditions = c1.multiselect("Condition", ["high", "low"], default=["high", "low"])
    genders = c2.multiselect("Persona gender", sorted(frame["gender"].fillna("").unique()),
                             default=sorted(frame["gender"].fillna("").unique()))
    validity = c3.radio("Rows", ["All", "Valid only", "Invalid only"], horizontal=True)
    view = frame[frame.condition.isin(conditions) & frame["gender"].fillna("").isin(genders)]
    if validity == "Valid only":
        view = view[view.valid]
    elif validity == "Invalid only":
        view = view[~view.valid]
    st.caption(f"{len(view)} of {len(frame)} agents shown.")
    st.dataframe(view, hide_index=True, width="stretch", height=420)
    st.download_button("Download the full CSV", data=ctx.path.read_bytes(), file_name=ctx.path.name, mime="text/csv")
    with st.expander("Variable dictionary and data-collection procedure"):
        dictionary = DATA_DIR / "VARIABLE_DICTIONARY.md"
        st.markdown(dictionary.read_text(encoding="utf-8") if dictionary.is_file() else "Dictionary not found.")


# ==========================================================================
# Page 7: Limitations
# ==========================================================================

def page_limitations(ctx: Context) -> None:
    """What the simulation can and cannot show."""
    st.title("Limitations and cautions")
    st.markdown(
        "- **No real attention or arousal.** The paper's mechanism (saturation -> arousal -> attention -> size) "
        "is physiological. A language model has none of it; any effect reflects learned associations between "
        "images and words, so a matching result would not show the same *process*.\n"
        "- **Training-data recall.** The finding is published and widely cited. A model could answer from "
        "what it has read about colour and attention rather than from the image. The diagnostic run (20 agents "
        "asked to explain their answers) is used to look for this; it never changes settings.\n"
        "- **Setting.** Humans saw a large projected image in a group; agents see a small file. Humans were "
        "paid in snacks; agents are not. The replication was online and in Japanese.\n"
        "- **One model, one prompt.** Results may differ for other models or wordings. Settings were fixed "
        "before any live run and are not tuned to match humans.\n"
        "- **Variation is artificial.** Differences between agents come from sampling temperature and a "
        "one-line persona, not from real individual differences. Watch the zero-variance and duplicate-answer "
        "warnings.\n"
        "- **Summary-level comparison.** No raw human data were provided, and per-cell n is assumed.\n"
        "- **Benchmarks disagree.** The size effect appeared in the original (n = 77) but not in the much larger "
        "replication (n = 823). \"Matching humans\" depends on which humans.\n\n"
        "**For researchers using AI agents as participants:** fix settings before looking at results; never "
        "reveal the hypothesis or condition; send the real stimulus; one independent call per participant; "
        "compare effects (direction, size, uncertainty), not just averages; report every deviation and every "
        "invalid response; and treat AI results as a pilot or a hypothesis check, not a substitute for people."
    )


# ==========================================================================
# Page 8: Run experiment (hidden unless enabled in config)
# ==========================================================================

def page_run(ctx: Context) -> None:
    """Placeholder: live runs are started with scripts/run_live.py (built in Phase 6)."""
    st.title("Run experiment")
    st.warning("Live runs spend API money. In this version they are started from the command line with "
               "`python scripts/run_live.py --run-label smoke`, which shows the cost and asks for confirmation.")


# ==========================================================================
# Main: sidebar, banner, page
# ==========================================================================

def main() -> None:
    """Sidebar file picker and page navigation, then the selected page."""
    config = get_config()
    st.sidebar.title("GP4 dashboard")
    runs = list_runs()
    if not runs:
        st.title("No data yet")
        st.markdown("Run `python scripts/run_dry.py` (mock data) or a live run first, then refresh this page.")
        return
    labels = [run_label_for(p) for p in runs]
    choice = st.sidebar.selectbox("Data file", labels, index=0,
                                  help="REAL = live results (data/real). MOCK = dry-run test data (data/mock).")
    path = runs[labels.index(choice)]
    pages = PAGES + (["8. Run experiment"] if config.enable_run_page else [])
    page = st.sidebar.radio("Page", pages)

    frame, result = load_and_analyze(str(path), path.stat().st_mtime)
    ctx = Context(config, path, frame, result, load_snapshot(path))
    if not ctx.is_mock and "main" in ctx.result.quality["run_labels"] and path != primary_main(path.parent):
        st.warning(f"REPEAT RUN: by the rule fixed before any results, the first main run "
                   f"({primary_main(path.parent).name}) is the primary result. This repeat is shown for "
                   "transparency and as a stability check.")
    if "smoke" in ctx.result.quality["run_labels"]:
        st.warning("SMOKE TEST: a 4-agent pipeline check, not a result. Effects from 4 agents mean nothing; "
                   "select a main run in the sidebar.")
    if ctx.is_mock:
        st.error(MOCK_BANNER)
        st.sidebar.error("MOCK DATA selected")
    else:
        st.sidebar.success("Real data selected")
    st.sidebar.caption(f"Colours: high = red circles, low = violet triangles; original = blue squares, "
                       f"replication = orange diamonds, AI = aqua circles.")

    handlers = {
        "1. Overview": page_overview, "2. Original study": page_original, "3. AI-agent system": page_system,
        "4. Results": page_results, "5. Human vs AI": page_comparison, "6. Explore data": page_explore,
        "7. Limitations": page_limitations, "8. Run experiment": page_run,
    }
    handlers[page](ctx)
    provenance(ctx)


main()
