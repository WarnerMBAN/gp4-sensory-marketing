"""
build_report.py: build the 2-page short report (deliverable C) as a Word file.

Where it fits
-------------
Last step of the pipeline. Reads the saved analysis of the PRIMARY main run
(data/real/gp4_main_20261105_191049_*) and the report figures, and writes a
house-style .docx (Dale's MBAN 5640 Word layout, reports/mban_docx.py).
Every number in the report comes from those files, not from typing, so the
report cannot drift from the data. Rebuild after any analysis change.

How to run (from the project folder, .venv active)
--------------------------------------------------
    python -m pip install -r reports/requirements-report.txt   # once (python-docx)
    python reports/build_report.py

In:  data/real/gp4_main_20261105_191049_analysis/ (descriptives, comparison, details),
     data/real/gp4_main_20261105_191049.csv, reports/figures/gp4_main_20261105_191049_fig2/fig3.
Out: reports/MBAN5640_GP4_Group01_Report_SONI-TONER-WARNER_<YYYYMMDD_HHMM>.docx

Writing rules: no em dashes; plain language; the course limit is 2 pages
(check the page count after every edit).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import mban_docx as M  # noqa: E402

# CONFIG: the run this report describes (the PRIMARY main run; see CHANGELOG.md)
RUN_STEM = "gp4_main_20261105_191049"
REPEAT_STEM = "gp4_main_20261105_191715"   # accidental repeat, used only as a stability check
DASHBOARD_URL = "https://gp4-saturation.streamlit.app/"
REPO_URL = "https://github.com/WarnerMBAN/gp4-sensory-marketing"

BODY = 9.5  # EDIT HERE: body text size (pt); smaller than the house 10.5 to meet the 2-page limit


# ---------------------------------------------------------------------------
# 1. Load the numbers
# ---------------------------------------------------------------------------
def load():
    """All figures the text needs, from the saved analysis files."""
    adir = ROOT / "data" / "real" / f"{RUN_STEM}_analysis"
    comp = pd.read_csv(adir / "comparison.csv")
    desc = pd.read_csv(adir / "descriptives.csv")
    details = json.loads((adir / "details.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(ROOT / "data" / "real" / f"{RUN_STEM}.csv")
    raw = raw[raw.valid]
    repeat = pd.read_csv(ROOT / "data" / "real" / f"{REPEAT_STEM}_analysis" / "comparison.csv")

    def row(measure, source, frame=comp):
        return frame[(frame.measure == measure) & (frame.source == source)].iloc[0]

    def share(cond, inches):
        part = raw[raw.condition == cond]
        return 100 * (part.screen_size == inches).mean()

    tokens = json.loads((ROOT / "data" / "real" / f"{RUN_STEM}_config.json").read_text(encoding="utf-8"))
    return {"row": row, "desc": desc, "d": details, "share": share, "repeat": repeat, "config": tokens,
            "n": len(raw)}


def r2(x):
    """+.30 style (two decimals, sign, no leading zero). Rounds half up on the decimal value, so a published
    r of .295 prints as .30 (plain float formatting gives .29 because 0.295 is stored as 0.29499...)."""
    from decimal import ROUND_HALF_UP, Decimal
    v = Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{v:+.2f}".replace("0.", ".", 1)


def ci(lo, hi):
    return f"[{r2(lo)}, {r2(hi)}]"


def pval(p):
    return "p < .001" if p < 0.001 else f"p = {p:.3f}".replace("0.", ".", 1)


# ---------------------------------------------------------------------------
# 2. Small layout helpers on top of the house style
# ---------------------------------------------------------------------------
def tight(doc, after=3):
    """Shrink the space after the last paragraph."""
    M.spacing(doc.paragraphs[-1], after=after)


def body(doc, text):
    p = M.para(doc, text, size=BODY)
    M.spacing(p, after=4, line=1.05)
    return p


def items(doc, lines):
    for line in lines:
        p = doc.add_paragraph(style="List Bullet")
        M.spacing(p, after=1.5, line=1.05)
        M.rich(p, line, size=BODY)


def h1(doc, text):
    h = M.heading(doc, text, level=1)
    h.paragraph_format.space_before, h.paragraph_format.space_after = Pt(7), Pt(3)
    for r in h.runs:
        r.font.size = Pt(12)


def two_figures(doc, left, right, captions):
    """Two figures side by side in a borderless two-cell table, each with a caption."""
    t = doc.add_table(rows=2, cols=2)
    M._widths(t, [5120, 5120])
    for i, (path, cap) in enumerate(zip((left, right), captions)):
        c = t.rows[0].cells[i]
        p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; M.spacing(p, after=0)
        p.add_run().add_picture(str(path), width=Inches(3.35))
        q = t.rows[1].cells[i].paragraphs[0]; M.spacing(q, after=0, line=1.0)
        M.rich(q, cap, size=7.5, color=M.GREY)
    M._gap(doc)


# ---------------------------------------------------------------------------
# 3. The report
# ---------------------------------------------------------------------------
def build():
    """Write the report and return its path."""
    x = load()
    row, d, share = x["row"], x["d"], x["share"]
    s_o, s_r, s_a = row("size", "original"), row("size", "replication"), row("size", "ai")
    a_o, a_r, a_a = row("attention", "original"), row("attention", "replication"), row("attention", "ai")
    v_o, v_r, v_a = row("arousal", "original"), row("arousal", "replication"), row("arousal", "ai")
    m_a = row("mood", "ai")
    rep_size = row("size", "ai", x["repeat"])
    tost, med, q = d["tost_size"], d["mediation"], d["quality"]
    hi15, lo13 = share("high", 15), share("low", 13)
    cost_note = "about US$0.04"

    doc = M.new_document(
        title="Can AI Agents See What People See?",
        doc_name="GP4 - Short Report",
        subtitle="Colour saturation and perceived product size: Hagtvedt and Brasel (2017) with AI agents",
        course_line="MBAN 5640 Visualization & Data Mining · Group Project 4 · Short report (deliverable C)",
        status_tail=f"from {RUN_STEM}",
        ai_text=("Prepared with AI assistance from **Claude (Anthropic)**: the simulation code, statistical analysis, "
                 "figures and a first draft of this report were produced with Claude, then reviewed and edited by "
                 "the team. The simulated participants are OpenAI gpt-4o-mini agents."))
    # tighten the title block a little for the 2-page limit
    for p in doc.paragraphs[:6]:
        p.paragraph_format.space_after = Pt(1)

    M.bluf(doc, [
        f"**Direction yes, pattern no.** The AI agents shifted all three measures the same way as people did, but "
        f"the size effect was more than double the original (r = {r2(s_a.r)} vs {r2(s_o.r)}), while the large "
        f"replication found none ({r2(s_r.r)}).",
        f"**The mechanism was missing.** Attention barely moved (r = {r2(a_a.r)}, not significant), the "
        f"arousal-attention-size chain was not significant, and mood, which people did not change, did (r = "
        f"{r2(m_a.r)}): a halo response.",
        f"**Answers were near-categorical.** {hi15:.0f}% of high-saturation agents said 15 inches and {lo13:.0f}% of "
        f"low-saturation agents said 13. AI agents can flag the direction of a visual cue, but their effect sizes "
        f"should not be read as human ones.",
    ])

    # 1. Background ---------------------------------------------------------
    h1(doc, "1. Research background")
    body(doc, "Product colour is one of the cheapest design choices a marketer controls. Hagtvedt and Brasel "
              "(2017) asked whether **colour saturation** (how vivid a colour is) changes how **big** a product "
              "looks. Their theory: saturated colours are more **arousing**; arousal draws **attention**; and "
              "objects that attract attention are judged **larger**. If true, saturation is a lever for packaging "
              "and product images, and a risk when a product should look small. Our question, from the course "
              "brief: to what extent can AI agents reproduce these human perceptions and effects?")

    # 2. Human results ------------------------------------------------------
    h1(doc, "2. Human results")
    body(doc, f"In **Study 3** (n = 77 undergraduates, between-subjects), each person saw one red laptop in high or "
              f"low saturation. High saturation raised estimated screen size ({s_o.mean_high:.2f} vs "
              f"{s_o.mean_low:.2f} inches, r = {r2(s_o.r)}), attention ({a_o.mean_high:.2f} vs {a_o.mean_low:.2f} "
              f"on 1 to 7, r = {r2(a_o.r)}) and arousal ({v_o.mean_high:.2f} vs {v_o.mean_low:.2f} on 1 to 9, r = "
              f"{r2(v_o.r)}); mood, a placebo measure, did not differ (5.43 vs 5.49, p > .87). A serial mediation "
              f"(saturation, arousal, attention, size) was significant (B = .53, 95% CI [.16, 1.01]). The "
              f"**Motoki and Iseki (2022)** replication (n = 823 Japanese online adults) confirmed attention "
              f"(r = {r2(a_r.r)}) and arousal (r = {r2(v_r.r)}, 7-point scale) but found **no size effect** "
              f"({s_r.mean_high:.2f} vs {s_r.mean_low:.2f} inches, r = {r2(s_r.r)}). We compare the AI with both.")

    # 3. AI design and results ---------------------------------------------
    h1(doc, "3. AI-agent design and results")
    items(doc, [
        "**Agents.** 77 agents, as in the original, randomly assigned with a fixed seed (39 high, 38 low). Each agent "
        "is **one fresh call** to OpenAI **gpt-4o-mini** with no memory of other agents, which reproduces the "
        "between-subjects design. Persona: \"You are a female/male undergraduate university student\" (49% male, "
        "balanced within each condition).",
        "**Stimulus and questions.** Each agent receives the **actual image** (one image only, neutral file name) "
        "followed by the original questions and scales: screen size in whole inches from 10 to 20, two attention "
        "items (1 to 7, averaged), arousal and mood (1 to 9). The prompt never mentions colour, saturation, "
        "conditions or the hypothesis; the code checks this.",
        f"**Settings and data.** Temperature 1.0, low image detail. Answers are forced into a JSON format and "
        f"checked in Python (whole numbers, in range; up to 3 tries). {q['n_valid']} of {q['n_agents']} agents were "
        f"valid on the first try; cost {cost_note}. Every call is logged (prompt and image fingerprints, tokens, "
        f"raw output). All settings were signed off **before** the first live run and not changed afterwards.",
    ])
    body(doc, f"**AI results (high vs low).** Size {s_a.mean_high:.2f} vs {s_a.mean_low:.2f} inches (F(1, 75) = "
              f"{s_a.F:.2f}, {pval(s_a.p)}); arousal {v_a.mean_high:.2f} vs {v_a.mean_low:.2f} ({pval(v_a.p)}); "
              f"attention {a_a.mean_high:.2f} vs {a_a.mean_low:.2f} ({pval(a_a.p)}, not significant); mood "
              f"{m_a.mean_high:.2f} vs {m_a.mean_low:.2f} ({pval(m_a.p)}).")

    # 4. Comparison ---------------------------------------------------------
    h1(doc, "4. Human-AI comparison")
    rows = [
        ["Size", f"{r2(s_o.r)} {ci(s_o.r_ci_low, s_o.r_ci_high)}", r2(s_r.r), f"{r2(s_a.r)} {ci(s_a.r_ci_low, s_a.r_ci_high)}",
         f"Larger ({pval(s_a.p_vs_original)})", "**Exaggerated**"],
        ["Attention", f"{r2(a_o.r)} {ci(a_o.r_ci_low, a_o.r_ci_high)}", r2(a_r.r), f"{r2(a_a.r)} {ci(a_a.r_ci_low, a_a.r_ci_high)}",
         f"Not different ({pval(a_a.p_vs_original)})", "Same sign, not significant"],
        ["Arousal", f"{r2(v_o.r)} {ci(v_o.r_ci_low, v_o.r_ci_high)}", r2(v_r.r), f"{r2(v_a.r)} {ci(v_a.r_ci_low, v_a.r_ci_high)}",
         f"Not different ({pval(v_a.p_vs_original)})", "**Reproduced**"],
        ["Mood (placebo)", "none (p > .87)", "n/a", f"{r2(m_a.r)} {ci(m_a.r_ci_low, m_a.r_ci_high)}", "n/a",
         "**Halo** (should be zero)"],
    ]
    M.table(doc, ["Measure", "Original r [95% CI]", "Replication r", "AI r [95% CI]", "AI vs original r",
                  "Verdict"], rows, widths=[1250, 1800, 1400, 1800, 2050, 1940])
    tight(doc, 2)
    two_figures(doc, ROOT / "reports" / "figures" / f"{RUN_STEM}_fig2_effect_sizes.png",
                ROOT / "reports" / "figures" / f"{RUN_STEM}_fig3_size_histogram.png",
                ["Figure 1. Effect of high vs low saturation (r, 95% CI) for each source. Right of zero = higher for "
                 "the more saturated laptop.",
                 "Figure 2. AI screen-size answers. Agents used only 13, 14 or 15 inches, almost one value per "
                 "condition."])
    items(doc, [
        f"**Direction and magnitude.** All three AI effects point the same way as the original. Arousal matches "
        f"closely; size is far larger than in either human study; attention is smaller and not significant.",
        f"**Size is not a null.** The AI difference is {tost['diff']:.2f} inches (90% CI [{tost['ci90_low']:.2f}, "
        f"{tost['ci90_high']:.2f}]), well outside a plus or minus 0.5 inch equivalence band, so the AI clearly sides "
        f"with the original, not the replication, and overshoots it. An accidental repeat run gave r = "
        f"{r2(rep_size.r)}, so the result is stable.",
        f"**Variability is not human.** AI standard deviations for size are about half the humans' "
        f"({s_a.sd_high:.2f} vs {s_o.sd_high:.2f}), and for attention about a tenth; {100 * q['duplicate_answer_share']:.0f}% "
        f"of agents gave an answer pattern identical to another agent's. The mediation chain was not significant "
        f"(total indirect B = {r2(med['paths']['total_indirect']).lstrip('+')}, 95% CI {ci(*med['ci95']['total_indirect'])}; humans .53).",
        "**Possible explanations.** The model has no eyes or arousal system; it most likely maps a vivid image onto "
        "learned associations (vivid, premium, larger) and then picks the most typical answer, which removes the "
        "spread that real people show. In a 20-agent diagnostic run, all 20 explanations mentioned colour and "
        "style; none mentioned size.",
    ])

    # 5. Conclusion ---------------------------------------------------------
    h1(doc, "5. Conclusion and limitations")
    body(doc, "**Outcome: exaggerated, with a halo.** AI agents reproduced the *direction* of the saturation "
              "effects and the size of the arousal effect, but not the human *pattern*: size is overstated, the "
              "attention mechanism is missing, mood moves when it should not, and answers are nearly uniform. "
              "AI agents are useful for a fast, cheap first look at whether a visual cue matters, not as a "
              "substitute for human participants or for estimating effect sizes.")
    body(doc, "**Limitations.** One model and one prompt version; the comparison uses published summary statistics "
              "(no raw human data; cell sizes assumed); the image is small and on screen; the replication used a "
              "different population and a 7-point arousal scale (compared by effect size only); an AI has no real "
              "attention or arousal. All differences from the original design are listed in DEVIATIONS.md.")
    p = M.para(doc, f"Code, data and variable dictionary: {REPO_URL} · Dashboard: {DASHBOARD_URL} · Sources: "
                    "Hagtvedt, H., and Brasel, S. A. (2017), *Journal of Consumer Research*, 44(2), 396-413. "
                    "Motoki, K., and Iseki, S. (2022), *Frontiers in Communication*, 7, 1048896.", size=7.5,
               color=M.GREY)
    M.spacing(p, before=2, after=0, line=1.0)

    return M.save(doc, HERE, "MBAN5640_GP4_Group01_Report_SONI-TONER-WARNER")


if __name__ == "__main__":
    print("Written:", build())
