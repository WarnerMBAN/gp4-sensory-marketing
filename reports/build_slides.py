"""
build_slides.py: build the presentation deck (deliverable D, Option A) as a PowerPoint file.

Where it fits
-------------
Reads the primary main run's analysis, the stimuli and the report figures, and the
talk text in reports/talk_content.py (which becomes each slide's speaker notes).
Writes a 12-slide, 16:9 deck in the navy house style used by the dashboard.

How to run (from the project folder, .venv active)
--------------------------------------------------
    python -m pip install -r reports/requirements-report.txt   # once (python-pptx)
    python reports/build_slides.py

Out: reports/MBAN5640_GP4_Group01_Slides_SONI-TONER-WARNER_<YYYYMMDD_HHMM>.pptx

Design notes: navy for title, demo and closing slides; white content slides.
Chart colours are the project's fixed ones (high #e34948, low #6250d6; sources
blue/orange/green) and red is kept out of the page frame so it always means
"high saturation". No em dashes in slide text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import mban_docx  # noqa: E402  (only for the Halifax clock)
import talk_content as T  # noqa: E402

RUN_STEM = "gp4_main_20261105_191049"  # CONFIG: the PRIMARY main run

# EDIT HERE: palette (navy frame; data colours fixed project-wide)
NAVY, INK, ROYAL = "0B2A5B", "0B1F3A", "1D4E9E"
ICE, PALE, GREY, WHITE = "E8EEF8", "C9D6EC", "5B6573", "FFFFFF"
CORAL = "FF6B7A"          # accent on navy only
HIGH, LOW = "E34948", "6250D6"
ORIGINAL, REPLICATION, AI = "2A78D6", "EB6834", "1BAF7A"
FONT = "Arial"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)


def rgb(hex_):
    return RGBColor.from_string(hex_)


# ---------------------------------------------------------------------------
# 1. Drawing helpers
# ---------------------------------------------------------------------------
def background(slide, color):
    fill = slide.background.fill
    fill.solid(); fill.fore_color.rgb = rgb(color)


def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         name=None, line=1.1):
    """Text box. runs: a string, or a list of paragraphs; each paragraph a string or a list of (text, opts)."""
    box = slide.shapes.add_textbox(x, y, w, h)
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paragraphs = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        pieces = para if isinstance(para, list) else [(para, {})]
        for piece, opts in pieces:
            r = p.add_run(); r.text = piece
            f = r.font
            f.name, f.size = FONT, Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold); f.italic = opts.get("italic", False)
            f.color.rgb = rgb(opts.get("color", color))
        if i < len(paragraphs) - 1:
            p.space_after = Pt(opts.get("after", 6) if pieces else 6)
    return box


def box(slide, x, y, w, h, fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=None, name=None, radius=0.08):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if name:
        s.name = name
    s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line); s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def shape_text(shape, value, size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER):
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = value
    r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
    r.font.color.rgb = rgb(color)


def title(slide, value, color=INK):
    """Content-slide title: same position, font and size on every content slide."""
    text(slide, MARGIN, Inches(0.45), W - 2 * MARGIN, Inches(0.9), value, size=32, bold=True, color=color,
         name="Title", anchor=MSO_ANCHOR.MIDDLE)


def footer(slide, number, dark=False):
    color = PALE if dark else GREY
    text(slide, MARGIN, H - Inches(0.45), Inches(8), Inches(0.3),
         "MBAN 5640 · Group Project 4 · Group 1: Soni, Toner, Warner", size=10, color=color, name="Footer")
    text(slide, W - MARGIN - Inches(1), H - Inches(0.45), Inches(1), Inches(0.3), str(number), size=10,
         color=color, align=PP_ALIGN.RIGHT, name="Slide number")


def notes(slide, entry):
    """Speaker notes: speaker, stage directions, then the words."""
    who = T.SPEAKERS[entry["speaker"]]
    lines = [f"{who} (about {T.mmss(T.seconds(entry))})"]
    lines += [f"[{a}]" for a in entry["actions"]]
    if entry["text"]:
        lines += ["", entry["text"]]
    slide.notes_slide.notes_text_frame.text = "\n".join(lines)


def picture(slide, path, x, y, w=None, h=None, name=None):
    pic = slide.shapes.add_picture(str(path), x, y, w, h)
    if name:
        pic.name = name
    return pic


# ---------------------------------------------------------------------------
# 2. Data
# ---------------------------------------------------------------------------
def load():
    adir = ROOT / "data" / "real" / f"{RUN_STEM}_analysis"
    comp = pd.read_csv(adir / "comparison.csv")
    details = json.loads((adir / "details.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(ROOT / "data" / "real" / f"{RUN_STEM}.csv")
    raw = raw[raw.valid]
    stored = json.loads((ROOT / "stimuli" / "stimulus_key.json").read_text(encoding="utf-8"))
    key = {v["condition"]: {"file": name} for name, v in stored.items()}  # condition -> file name
    return comp, details, raw, key


def r_text(x):
    from decimal import ROUND_HALF_UP, Decimal
    v = Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{v:+.2f}".replace("0.", ".", 1)


# ---------------------------------------------------------------------------
# 3. Slides
# ---------------------------------------------------------------------------
def build():
    comp, details, raw, key = load()
    row = lambda m, s: comp[(comp.measure == m) & (comp.source == s)].iloc[0]  # noqa: E731
    s_o, s_r, s_a = row("size", "original"), row("size", "replication"), row("size", "ai")
    a_o, a_r, a_a = row("attention", "original"), row("attention", "replication"), row("attention", "ai")
    v_o, v_r, v_a = row("arousal", "original"), row("arousal", "replication"), row("arousal", "ai")
    m_a = row("mood", "ai")
    q, tost = details["quality"], details["tost_size"]
    high_img = ROOT / "stimuli" / key["high"]["file"]
    low_img = ROOT / "stimuli" / key["low"]["file"]
    entries = {e["slide"]: e for e in T.OPTION_A}

    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    core = prs.core_properties
    core.title = "Can AI agents see what people see?"
    core.author = "Group 1: Krishna Soni, Michael Toner, Dale Warner"
    core.subject = "MBAN 5640 Group Project 4"

    # --- 1. Title (navy) ---------------------------------------------------
    s = prs.slides.add_slide(blank); background(s, NAVY)
    text(s, MARGIN, Inches(1.5), Inches(7.4), Inches(1.9), "Can AI agents see what people see?", size=44,
         bold=True, color=WHITE, name="Title", line=1.0)
    text(s, MARGIN, Inches(3.55), Inches(7.2), Inches(1.0),
         "Colour saturation and perceived product size: Hagtvedt and Brasel (2017), Study 3, replicated with "
         "77 AI agents", size=18, color=PALE)
    text(s, MARGIN, Inches(5.3), Inches(7.4), Inches(0.9),
         ["Krishna Soni · Michael Toner · Dale Warner",
          [("MBAN 5640 Visualization & Data Mining · Group Project 4 · November 28, 2026", {"size": 13,
                                                                                               "color": PALE})]],
         size=16, color=WHITE, bold=True)
    for i, (img, label) in enumerate(((high_img, "Vivid"), (low_img, "Muted"))):
        y = Inches(1.35 + i * 2.65)
        box(s, Inches(8.65), y, Inches(4.05), Inches(2.4), WHITE, name=f"Image card {i + 1}")
        picture(s, img, Inches(8.9), y + Inches(0.2), w=Inches(3.0), name=f"Laptop {label}")
        text(s, Inches(11.95), y + Inches(0.95), Inches(0.7), Inches(0.5), label, size=12, color=GREY)
    notes(s, entries[1])

    # --- 2. Marketing question ---------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[2]["title"])
    for i, (img, label, sub) in enumerate(((high_img, "High saturation", "vivid"),
                                           (low_img, "Low saturation", "muted"))):
        x = MARGIN + i * Inches(6.15)
        box(s, x, Inches(1.55), Inches(5.95), Inches(3.55), ICE, name=f"Stimulus card {i + 1}")
        picture(s, img, x + Inches(0.95), Inches(1.8), w=Inches(4.05), name=f"Stimulus {sub}")
        text(s, x, Inches(4.62), Inches(5.95), Inches(0.4), [[(label, {"bold": True}), (f"  ({sub})", {})]],
             size=16, align=PP_ALIGN.CENTER)
    text(s, MARGIN, Inches(5.25), W - 2 * MARGIN, Inches(0.4),
         "Same laptop, same size. Only the colour saturation differs.", size=14, color=GREY,
         align=PP_ALIGN.CENTER)
    for i, (head, body) in enumerate((("Cheap lever", "Colour costs almost nothing to change"),
                                      ("Where it matters", "Packaging, product design, online photos"),
                                      ("What we measure", "Perceived screen size (inches)"))):
        x = MARGIN + i * Inches(4.1)
        text(s, x, Inches(5.85), Inches(3.9), Inches(0.9),
             [[(head, {"bold": True, "color": ROYAL, "size": 16})], body], size=14)
    footer(s, 2); notes(s, entries[2])

    # --- 3. Theory and design ----------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[3]["title"])
    steps = ["Colour saturation", "Arousal", "Attention", "Perceived size"]
    for i, label in enumerate(steps):
        x = MARGIN + i * Inches(3.05)
        shp = box(s, x, Inches(1.6), Inches(2.95), Inches(1.0), NAVY if i in (0, 3) else ROYAL,
                  shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, name=f"Step {i + 1}")
        shape_text(shp, label, size=17)
    text(s, MARGIN, Inches(2.75), W - 2 * MARGIN, Inches(0.4),
         "Proposed mechanism, confirmed by serial mediation in the original (indirect effect B = .53, "
         "95% CI [.16, 1.01])", size=12, color=GREY)
    box(s, MARGIN, Inches(3.4), Inches(5.0), Inches(3.3), ICE, name="Design card")
    text(s, MARGIN + Inches(0.3), Inches(3.6), Inches(4.4), Inches(3.0),
         [[("Study 3 design", {"bold": True, "size": 18, "color": NAVY})],
          "77 undergraduates", "Between-subjects: each person sees one image",
          "Random assignment to vivid or muted"], size=15)
    rows = [("Measure", "Scale"), ("Screen-size estimate", "10 to 20 inches, whole numbers"),
            ("Attention (2 items, averaged)", "1 to 7"), ("Arousal", "1 to 9"),
            ("Mood (control: should not change)", "1 to 9")]
    tbl = s.shapes.add_table(len(rows), 2, MARGIN + Inches(5.3), Inches(3.4), Inches(6.83), Inches(3.3)).table
    tbl.columns[0].width, tbl.columns[1].width = Inches(3.9), Inches(2.93)
    for r_i, (a, b) in enumerate(rows):
        for c_i, v in enumerate((a, b)):
            cell = tbl.cell(r_i, c_i)
            cell.fill.solid(); cell.fill.fore_color.rgb = rgb(NAVY if r_i == 0 else (WHITE if r_i % 2 else ICE))
            tf = cell.text_frame; tf.paragraphs[0].text = ""
            run = tf.paragraphs[0].add_run(); run.text = v
            run.font.name, run.font.size, run.font.bold = FONT, Pt(15), r_i == 0
            run.font.color.rgb = rgb(WHITE if r_i == 0 else INK)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    footer(s, 3); notes(s, entries[3])

    # --- 4. Human results ---------------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[4]["title"])
    cols = [("Original study", "Hagtvedt and Brasel (2017) · n = 77 students", ORIGINAL,
             [("Size", s_o), ("Attention", a_o), ("Arousal", v_o)]),
            ("Replication", "Motoki and Iseki (2022) · n = 823 adults, Japan", REPLICATION,
             [("Size", s_r), ("Attention", a_r), ("Arousal", v_r)])]
    for i, (head, sub, color, stats) in enumerate(cols):
        x = MARGIN + i * Inches(6.15)
        box(s, x, Inches(1.55), Inches(5.95), Inches(4.75), ICE, name=f"{head} card")
        text(s, x + Inches(0.35), Inches(1.75), Inches(5.3), Inches(0.9),
             [[(head, {"bold": True, "size": 22, "color": NAVY})], [(sub, {"size": 13, "color": GREY})]], size=13)
        for j, (label, r_row) in enumerate(stats):
            y = Inches(2.95 + j * 1.05)
            weak = abs(r_row.r) < 0.1
            text(s, x + Inches(0.35), y, Inches(2.2), Inches(0.9), r_text(r_row.r), size=40, bold=True,
                 color=GREY if weak else color, anchor=MSO_ANCHOR.MIDDLE)
            detail = "no effect" if weak else "effect (r)"
            if label == "Size":
                detail = f"{r_row.mean_high:.1f} vs {r_row.mean_low:.1f} in" + (", no effect" if weak else "")
            text(s, x + Inches(2.6), y + Inches(0.12), Inches(3.2), Inches(0.8),
                 [[(label, {"bold": True, "size": 17})], [(detail, {"size": 13, "color": GREY})]], size=13)
    text(s, MARGIN, Inches(6.45), W - 2 * MARGIN, Inches(0.4),
         "r = effect size of high vs low saturation (0 = none, .3 = moderate). Mood did not differ in the original "
         "(p > .87). The replication used a 7-point arousal scale, so arousal is compared by r only.",
         size=11, color=GREY)
    footer(s, 4); notes(s, entries[4])

    # --- 5. AI-agent system -------------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[5]["title"])
    steps = [("Roster", "77 agents\n39 vivid / 38 muted\nfixed random seed\n49% male student persona"),
             ("One fresh call", "OpenAI GPT-4o mini\nsees ONE real image\nno memory between agents"),
             ("Fixed format", "Answers forced into\na JSON structure:\nfive whole numbers"),
             ("Validate", "Whole number,\ninside its scale?\nRetry up to 3 times"),
             ("Log everything", "Prompt and image\nfingerprints, settings,\ntokens, raw answer")]
    for i, (head, body) in enumerate(steps):
        x = MARGIN + i * Inches(2.45)
        circ = box(s, x + Inches(0.75), Inches(1.65), Inches(0.75), Inches(0.75), NAVY, shape=MSO_SHAPE.OVAL,
                   name=f"Step {i + 1} number")
        shape_text(circ, str(i + 1), size=20)
        if i < len(steps) - 1:
            arrow = box(s, x + Inches(1.75), Inches(1.88), Inches(1.15), Inches(0.3), PALE,
                        shape=MSO_SHAPE.RIGHT_ARROW, name=f"Arrow {i + 1}")
        box(s, x, Inches(2.65), Inches(2.25), Inches(2.55), ICE, name=f"Step {i + 1} card")
        text(s, x + Inches(0.18), Inches(2.85), Inches(1.95), Inches(2.3),
             [[(head, {"bold": True, "size": 17, "color": NAVY})]] + body.split("\n"), size=14, line=1.05)
    callout = box(s, MARGIN, Inches(5.55), W - 2 * MARGIN, Inches(0.95), NAVY, name="Rule callout")
    shape_text(callout, "All settings were signed off before the first real run and never tuned to make the AI "
                        "look more human.", size=17, color=WHITE, bold=False)
    footer(s, 5); notes(s, entries[5])

    # --- 6. What each agent sees -------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[6]["title"])
    box(s, MARGIN, Inches(1.5), Inches(7.2), Inches(5.2), ICE, name="Prompt card")
    picture(s, high_img, MARGIN + Inches(0.3), Inches(1.7), w=Inches(1.9), name="Image sent")
    text(s, MARGIN + Inches(2.4), Inches(1.75), Inches(4.6), Inches(1.2),
         [[("1. The image", {"bold": True, "color": NAVY})],
          "One image per agent, sent as it is. No file name."], size=14)
    text(s, MARGIN + Inches(0.3), Inches(3.2), Inches(6.7), Inches(3.4),
         [[("2. The original questions", {"bold": True, "color": NAVY})],
          [("\"Estimate the laptop's screen size. Choose a whole number of inches from 10 to 20.\"",
            {"italic": True})],
          [("\"The laptop is attention-getting.\"  \"The laptop captures my attention.\"  (1 to 7)",
            {"italic": True})],
          [("\"Arousal: 1 = low, 9 = high.\"  \"Mood: 1 = displeasure, 9 = pleasure.\"", {"italic": True})],
          [("3. Answer format: ", {"bold": True, "color": NAVY}), ("five whole numbers, nothing else", {})]],
         size=14, line=1.1)
    text(s, Inches(8.35), Inches(1.55), Inches(4.4), Inches(0.5), "Never sent to the model", size=18, bold=True,
         color=NAVY)
    for j, item in enumerate(["The word colour or saturation", "Which condition it is in",
                              "The hypothesis or the paper", "Image file names", "Other agents' answers"]):
        y = Inches(2.2 + j * 0.62)
        mark = box(s, Inches(8.35), y, Inches(0.42), Inches(0.42), NAVY, shape=MSO_SHAPE.OVAL, name=f"No {j + 1}")
        shape_text(mark, "×", size=16)
        text(s, Inches(8.95), y + Inches(0.02), Inches(3.8), Inches(0.42), item, size=15, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(8.35), Inches(5.45), Inches(4.4), Inches(1.2),
         [[("Not reproduced: ", {"bold": True}), ("small on-screen image, no snack incentive, no real eyes or "
                                                  "arousal. All listed in DEVIATIONS.md.", {})]],
         size=12, color=GREY)
    footer(s, 6); notes(s, entries[6])

    # --- 7. AI size results (native chart) ---------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[7]["title"])
    cats = [str(v) for v in range(10, 21)]
    data = CategoryChartData(); data.categories = cats
    for cond, label in (("high", "High saturation (vivid)"), ("low", "Low saturation (muted)")):
        part = raw[raw.condition == cond].screen_size
        data.add_series(label, [float((part == int(c)).mean()) for c in cats])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, MARGIN, Inches(1.45), Inches(7.6), Inches(5.2), data)
    gf.name = "Size answers chart"
    ch = gf.chart
    ch.has_title = True
    ch.chart_title.text_frame.text = "Screen-size answers by condition (share of agents)"
    tp = ch.chart_title.text_frame.paragraphs[0].runs[0].font
    tp.size, tp.bold, tp.name, tp.color.rgb = Pt(14), True, FONT, rgb(INK)
    ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
    ch.legend.font.size, ch.legend.font.name = Pt(12), FONT
    plot = ch.plots[0]; plot.gap_width, plot.overlap = 60, -10
    for series, color in zip(plot.series, (HIGH, LOW)):
        series.format.fill.solid(); series.format.fill.fore_color.rgb = rgb(color)
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = '0%;;;', False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.name = Pt(12), FONT; dl.font.color.rgb = rgb(INK)
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 1.0, 0
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("E3E7EE")
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = '0%', False
    va.tick_labels.font.size = Pt(11); va.tick_labels.font.color.rgb = rgb(GREY)
    va.format.line.fill.background()
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(12); ca.tick_labels.font.color.rgb = rgb(GREY)
    ca.has_title = True; ca.axis_title.text_frame.text = "Estimated screen size (inches)"
    ca.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    ca.axis_title.text_frame.paragraphs[0].runs[0].font.color.rgb = rgb(GREY)
    stats = [(f"{s_a.mean_high:.1f} vs {s_a.mean_low:.1f} in", "average estimate, vivid vs muted"),
             (f"r = {r_text(s_a.r)}", "very large effect (original: " + r_text(s_o.r) + ")"),
             (f"{q['n_valid']} of {q['n_agents']}", "valid on the first try, about US$0.04"),
             (f"{100 * q['duplicate_answer_share']:.0f}%", "of agents gave identical answer sets")]
    for j, (big, small) in enumerate(stats):
        y = Inches(1.55 + j * 1.27)
        text(s, Inches(8.6), y, Inches(4.2), Inches(1.2),
             [[(big, {"bold": True, "size": 30, "color": NAVY})], [(small, {"size": 14, "color": GREY})]], size=14,
             line=1.0)
    footer(s, 7); notes(s, entries[7])

    # --- 8. Comparison ------------------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[8]["title"])
    picture(s, ROOT / "reports" / "figures" / f"{RUN_STEM}_fig2_effect_sizes.png", MARGIN, Inches(1.4),
            h=Inches(5.3), name="Effect size chart")
    verdicts = [("Size", "Exaggerated", f"{r_text(s_a.r)} vs {r_text(s_o.r)} original; Fisher z p < .001"),
                ("Attention", "Not significant", f"{r_text(a_a.r)}, same sign as people"),
                ("Arousal", "Reproduced", f"{r_text(v_a.r)} vs {r_text(v_o.r)} original"),
                ("Mood (control)", "Halo", f"{r_text(m_a.r)} where people showed none")]
    for j, (measure, verdict, detail) in enumerate(verdicts):
        y = Inches(1.5 + j * 1.12)
        chip = box(s, Inches(8.45), y, Inches(1.95), Inches(0.5), ROYAL if verdict == "Reproduced" else NAVY,
                   name=f"Verdict {measure}", radius=0.5)
        shape_text(chip, verdict, size=13)
        text(s, Inches(10.55), y - Inches(0.02), Inches(2.3), Inches(1.0),
             [[(measure, {"bold": True, "size": 16})], [(detail, {"size": 12, "color": GREY})]], size=12, line=1.0)
    text(s, Inches(8.45), Inches(6.0), Inches(4.3), Inches(0.8),
         f"Size difference {tost['diff']:.2f} in, 90% CI [{tost['ci90_low']:.2f}, {tost['ci90_high']:.2f}]: far "
         f"outside a plus or minus 0.5 in band. Repeat run: r = +.63.", size=12, color=GREY)
    footer(s, 8); notes(s, entries[8])

    # --- 9. Live demo (navy) -----------------------------------------------
    s = prs.slides.add_slide(blank); background(s, NAVY)
    text(s, MARGIN, Inches(0.45), W - 2 * MARGIN, Inches(0.9), "Live demo: the dashboard", size=32, bold=True,
         color=WHITE, name="Title", anchor=MSO_ANCHOR.MIDDLE)
    text(s, MARGIN, Inches(1.7), W - 2 * MARGIN, Inches(0.8), "gp4-saturation.streamlit.app", size=36, bold=True,
         color=CORAL)
    for j, (head, body) in enumerate((("Human vs AI", "Hover for the exact effect sizes"),
                                      ("Explore data", "Every agent's answers; filter by condition"),
                                      ("Open to anyone", "Code, data and dashboard are public"))):
        x = MARGIN + j * Inches(4.1)
        card = box(s, x, Inches(3.2), Inches(3.9), Inches(1.9), "17396F", name=f"Demo card {j + 1}")
        text(s, x + Inches(0.3), Inches(3.45), Inches(3.3), Inches(1.5),
             [[(head, {"bold": True, "size": 20, "color": WHITE})], [(body, {"size": 15, "color": PALE})]], size=15)
    text(s, MARGIN, Inches(5.6), W - 2 * MARGIN, Inches(0.5),
         "No internet? Slides 7 and 8 show the same results.", size=14, color=PALE)
    footer(s, 9, dark=True); notes(s, entries[9])

    # --- 10. Why ------------------------------------------------------------
    s = prs.slides.add_slide(blank); background(s, WHITE)
    title(s, entries[10]["title"])
    cards = [("No eyes, no arousal", "A language model has no visual system or nervous system to be aroused."),
             ("Learned associations", "Vivid looks premium, premium looks bigger: patterns from text and images "
                                      "it was trained on."),
             ("The most typical answer", "It returns the modal answer almost every time, so the human spread "
                                          "disappears.")]
    for j, (head, body) in enumerate(cards):
        x = MARGIN + j * Inches(4.1)
        box(s, x, Inches(1.6), Inches(3.9), Inches(2.75), ICE, name=f"Reason {j + 1}")
        num = box(s, x + Inches(0.3), Inches(1.85), Inches(0.6), Inches(0.6), NAVY, shape=MSO_SHAPE.OVAL,
                  name=f"Reason {j + 1} number")
        shape_text(num, str(j + 1), size=16)
        text(s, x + Inches(0.3), Inches(2.65), Inches(3.3), Inches(1.6),
             [[(head, {"bold": True, "size": 18, "color": NAVY})], body], size=14)
    text(s, MARGIN, Inches(4.75), Inches(3.2), Inches(1.3), "20 of 20", size=54, bold=True, color=NAVY,
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, MARGIN + Inches(3.3), Inches(4.85), Inches(8.5), Inches(1.2),
         [[("diagnostic agents explained their answer by colour and style.", {"size": 18})],
          [("None mentioned size. The model never says the vivid laptop looks bigger, yet it answers as if it "
            "does.", {"size": 15, "color": GREY})]], size=16)
    footer(s, 10); notes(s, entries[10])

    # --- 11. What we learned (navy) ----------------------------------------
    s = prs.slides.add_slide(blank); background(s, NAVY)
    text(s, MARGIN, Inches(0.45), W - 2 * MARGIN, Inches(0.9), "What we learned", size=32, bold=True,
         color=WHITE, name="Title", anchor=MSO_ANCHOR.MIDDLE)
    lists = [("Reproduced", ["Direction of every effect", f"Arousal effect ({r_text(v_a.r)} vs {r_text(v_o.r)})"]),
             ("Not reproduced", ["Size of the size effect (2x)", "Attention mechanism", "Mood control (halo)",
                                 "Human spread of answers"])]
    for j, (head, items_) in enumerate(lists):
        x = MARGIN + j * Inches(6.15)
        box(s, x, Inches(1.55), Inches(5.95), Inches(2.95), "17396F", name=f"{head} card")
        text(s, x + Inches(0.35), Inches(1.75), Inches(5.3), Inches(2.6),
             [[(head, {"bold": True, "size": 22, "color": CORAL if j else WHITE})]] +
             [[(f"·  {it}", {"size": 17, "color": WHITE})] for it in items_], size=17)
    take = box(s, MARGIN, Inches(4.8), W - 2 * MARGIN, Inches(0.95), WHITE, name="Takeaway")
    shape_text(take, "AI agents: a fast, cheap first look at a visual cue. Not a substitute for people, and not "
                     "a source of effect sizes.", size=18, color=NAVY)
    text(s, MARGIN, Inches(6.0), W - 2 * MARGIN, Inches(0.7),
         "Limitations: one model and one prompt; published summary statistics, no raw human data; small on-screen "
         "image; an AI has no real attention or arousal.", size=13, color=PALE)
    footer(s, 11, dark=True); notes(s, entries[11])

    # --- 12. Questions (navy) ----------------------------------------------
    s = prs.slides.add_slide(blank); background(s, NAVY)
    text(s, MARGIN, Inches(2.0), W - 2 * MARGIN, Inches(1.3), "Questions?", size=60, bold=True, color=WHITE,
         name="Title")
    text(s, MARGIN, Inches(3.6), W - 2 * MARGIN, Inches(1.4),
         [[("Dashboard  ", {"bold": True, "color": PALE}), (T.DASHBOARD_URL, {"color": CORAL})],
          [("Code and data  ", {"bold": True, "color": PALE}), (T.REPO_URL, {"color": WHITE})]], size=20)
    text(s, MARGIN, Inches(5.6), W - 2 * MARGIN, Inches(0.8),
         "Built with AI assistance from Claude (Anthropic): code, analysis and drafts were produced with Claude and "
         "reviewed by the team. Simulated participants: OpenAI GPT-4o mini.", size=12, color=PALE)
    footer(s, 12, dark=True); notes(s, entries[12])

    out = HERE / f"MBAN5640_GP4_Group01_Slides_SONI-TONER-WARNER_{mban_docx.halifax_now()[0]}.pptx"
    prs.save(out)
    return out


if __name__ == "__main__":
    print("Written:", build())
