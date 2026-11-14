"""
build_walkthrough.py: build the GP4 Code Walkthrough (a module-by-module guide) as a Word file.

Where it fits
-------------
Documentation for deliverable A (source code). Explains each part of the
pipeline in plain language, for teammates and for presentation Q&A. Code
excerpts are pulled from the source files at build time (by function name),
so the document always shows the code as it is. Test counts come from pytest.

How to run (from the project folder, .venv active)
--------------------------------------------------
    python -m pip install -r reports/requirements-report.txt   # once
    python reports/build_walkthrough.py

Out: reports/MBAN5640_GP4_Group01_CodeWalkthrough_SONI-TONER-WARNER_<YYYYMMDD_HHMM>.docx
Writing rules: no em dashes; plain language; define jargon on first use.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import mban_docx as M  # noqa: E402

RUN_STEM = "gp4_main_20261105_191049"  # CONFIG: the PRIMARY main run


# ---------------------------------------------------------------------------
# 1. Helpers: live code excerpts and test counts
# ---------------------------------------------------------------------------
def excerpt(rel_path: str, name: str, keep_docstring: bool = False, max_lines: int | None = None) -> list[str]:
    """Source lines of one function (or Class.method) from a project file, read now.

    The docstring is dropped by default (the walkthrough explains it in prose).
    Indentation is removed so a method reads like a function.
    """
    path = ROOT / rel_path
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    nodes: dict[str, ast.AST] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef):
            nodes[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    nodes[f"{node.name}.{sub.name}"] = sub
    if name not in nodes:
        raise KeyError(f"{name} not found in {rel_path}: the code changed; update build_walkthrough.py.")
    node = nodes[name]
    start = node.lineno - 1
    if node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    body = lines[start:node.end_lineno]
    if not keep_docstring and ast.get_docstring(node):
        doc = node.body[0]
        cut_from, cut_to = doc.lineno - 1 - start, doc.end_lineno - start
        body = body[:cut_from] + body[cut_to:]
    indent = min(len(l) - len(l.lstrip()) for l in body if l.strip())
    body = [l[indent:] for l in body]
    if max_lines and len(body) > max_lines:
        body = body[:max_lines] + ["    ...  (continues in the file)"]
    return body


def code(doc, rel_path, name, caption, **kw):
    """Add a live code excerpt with a caption naming the file and function.

    The caption is kept on the same page as the start of the code (Word's "keep with next").
    """
    first_new = len(doc.paragraphs)  # the caption is the first paragraph code_block adds
    M.code_block(doc, excerpt(rel_path, name, **kw), f"{rel_path} · {name}(), {caption}")
    doc.paragraphs[first_new].paragraph_format.keep_with_next = True


def test_counts() -> Counter:
    """Number of tests per test file, from pytest's own collection (no tests are run)."""
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return Counter(line.split("::")[0].replace("\\", "/") for line in out.splitlines() if "::" in line)


def line_count(rel_path: str) -> int:
    return len((ROOT / rel_path).read_text(encoding="utf-8").splitlines())


# ---------------------------------------------------------------------------
# 2. The document
# ---------------------------------------------------------------------------
def build() -> Path:
    stamp_file, stamp_text = M.halifax_now()
    counts = test_counts()
    total_tests = sum(counts.values())
    quality = json.loads((ROOT / "data" / "real" / f"{RUN_STEM}_analysis" / "details.json")
                         .read_text(encoding="utf-8"))["quality"]
    cfg = json.loads((ROOT / "config" / "config_v1.json").read_text(encoding="utf-8"))

    doc = M.new_document(
        title="GP4 Code Walkthrough", doc_name="GP4 - Code Walkthrough",
        subtitle="Can AI agents see what people see? Hagtvedt and Brasel (2017) with AI agents",
        subsubtitle="module-by-module guide to the pipeline, for the team and for presentation Q&A",
        course_line="MBAN 5640 Visualization & Data Mining · Group Project 4 · Deliverable A (source code)",
        status_tail="from the current code (excerpts read from the source files)",
        ai_text=("Prepared with AI assistance from **Claude (Anthropic)**. The pipeline code, tests, dashboard and "
                 "this walkthrough were drafted with Claude and reviewed by the team. Code excerpts are copied "
                 "from the source files automatically when the document is built."),
        stamp_text=stamp_text)

    M.bluf(doc, [
        "**One pipeline, one job per file.** Settings, agents, prompt, model call, answer check, run engine, "
        "analysis, figures and dashboard each live in their own module under `src/gp4/` and `app/`.",
        "**Integrity is enforced by code, not memory.** The prompt files are fingerprinted, forbidden words are "
        "blocked before any call, the image goes in without its file name, and a live run cannot start until the "
        "settings are signed off.",
        f"**Every answer is checked and logged.** A JSON schema limits the model to valid answers, Python checks "
        f"them again, and every attempt is saved. The main run: {quality['n_valid']} of {quality['n_agents']} "
        f"valid, {quality['n_retried']} retries.",
        f"**{total_tests} automated tests** check the statistics against the published values, the prompt rules, "
        "the engine, the figures and every dashboard page.",
    ])

    # 1. Pipeline ----------------------------------------------------------
    M.heading(doc, "1. The pipeline at a glance")
    M.para(doc, "Each AI agent is one simulated participant: a single, independent call to a vision-language model "
                "(an AI model that reads images and text) that sees one laptop image and answers the original "
                "questions. The code turns settings into agents, agents into model calls, answers into a dataset, "
                "and the dataset into statistics, figures and a dashboard.")
    M.code_block(doc, [
        "config/config_v1.json --> agents.py      roster: 39 high / 38 low, seeded; 49% male persona",
        "prompts/v1/*.txt ------> prompts.py     exact text, forbidden-word check, fingerprint",
        "stimuli/stim_A|B.png --> llm_client.py  ONE call: system text + ONE image + task text; JSON schema",
        "                         validate.py    whole numbers in range? retry up to 3 tries",
        "                         run_experiment.py --> data/real/gp4_<label>_<run_id>.csv, _raw.jsonl,",
        "                                               _config.json, _run.log",
        "                         analysis.py + plots.py --> tables, figures, dashboard, report",
    ], "The flow from settings to results (README.md has the same picture)")
    modules = [
        ("config.py", "Load and check every setting; fingerprint prompts and images; block unsigned live runs",
         "src/gp4/config.py"),
        ("agents.py", "Create the roster: condition, persona and ID for every agent", "src/gp4/agents.py"),
        ("prompts.py", "Assemble the exact prompt; forbidden-word check; prompt fingerprint", "src/gp4/prompts.py"),
        ("llm_client.py", "One call to the model (real or mock); never sees a file name", "src/gp4/llm_client.py"),
        ("validate.py", "Parse and check the answer; decide whether to retry", "src/gp4/validate.py"),
        ("run_experiment.py", "Run every agent, log every attempt, write the files", "src/gp4/run_experiment.py"),
        ("costs.py", "Estimate the cost before a live run; report the real cost after", "src/gp4/costs.py"),
        ("benchmarks.py", "The published human results, checked against the papers", "src/gp4/benchmarks.py"),
        ("analysis.py", "ANOVA, effect sizes, human-AI tests, equivalence, mediation, outcome label",
         "src/gp4/analysis.py"),
        ("plots.py", "Every figure, in a dashboard (Plotly) and a report (Matplotlib) version", "src/gp4/plots.py"),
        ("streamlit_app.py", "The seven-page dashboard", "app/streamlit_app.py"),
    ]
    M.table(doc, ["Module", "Job", "Lines"],
            [[f"`{m}`", job, str(line_count(p))] for m, job, p in modules], widths=[2300, 6900, 1040])

    # 2. Running it ---------------------------------------------------------
    M.heading(doc, "2. How to run it")
    M.para(doc, "Every command runs from the project folder in a terminal, after turning on the project's Python "
                "environment with `.\\.venv\\Scripts\\Activate.ps1` (the prompt then starts with `(.venv)`). Only "
                "`run_live.py` spends money, and it asks first.")
    M.table(doc, ["Command", "What it does", "Cost"], [
        ["`python -m pytest`", f"Runs all {total_tests} automated checks (about 20 seconds)", "none"],
        ["`python scripts/show_prompt.py --agent 5`", "Prints the exact prompt one agent would receive", "none"],
        ["`python scripts/run_dry.py`", "Whole experiment with fake (mock) answers, saved in `data/mock/`", "none"],
        ["`python scripts/run_live.py --run-label main`", "Real run: shows the plan and cost, then asks you to type "
                                                           "the label to start", "about US$0.04"],
        ["`python scripts/analyze.py --latest real`", "Tables, summary and six figures for the newest real run",
         "none"],
        ["`streamlit run app/streamlit_app.py`", "The dashboard at http://localhost:8501", "none"],
        ["`python reports/build_report.py`", "Rebuilds the 2-page report (also `build_slides.py`, "
                                             "`build_scripts.py`, `build_walkthrough.py`)", "none"],
    ], widths=[3900, 5240, 1100])

    # 3. Settings -------------------------------------------------------------
    M.heading(doc, "3. Settings and integrity: config.py")
    M.para(doc, f"All experimental settings live in one file, `config/config_v1.json`: model "
                f"`{cfg['model']}`, temperature {cfg['temperature']} (how random the answers are), image detail "
                f"`{cfg['image_detail']}`, seed {cfg['seed']}, {int(cfg['pct_male'] * 100)}% male personas, up to "
                f"{cfg['max_attempts']} attempts per agent. Dale signed them off on {cfg['signed_off_date']}, "
                "before any live run. The course brief forbids changing settings to make AI results look more "
                "human, so any change would become a new version (`config_v2.json`) with a reason in "
                "`CHANGELOG.md`.")
    M.para(doc, "`load_config()` reads the file, checks every value (right type, allowed range), and returns a "
                "frozen `Config` object that no other code can change. It also checks three things that protect "
                "the experiment:")
    M.bullets(doc, [
        "**The prompt files have not changed.** Each file's SHA-256 fingerprint (a 64-character code that "
        "changes if even one character of the file changes) is stored in the config. If a word changes, the "
        "run is blocked.",
        "**The arousal scale in the config matches the prompt wording** (9 points). The code refuses to run if "
        "they disagree.",
        "**The two images are the instructor's files, byte for byte**, checked against their fingerprints in "
        "`stimuli/stimulus_key.json`.",
    ])
    code(doc, "src/gp4/config.py", "verify_prompt_files", "blocks a run if a signed-off prompt file changed")
    M.para(doc, "`require_sign_off()` stops `run_live.py` before any paid call if `signed_off` is not true in the "
                "config.")

    # 4. Agents ---------------------------------------------------------------
    M.heading(doc, "4. Creating the agents: agents.py")
    M.para(doc, "`build_roster()` creates the list of participants for one run. Each agent gets an ID (M001 to "
                "M077 for the main run), a condition (high or low saturation) and a persona gender. One random "
                "number generator, started from the fixed seed, is used in a fixed order: conditions first, then "
                "genders. So the same seed always gives the same roster, and anyone can reproduce the assignment.")
    M.bullets(doc, [
        "**Conditions:** 39 high and 38 low for 77 agents (an odd agent goes to high), then shuffled.",
        "**Persona quota within each condition:** 49% male in the original sample, so 19 of 39 high and 19 of "
        "38 low agents are male. Balancing inside each condition means gender cannot be mixed up with condition.",
    ])
    code(doc, "src/gp4/agents.py", "assign_genders", "the male quota is applied inside each condition")

    # 5. Prompt ---------------------------------------------------------------
    M.heading(doc, "5. The prompt: prompts.py and prompts/v1/")
    M.para(doc, "The prompt (the text instructions sent to the model) is the team's signed-off version 1, copied "
                "word for word into `prompts/v1/`: a one-line system text (\"You are a participant in a research "
                "study.\" plus the persona sentence), the task text with the original three questions and scales, "
                "and the answer format. `assemble_prompt()` fills in the persona and the answer format, checks the "
                "result, and computes the prompt fingerprint that is stored on every data row (`prompt_sha`).")
    M.para(doc, "`check_hygiene()` enforces the rule that the model must never learn the manipulation or the "
                "hypothesis. It scans the finished text for forbidden terms such as \"satur\", \"vivid\", "
                "\"colour\", \"hypothes\", the authors' names, \"stim_\" and \".png\", and stops the run if any "
                "appear.")
    code(doc, "src/gp4/prompts.py", "check_hygiene", "the forbidden-word check runs on every prompt before any call")
    M.callout(doc, "Integrity rule · No condition leaks",
              "The images are stored as `stim_A.png` (high) and `stim_B.png` (low). Which is which lives only in "
              "`stimuli/stimulus_key.json`, which is never sent. The prompt contains no file path, and the image "
              "is sent as raw data without its name (section 6).")

    # 6. Model call ---------------------------------------------------------------
    M.heading(doc, "6. Calling the model: llm_client.py")
    M.para(doc, "`OpenAIClient` makes one call per attempt to OpenAI's Responses API. The request has two parts: "
                "the system text, then a user message containing **one image followed by the task text**. The "
                "model really looks at the picture; there is no step where a text description replaces it. "
                "`store=False` asks OpenAI not to keep the conversation, and no earlier response is ever passed "
                "in, so agents cannot share memory.")
    code(doc, "src/gp4/llm_client.py", "OpenAIClient._request_kwargs", "one image, then the task text, then the "
                                                                        "answer format")
    M.bullets(doc, [
        "**The image goes in as a data URL** (the picture's bytes written as text, `data:image/png;base64,...`) "
        "with no file name, so the name cannot give the condition away.",
        "**A JSON schema** (a formal description of the answer's shape) lists the only allowed values for each "
        "answer, for example the whole numbers 10 to 20 for screen size. With `strict: True` the model can only "
        "return answers that fit, like a paper form with only valid boxes.",
        "**Errors are sorted.** Ordinary failures (a timeout, a server hiccup) come back as a failed result and "
        "are retried. Problems a retry cannot fix (a bad key, an unknown model) raise `FatalClientError`, which "
        "stops the whole run so no money is spent on doomed calls.",
        "**If a model rejects the temperature setting**, the client stops sending it and records that, rather "
        "than failing.",
        "**MockClient** is a fake model for dry runs. It gives random but repeatable answers and can act out "
        "problems on purpose (identical answers, out-of-range numbers, answers wrapped in code fences, failed "
        "calls) so the rest of the pipeline can be tested for free.",
    ])
    code(doc, "src/gp4/llm_client.py", "build_json_schema", "each rating may only be a whole number in its scale")

    # 7. Validation -----------------------------------------------------------
    M.heading(doc, "7. Checking every answer: validate.py")
    M.para(doc, "The schema should already prevent bad answers, but Python checks every one again. "
                "`check_response()` reads the raw text, removes a code fence if the model added one, finds the "
                "JSON object (the answer in key-value form), and lists every problem: a missing or extra key, a "
                "value that is not a whole number, or a value outside its scale.")
    code(doc, "src/gp4/validate.py", "check_answers", "an empty list of problems means the answer is valid")
    M.para(doc, "`is_whole_number()` rejects 15.0, \"15\" and True. (In Python, True counts as the number 1, so "
                "it has to be excluded on purpose.) `should_retry()` is the single retry rule: try again only if "
                f"the last answer was invalid and fewer than {cfg['max_attempts']} attempts have been made. An "
                "agent that still fails stays in the data with `valid = False` and is left out of the analysis, "
                "so no participant disappears without a trace.")

    # 8. Engine ---------------------------------------------------------------
    M.heading(doc, "8. Running the experiment: run_experiment.py")
    M.para(doc, "`run_experiment()` is the engine used by both the dry run and the live run. It loads the "
                "settings, builds the roster, reads both images once, then runs the agents, "
                f"{cfg['workers']} at a time. Each agent is handled by `run_one_agent()`: build the "
                "request, call the model, check the answer, retry if needed, and log every attempt.")
    code(doc, "src/gp4/run_experiment.py", "run_one_agent", "one agent: call, check, retry, log", max_lines=42)
    M.bullets(doc, [
        "**A shared stop signal.** If any agent hits a fatal error, `stop.set()` tells every other agent to stop "
        "before its next call. An automated test found that queued agents kept calling after an error; this "
        "fixed it.",
        "**Four files per run, never overwritten.** Each run gets an ID from its start time, so a second run "
        "makes new files instead of replacing old ones: the tidy `.csv` (one row per agent), the `_raw.jsonl` "
        "log (every attempt's raw output, tokens and timing), the `_config.json` snapshot (every setting, the "
        "exact prompt variants and library versions) and the `_run.log` progress log.",
        "**Mock and real data are kept apart.** Dry runs write to `data/mock/` (never uploaded) with "
        "`dry_run = True` on every row; live runs write to `data/real/`.",
    ])

    # 9. Live runs ------------------------------------------------------------
    M.heading(doc, "9. Live runs and cost: run_live.py and costs.py")
    M.para(doc, "`scripts/run_live.py` is the only entry point that calls the real model. Its safeguards run "
                "in order:")
    M.bullets(doc, [
        "Settings, prompt files and images are verified, and the config must be signed off.",
        "The API key must be present. It is read from the `.env` file and never printed.",
        "The plan is printed: model, settings, number of agents and calls, and the expected and worst-case "
        "cost (from `costs.py` and `config/pricing.json`).",
        "If a run with the same label already exists, it is listed with a reminder that the FIRST run is the "
        "one to report, and you must type \"main again\" instead of \"main\" to go ahead.",
        "You must type the label to start; anything else cancels with no calls made.",
    ], numbered=True)
    M.para(doc, "After the run it prints the parse rate (share of valid answers), the answers, and the real "
                "tokens and cost, added up from every attempt in the log. The estimate was within 1% of the real "
                "token count in the smoke test.")

    # 10. Analysis -------------------------------------------------------------
    M.heading(doc, "10. The statistics: analysis.py and benchmarks.py")
    M.para(doc, "`benchmarks.py` holds the published human results (means, standard deviations, F values and r "
                "for size, attention, arousal and mood) from the original study and the replication, each checked "
                "against the papers. `analyze()` runs eight numbered steps on one run's data:")
    M.table(doc, ["Step", "Function", "What it answers"], [
        ["1", "`data_quality()`", "How many agents, how many valid, retries, identical answer sets"],
        ["2", "`describe()`", "Mean, standard deviation, median and range by measure and condition"],
        ["3", "`anova_table()`", "Do high and low differ? One-way ANOVA (a test of whether group means differ "
                                 "more than chance), with r, Cohen's d and confidence intervals"],
        ["4", "`comparison_table()`", "Is the AI effect the same size as the human effect? Fisher z test "
                                      "against the original and the replication"],
        ["5", "`tost()`", "If size showed no effect, is it truly zero? Equivalence test within plus or minus 0.5 "
                          "inch"],
        ["6", "`mood_placebo()`", "Did mood, which should not change, change? (A halo check)"],
        ["7", "`classify_outcome()`", "Which pattern: A original, B replication, C blind, D exaggerated/halo"],
        ["8", "`mediation_if_warranted()`", "Does saturation work through arousal and attention? Only if a size "
                                            "effect appears; bootstrap with 10,000 resamples"],
    ], widths=[700, 2900, 6640])
    M.para(doc, "The key formula is the one the replication paper uses to turn every F into an effect size r, "
                "so the human and AI results are measured the same way:")
    code(doc, "src/gp4/analysis.py", "r_from_f", "r = sqrt(F / (F + df)); tests reproduce all six published values")
    code(doc, "src/gp4/analysis.py", "fisher_z_compare", "is the AI r different from a human r?")
    M.para(doc, "`classify_outcome()` applies the labels in a fixed order decided before any results: D "
                "(exaggerated or halo) is checked first, then A, B and C, otherwise Mixed. Our main run is D, "
                "because mood differed and the size effect was significantly larger than the original's.")

    # 11. Figures and dashboard --------------------------------------------------
    M.heading(doc, "11. Figures and the dashboard: plots.py and streamlit_app.py")
    M.para(doc, "`plots.py` builds every chart twice: an interactive Plotly version for the dashboard and a "
                "Matplotlib image for the report and slides, so both always show the same thing. The colours are "
                "fixed across the project and checked for colour-blind safety. Shape is used as well as colour: "
                "high saturation red circles, low violet triangles (hatched), original study blue squares, "
                "replication orange diamonds, AI green circles. Response scales are always drawn in full (for "
                "example 10 to 20 inches), so small gaps are never made to look large.")
    M.para(doc, "`app/streamlit_app.py` is the dashboard, live at https://gp4-saturation.streamlit.app/. It only "
                "reads saved files and never calls the model (the Run page is switched off in the config), so the "
                "public copy cannot spend money. It always opens on the first main run, using `primary_main()`, "
                "because the rule fixed before any results says the first run is the one to report. A repeat run "
                "is labelled as such, and mock data shows a red MOCK DATA banner.")
    M.table(doc, ["Page", "Shows"], [
        ["1. Overview", "Research question, marketing context, outcome label and headline table"],
        ["2. Original study", "Design, the two images, both human benchmarks and the proposed mechanism"],
        ["3. AI-agent system", "Pipeline diagram, settings, exact prompt, JSON schema, deviations"],
        ["4. Results", "Data quality, then each measure by condition with its test"],
        ["5. Human vs AI", "Effect sizes with confidence intervals for all three sources, tests, outcome"],
        ["6. Explore data", "Every agent's answers, filters, CSV download, variable dictionary"],
        ["7. Limitations", "What the simulation can and cannot show; cautions for researchers"],
    ], widths=[2500, 7740])

    # 12. Report pipeline ------------------------------------------------------
    M.heading(doc, "12. Report, slides and scripts: reports/")
    M.para(doc, "The written deliverables are built by code too, so their numbers cannot drift from the data. "
                "`build_report.py` reads the primary run's analysis files and writes the 2-page report; "
                "`build_slides.py` writes the 12-slide deck with speaker notes; `build_scripts.py` writes the "
                "two speaker scripts. All talk text lives in one file, `talk_content.py`, so the slide notes and "
                "both scripts always say the same thing. Edit the words there and rebuild. Older versions go in "
                "`reports/archive/`, which is not uploaded.")

    # 13. Tests ---------------------------------------------------------------
    M.heading(doc, "13. The tests")
    M.para(doc, f"`python -m pytest` runs {total_tests} checks with no API calls and no cost. The statistics "
                "tests are the most important: they confirm our formulas reproduce the published r values "
                "(original size .295, attention .249, arousal .299; replication .011, .238, .180) and the "
                "published confidence interval for the original size effect [.076, .487].")
    purposes = {
        "tests/test_analysis.py": "Effect sizes against published values and against scipy and statsmodels; "
                                  "TOST, mediation, outcome labels",
        "tests/test_validate.py": "Answer parsing, ranges, whole numbers, the retry rule",
        "tests/test_dashboard.py": "Every dashboard page renders, on mock and real data",
        "tests/test_prompts_config.py": "Prompt fingerprints, forbidden words, config checks, sign-off",
        "tests/test_run_experiment.py": "The engine with the mock model: retries, failures, fatal stop, files",
        "tests/test_assignment.py": "Seeded 39/38 assignment and the persona quota",
        "tests/test_plots.py": "Every figure in both versions, including zero-variance data",
        "tests/test_costs_live.py": "Cost estimates and the typed confirmation (no network)",
    }
    M.table(doc, ["Test file", "Tests", "What it checks"],
            [[f"`{Path(f).name}`", str(counts.get(f, 0)), why] for f, why in purposes.items()],
            widths=[2900, 800, 6540])

    # 14. Questions -----------------------------------------------------------
    M.heading(doc, "14. Likely questions about the code")
    for question, answer in [
        ("How do you know the model saw the image and not a description?",
         "The image bytes go directly into the request as an `input_image` (section 6). There is no "
         "describe-then-answer step anywhere in the code."),
        ("Could the model have learned which condition it was in?",
         "No label, file name or colour word is sent. `check_hygiene()` blocks forbidden terms, and the image is "
         "sent as raw data without its name."),
        ("Do agents remember each other?",
         "No. Every attempt is a fresh call with `store=False` and no earlier response attached."),
        ("What if the model gives a bad answer?",
         "The JSON schema prevents most; Python re-checks every answer and retries up to 3 times. Invalid agents "
         "stay in the file and are excluded from analysis. In the main run all 77 were valid on the first try."),
        ("Could you have changed settings after seeing the results?",
         "The settings were signed off before any live run, the prompt files are fingerprinted, and the first "
         "main run is reported by a rule set in advance. The accidental repeat run is recorded in CHANGELOG.md "
         "and shown only as a stability check."),
        ("How would someone reproduce your work?",
         "Clone the repository, install `requirements.txt`, run `python -m pytest`, then `run_dry.py` (free) or "
         "`run_live.py` with their own API key. The seed fixes the assignment; model answers vary by design."),
    ]:
        M.para(doc, f"**{question}** {answer}")

    return M.save(doc, HERE, "MBAN5640_GP4_Group01_CodeWalkthrough_SONI-TONER-WARNER", stamp_file=stamp_file)


if __name__ == "__main__":
    print("Written:", build())
