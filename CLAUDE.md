# CLAUDE.md: MBAN 5640 GP4 (Group 1), AI-agent simulation of a sensory marketing experiment

Standing brief for any Claude Code session in this repository. Read it first. The phase-by-phase build instructions and the dashboard spec are in `docs/GP4_ClaudeCode_Build_Prompt_v1.1.md`; read the section for the current phase before starting work. This file holds the rules that apply to every session.

## Next session: start here (updated 2026-11-07, 09:50)

**Built and committed 2026-11-07:**
- Forest chart labels fixed (labels now sit past the CI line, dashboard and PNG) and r labels round half up (.295 prints .30). New test; `pytest` 169 passed. Both main runs' fig2 PNGs regenerated (analysis tables unchanged).
- **Report (deliverable C):** `reports/build_report.py` -> `reports/MBAN5640_GP4_Group01_Report_..._20261107_0932.docx`, exactly 2 pages (checked in Word). All numbers read from the primary run's analysis files.
- **Slides (Option A):** `reports/build_slides.py` -> `..._Slides_..._20261107_0943.pptx`, 12 slides, speaker notes, checked via PowerPoint export.
- **Scripts:** `reports/build_scripts.py` -> Script-OptionA-Slides and Script-OptionB-Dashboard .docx (4 pages each). Talk text lives in ONE place, `reports/talk_content.py` (about 10:40 for A, 10:05 for B at 130 wpm). Speakers: Soni opens and closes, Toner AI system, Warner results (a suggestion).
- `reports/mban_docx.py` is a copy of Dale's house-style module; `reports/requirements-report.txt` (python-docx, python-pptx, installed in .venv only).
- Superseded drafts go in an `archive/` folder (git-ignored, Dale 2026-11-07): `reports/archive/` holds the 0927 and 0930 report drafts.

**Next:** Dale and team review report, slides and both scripts; pick Option A or B; edit `talk_content.py` and rebuild. Then optional: invite Soni and Toner (needs GitHub usernames); post hoc attention-item table; robustness run (823, about $0.43, after Dr. Zhang replies; Dale emailed the questions on 2026-11-07); copy finals to the OneDrive P4 `final/` folder.

Done earlier: dashboard live at https://gp4-saturation.streamlit.app/ (public repo; Streamlit Secrets EMPTY, never add a key). Laptop images in the public repo are fine (Dale, 2026-11-07). GP3 app (separate repo) is public and read-only with no key; its local folder has two uncommitted prompt-file deletions to look at before any GP3 commit.

## 0. Current status (update at the end of every phase)

- **Status:** Phase 6 complete (2026-11-05): `scripts/run_live.py` (plan, cost estimate, typed confirmation, warns on repeat runs), `src/gp4/costs.py`, `config/pricing.json`. Live SMOKE run approved and made: `data/real/gp4_smoke_20261105_190229.*`, 4/4 valid, schema and temperature accepted, ~$0.002. `pytest`: 167 passed. Settings signed off 2026-11-05.
- **Colours (fixed):** high #e34948 circle, low #6250d6 triangle/hatched; original #2a78d6 square, replication #eb6834 diamond, AI #1baf7a circle. Condition and source colours never share a chart.
- **gpt-4o-mini is listed as Deprecated by OpenAI** (no shutdown date; still works as of the smoke run). Do not switch models without Dale's approval and a v2 config.
- **MAIN run done** (2026-11-05 19:10, by Dale): `data/real/gp4_main_20261105_191049.*`, 77/77 valid, ~$0.04. THE run to report (PRIMARY). A REPEAT main run (19:17, `gp4_main_20261105_191715`) exists: accidental, recorded in CHANGELOG, shown only as a stability check; dashboard defaults to the primary and flags repeats. Outcome D: size r = +.70 (AI 15 vs 13 in, near-categorical), attention n.s. (items split 6,5 vs 5,6), arousal r = +.32, mood r = +.29 (halo), mediation not significant. Answers heavily collapsed (86% duplicate patterns). Figures in reports/figures/.
- **Phase 7 complete (2026-11-05):** repo https://github.com/WarnerMBAN/gp4-sensory-marketing (created private; made PUBLIC by Dale on 2026-11-06 so the dashboard could deploy, because the free Streamlit plan allows one private app and Dale's GP3 app holds it), branch main, first commit 961aa1e (88 files) pushed with Dale's approval; verified on GitHub (private, no .env/brief/reference/mock). Open optional items: Streamlit Community Cloud deployment (walk through separately); robustness run (823, ~$0.43); exploratory item-level attention table (post hoc, labelled); invite teammates as collaborators; questions to Dr. Zhang. Any later commit or push needs Dale's approval and `git status` shown first.
- **Live data so far:** smoke, main (primary 19:10), main repeat (19:17), diagnostic (19:23, 20/20 valid; explanations never mention size; low laptop called "vibrant" 9/10, "pink" 2/10). No robustness run.

## 1. What this project is

- **Course:** MBAN 5640 Visualization and Data Mining, Saint Mary's University (Sobey School of Business). Group Project 4, 25% of the grade (raised from 20% after the 10% exam was cancelled). Present Nov 28, 2026 (12 min plus 3 min Q&A).
- **Task:** use LLM agents as simulated participants in a sensory marketing experiment, then compare AI results with the original human results.
- **Study (Group 1):** Hagtvedt and Brasel (2017), *Journal of Consumer Research*, Study 3, "Color Saturation Increases Perceived Product Size". One red laptop image in high or low colour saturation, between-subjects. Measures: screen-size estimate (10 to 20 inches), attention (two items, 1 to 7, averaged), arousal and mood (1 to 9).
- **Human yardsticks that disagree:** the original (n = 77) shows size, attention and arousal effects. The replication by Motoki and Iseki (2022, n = 823) shows attention and arousal but NO size effect. Always report AI results against both.
- **Grading emphasis:** AI-agent design 25 points and human-AI comparison 25 points, out of 100.
- **Deliverables:** (A) source code, (B) AI dataset with variable dictionary, (C) 2-page report, (D) presentation. The Streamlit dashboard supports D.

## 2. How to work with me (Dale)

- I am a beginner with Python, Git, GitHub and Streamlit. Explain in plain language and define jargon the first time.
- Plain-spoken executive-briefing register: bottom line first, then support.
- **Work in gated phases.** Finish a phase, say what you built, how to run it, how to check it, then STOP and wait for my "go". Update section 0 of this file at the end of each phase.
- **Walk me through setup one step at a time.** One command, wait for my result, then the next.
- **Ask before anything hard to undo or that leaves my machine:** global installs, deleting files, API calls that cost money, creating a repository, committing, pushing. Never push without my explicit approval in that turn.
- **Complete, runnable files, verified.** Run what you build and show real output. Never say something is verified unless you ran it.
- **Flag uncertainty honestly.** If you are unsure, say so and test.
- Team-facing documents (README, report text): no em dashes. Credit AI assistance with a short attribution line crediting Claude (Anthropic).

## 3. Experiment integrity rules (never break these)

1. **No tuning to match humans.** The brief forbids changing settings to make AI results look more human. Settings are fixed in `config/config_v1.json` before any live run. Any later change is a new version (`v2`) with a CHANGELOG reason and my approval. Never overwrite v1 results.
2. **Prompt hygiene.** Never mention colour, saturation, conditions, hypotheses or the paper in anything sent to the model.
3. **Use the signed-off v1 prompt text verbatim** (`prompts/v1/`, copied unchanged from `reference/prompts/v1/`). Do not reword. Record the prompt hash on every data row.
4. **No condition leaks.** Images go in as `stim_A.png` (high) and `stim_B.png` (low). The mapping lives in `stimuli/stimulus_key.json` and is never sent to the model. No file path in the prompt text.
5. **One fresh call per agent, one image per agent, no memory between agents.** This reproduces the between-subjects design. Seeded random assignment (39 and 38 for n = 77).
6. **Send the real image (multimodal).** No describe-then-answer step; a text description would replace the stimulus. Images are sent unchanged. Padding both images to a common canvas is an explicit config option, off by default; if turned on, it is logged and declared in `DEVIATIONS.md`.
7. **Keep original questions and scales:** size whole inches 10 to 20; attention two items 1 to 7; arousal and mood 1 to 9. JSON output, validated in Python, retried up to the configured limit. Invalid agents stay in the file with `valid = False` and are excluded from analysis.
8. **Log for audit:** model, temperature (blank if the model does not accept one), prompt version and hash, seed, image hash, image detail, tokens, timestamps, raw output, attempts, errors.
9. **Mock data is never results.** Dry-run rows carry `dry_run = True`, live in `data/mock/` (git-ignored), and the dashboard shows a red MOCK DATA banner when they are loaded.
10. **Declare every deviation** from the original design in `DEVIATIONS.md` (small on-screen image, no snack incentive, gender and colour-blindness items omitted, an LLM has no real attention or arousal system).

## 4. Decisions so far

**Locked (from the requirements analysis):**
- Study 3 only. Direct multimodal OpenAI API behind a swappable `llm_client.py`. CrewAI is not used unless I say so.
- Main run n = 77. Run labels: smoke 4, main 77, diagnostic 20 (with an `explanation` field, used only to explain results), robustness 823 (replication scale, always labelled as robustness).
- Analysis: one-way ANOVA per measure, r, Cohen's d and confidence intervals, Fisher-z comparison with each human benchmark, equivalence test (TOST) if the size effect is null, mood placebo, outcome label A to D (A full original pattern, B replication pattern, C blind to saturation, D exaggerated or halo). Mediation only if the AI size effect appears.

**Arousal scale:** v1 uses the 9-point affect grid (matches the original paper and the instructor's prompt), shown in text as two 9-point scales (arousal, mood). Pending Dr. Zhang's confirmation. `arousal_max` in config must match the prompt version; the code refuses to run if they disagree.

**Phase 0 findings (verified against the PDFs, 2026-11-05):**
- All benchmark means, SDs and F values in the build prompt match the papers. r = sqrt(F / (F + df)) reproduces all six published r values; d from means and SDs reproduces 0.61, 0.51, 0.61 (original) and 0.02, 0.50, 0.36 (replication).
- **The replication measured arousal on a 7-point scale** (1 = Very calm, 7 = Very aroused; supplementary materials). Its arousal means (5.83 vs 5.41) cannot be compared with AI means on a 1 to 9 scale. Compare effect sizes (r, d) only.
- **Mood order is not stated in the original** ("M = 5.43 vs. M = 5.49, p > .87"). Record as "order assumed high vs low"; use for direction only, no test.
- **Per-cell n is not reported** in either paper. Use 39/38 (original) and 411/412 (replication) and label them "assumed" everywhere they appear.
- Replication sample differs from the original: Japanese online adults (mean age 40.8), surveyed in Japanese, 10 studies per person in about 10 minutes, attention-check exclusions (1,070 to 823). The student persona matches the original only.
- Stimuli: hashes of `reference/stimuli/` match `brief/Group-1/`. Laptop is the same size in both (297 px wide, 0.06% area difference); canvases differ (311 x 213 vs 315 x 216, white space only). Low-saturation laptop reads as pink. No metadata leaks.
- Extra cross-checks from the replication's table: published 95% CIs for r. Original: size [.076, .487], attention [.026, .448], arousal [.080, .490]. Replication: size [-.058, .079], attention [.172, .301], arousal [.113, .245]. Partial eta-squared: original .09, .06, .09; replication .000, .057, .033.

**Signed off by Dale on 2026-11-05 (now fixed for v1; see CHANGELOG.md):** model `gpt-4o-mini`, temperature 1.0, student persona with 49% male, `arousal_max` 9, equivalence bound plus or minus 0.5 inch, `image_detail` low (changed from the old notebook's `auto`), seed 20261114, gender quota within each condition, `max_attempts` 3, parallel workers 4. Model availability on our key is not yet checked (Phase 6 smoke test).

**Open (for Dr. Zhang or the team):** arousal 7-point (overview text) versus 9-point (original and prompt); whether CrewAI is expected; whether raw human data exists for Group 1 (none provided, so comparison is at summary level); whether a replication-scale robustness run is acceptable; division of work among the three team members.

## 5. Structure and code standards

- Layout: `config/`, `prompts/v1/`, `stimuli/`, `src/gp4/` (config, benchmarks, prompts, agents, llm_client, validate, run_experiment, analysis, plots), `app/streamlit_app.py`, `scripts/`, `data/real/`, `data/mock/`, `reports/figures/`, `tests/`, `docs/`. Keep one job per module.
- Comment heavily in plain English. Every file starts with a docstring: what it does, where it fits in the pipeline, inputs and outputs. Every function has a docstring. Number pipeline steps in comments. Mark editable settings with `# CONFIG:` or `# EDIT HERE:`.
- Settings live in `config_v1.json`, not buried in code. Use `pathlib` with project-relative paths. No hard-coded absolute paths.
- Fail loudly and helpfully: error messages say what is wrong and how to fix it.
- Statistics are checked, not assumed. Tests must reproduce the published r values (original size .295, attention .249, arousal .299; replication size about .011, attention about .238, arousal about .180) and the Fisher-z CI for the original size effect [.076, .487].
- Dashboard: every chart has a title, labelled axes and a one-line caption. Consistent colours across pages. Do not rely on colour alone. The dashboard reads saved CSVs and never calls the API unless the optional Run page is switched on in config (default off).

## 6. Security, Git and GitHub

- The API key is read only from the `OPENAI_API_KEY` environment variable (`.env` locally, Streamlit secrets when deployed). Never open, print, log or paste it, and never commit it. To check it is present, print only whether it was found and its length.
- `.gitignore` must exclude: `.env`, secrets, `__pycache__`, the virtual environment, `data/mock/`, `brief/` and `reference/`. `brief/` holds copyrighted papers and instructor files and is never committed.
- Before every commit show me `git status`. After the first commit run `git ls-files` and confirm nothing excluded is tracked. Repository is PUBLIC since 2026-11-06 (Dale's decision): never commit secrets, `.env`, `brief/`, `reference/` or mock data; anything pushed is world-readable. No force pushes.
- Project lives at `C:\MBAN5640\mban5640-GP4`, outside OneDrive. Final deliverables are copied by hand into the OneDrive P4 `final/` folder.

## 7. Reference material (read-only)

- `brief/` is the source of truth: the instruction document and rubric, the Group 1 instructions and instructor prompt, the two stimulus images, the original paper, the replication paper and its supplementary materials.
- `reference/` is earlier team work: signed-off v1 prompt files, prompt notes, variable dictionary, stimuli with hashes, the requirements analysis, the work summary and an earlier mock-tested notebook. If it disagrees with `brief/`, trust the brief and tell me.
- `docs/GP4_ClaudeCode_Build_Prompt_v1.1.md` is the build prompt: phases, target structure, dashboard spec, definition of done.
- Human benchmark numbers must be re-checked against the PDFs before they are hard-coded.

## 8. Environment and run commands (fill in as the project is built)

- **Environment:** Python 3.13.12 in `.venv` (project folder). Package versions pinned in `requirements.txt`. Activate first in every new terminal: `.\.venv\Scripts\Activate.ps1` (prompt shows `(.venv)`). Claude's own shell calls use `.venv/Scripts/python.exe` directly.
- Install: `python -m pip install -r requirements.txt`
- Tests: `pytest`
- Dry run (no API calls): `python scripts/run_dry.py`
- Live run (asks for confirmation first): `python scripts/run_live.py --run-label smoke`
- Analysis on a saved file: `python scripts/analyze.py <csv>`
- Dashboard: `streamlit run app/streamlit_app.py`
