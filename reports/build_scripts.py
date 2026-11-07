"""
build_scripts.py: build the two speaker scripts (Option A slides + demo, Option B dashboard only) as Word files.

Where it fits
-------------
Reads the talk text from reports/talk_content.py (the same text as the slides'
speaker notes) and writes two house-style .docx scripts with a timing plan,
a pre-flight checklist, the words per speaker with stage directions, a
"running long" cut list and likely questions.

How to run:  python reports/build_scripts.py
Out: reports/MBAN5640_GP4_Group01_Script-OptionA-Slides_..._<stamp>.docx and ...Script-OptionB-Dashboard...
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mban_docx as M  # noqa: E402
import talk_content as T  # noqa: E402

AI_TEXT = ("Prepared with AI assistance from **Claude (Anthropic)**: the talk was drafted with Claude from the "
           "project's analysis and checked against the data; the team edits and delivers it.")

CHECKLIST_COMMON = [
    f"10 minutes before: open {T.DASHBOARD_URL} once. Free Streamlit apps go to sleep and take about a minute "
    "to wake up.",
    "Sidebar Data file must read **REAL | main | 2026-11-05 19:10** (the primary run) with the green "
    "\"Real data selected\" box.",
    "Browser zoom about 125% so the back row can read it; close other tabs and notifications.",
    "Backup if the internet fails: the PDF of the 2-page report and the slide deck on a USB stick or laptop.",
    "Timer visible to the presenter. Hard stop at 12:00; aim to finish at 11:00.",
]


def option_doc(name, label, entries, unit, checklist_extra, cuts):
    stamp_file, stamp_text = M.halifax_now()
    total = sum(T.seconds(e) for e in entries)
    doc = M.new_document(
        title=f"Presentation Script, {label}", doc_name=f"GP4 - Script {name}",
        subtitle="Can AI agents see what people see? Hagtvedt and Brasel (2017) with AI agents",
        subsubtitle=f"about {T.mmss(total)} of speaking at {T.WORDS_PER_MINUTE} words a minute, plus 3 minutes of Q&A",
        course_line="MBAN 5640 Visualization & Data Mining · Group Project 4 · Presentation, November 28, 2026",
        status_tail="from reports/talk_content.py", ai_text=AI_TEXT, stamp_text=stamp_text)
    M.bluf(doc, [f"**Speak about {T.mmss(total)}**; the slot is 12 minutes plus 3 for questions. If you are "
                 "behind at the checkpoints below, use the cut list.",
                 "Speaker split is a suggestion: Krishna opens and closes, Michael explains the AI system, "
                 "Dale presents the results. Swap freely, but keep the hand-off lines.",
                 "Words in **[brackets]** are actions, not spoken."])
    M.heading(doc, "1. Timing plan")
    rows, clock = [], 0.0
    for e in entries:
        clock += T.seconds(e)
        rows.append([str(e[unit]) if unit == "slide" else e[unit],
                     e.get("title", e.get("page", "")) if unit == "slide" else "",
                     T.SPEAKERS[e["speaker"]], T.mmss(T.seconds(e)), T.mmss(clock)])
    if unit == "slide":
        M.table(doc, ["Slide", "Title", "Speaker", "Length", "Clock"], rows, widths=[800, 5040, 1900, 1200, 1300])
    else:
        M.table(doc, ["Dashboard page", "", "Speaker", "Length", "Clock"],
                [[r[0], "", r[2], r[3], r[4]] for r in rows], widths=[3000, 2840, 1900, 1200, 1300])
    M.heading(doc, "2. Before you start")
    M.bullets(doc, CHECKLIST_COMMON + checklist_extra)
    M.heading(doc, "3. The script")
    for e in entries:
        head = f"Slide {e['slide']}: {e['title']}" if unit == "slide" else f"Page {e['page']}"
        M.heading(doc, f"{head} · {T.SPEAKERS[e['speaker']]} · about {T.mmss(T.seconds(e))}", level=2)
        for a in e["actions"]:
            M.para(doc, f"**[{a}]**", color=M.NAVY)
        if e["text"]:
            M.para(doc, e["text"])
    M.heading(doc, "4. If you are running long")
    M.bullets(doc, cuts)
    M.heading(doc, "5. Likely questions")
    for question, answer in T.QA:
        M.para(doc, f"**{question}** {answer}")
    return M.save(doc, HERE, f"MBAN5640_GP4_Group01_Script-{name}_SONI-TONER-WARNER", stamp_file=stamp_file)


def build():
    a = option_doc("OptionA-Slides", "Option A: slides with a short live demo", T.OPTION_A, "slide",
                   ["Open the deck in Slide Show; the dashboard is already open in a browser tab for slide 9.",
                    "Speaker notes in the deck hold the same words as this script (Presenter View)."],
                   ["Skip the live demo (slide 9): say \"the dashboard is public at the link on the last slide\" "
                    "and go to slide 10. Saves about 1 minute.",
                    "On slide 8, drop the sentence about the equivalence test and the repeat run (about 25 seconds).",
                    "On slide 6, drop the sentence about the diagnostic run (about 15 seconds)."])
    b = option_doc("OptionB-Dashboard", "Option B: live dashboard walkthrough", T.OPTION_B, "page",
                   ["Start on page 1. Overview, scrolled to the top, sidebar visible.",
                    "Practise the clicks once: tabs on page 4, hover on page 5, filter on page 6."],
                   ["Skip page 6 (Explore data); move its \"why\" sentences to page 5. Saves about 45 seconds.",
                    "On page 3, do not open the Deviations expander; just name the deviations (about 15 seconds).",
                    "On page 5, drop the sentence about the equivalence test and the repeat run (about 25 seconds)."])
    return a, b


if __name__ == "__main__":
    for path in build():
        print("Written:", path)
