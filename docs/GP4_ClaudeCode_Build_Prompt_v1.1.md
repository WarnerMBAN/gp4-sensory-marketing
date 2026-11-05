# GP4 Claude Code build prompt (v1.1)

**Version note:** v1.1 supersedes v1 (v1 is kept unchanged). Changes: (1) the team's signed-off v1 prompt text and earlier GP4 work are supplied as a read-only `reference/` folder and must be used verbatim; (2) the human benchmark table is complete (means, SDs, d, mood, mediation, assumed per-cell n); (3) persona default stated; (4) `brief/` and `reference/` are excluded from GitHub; (5) smaller fixes (temperature support, conditional mediation, run sizes, image handling, optional extras).

**How to use (do these before pasting):**
1. Create the project folder `C:\MBAN5640\mban5640-GP4`.
2. Copy your OneDrive `brief/` folder into it, so it sits at `<project>\brief\`.
3. Create `<project>\reference\` and copy into it, from the OneDrive P4 folder (these are read-only reference copies; do not edit them):
   - `working\prompts\v1\` (the four prompt text files) to `reference\prompts\v1\`
   - `working\prompts\PROMPT_NOTES_v1.md` to `reference\PROMPT_NOTES_v1.md`
   - `working\stimuli\` (`stim_A.png`, `stim_B.png`, `stimulus_key.json`) to `reference\stimuli\`
   - `working\data\VARIABLE_DICTIONARY.md` to `reference\VARIABLE_DICTIONARY.md`
   - `working\gp4_simulation.ipynb` to `reference\gp4_simulation.ipynb` (earlier notebook, built and tested on mock data only)
   - `notes\20261101_1430_GP4_Requirements_Analysis.md` and `notes\20261101_1515_GP4_Work_Summary_Requirements_and_Build.md` to `reference\`
4. Open `C:\MBAN5640\mban5640-GP4` in VS Code, start Claude Code, and paste everything below the line `=== PASTE FROM HERE ===`.

=== PASTE FROM HERE ===

# ROLE AND WORKING STYLE

You are helping me build a Python project for MBAN 5640 (Visualization and Data Mining, Sobey School of Business, Saint Mary's University), Group Project 4 (GP4). I am a beginner at GitHub, Streamlit and app deployment, and I have limited Python experience. Work like a patient senior colleague:

1. **Work in gated phases (listed in section 7).** At the end of each phase, STOP. Tell me in plain language what you built, how I run it, and how I check that it worked. Wait for me to say "go" before starting the next phase. Do not run ahead.
2. **Walk me through setup one step at a time**, not as a batch of steps I have to remember. Give one command, wait for me to confirm the result, then give the next.
3. **Ask before any action that is hard to undo or leaves my machine:** installing software globally, deleting files, running anything that spends API money, creating a GitHub repository, committing, or pushing. Never push to GitHub without my explicit approval in that same turn.
4. **Be honest about uncertainty.** If you are not sure something works, say so and test it. Do not tell me something is verified unless you actually ran it. Show me the real output.
5. **Deliver complete, runnable files**, not fragments. Every file you create must run as written. After creating files, run them and show me the result.
6. **Use a plain-spoken, executive-briefing tone.** Short sentences. Define any jargon the first time you use it.

# 1. THE PROJECT IN BRIEF

**Course task.** Use AI agents (LLM calls) to simulate human participants in a sensory marketing experiment, then compare the AI results with the original human results. Central research question: *To what extent can AI agents reproduce human perceptions, preferences and sensory marketing effects observed in the original experiment?*

**Our assigned study (Group 1).** Hagtvedt and Brasel (2017), *Journal of Consumer Research*, Study 3, "Color Saturation Increases Perceived Product Size". Participants see a laptop image in either **high** or **low** colour saturation (between-subjects: each person sees only one). They report:

| Measure | Question | Scale |
|---|---|---|
| Size estimate | Laptop screen size | Whole inches, 10 to 20 |
| Attention (2 items, averaged) | "The laptop is attention-getting." and "The laptop captures my attention." | 1 = Not at all to 7 = Definitely |
| Arousal | Affect grid arousal | 1 (low) to 9 (high) |
| Mood | Affect grid mood (placebo check) | 1 (displeasure) to 9 (pleasure) |

**Human benchmarks (two sources that disagree, report AI results against both).** Values below come from my earlier requirements analysis (`reference/`); they are starting values, not verified by you yet.

| Measure | Original (Hagtvedt and Brasel 2017, n = 77): high vs low, M (SD) | Original test | Replication (Motoki and Iseki 2022, n = 823): high vs low, M (SD) | Replication test |
|---|---|---|---|---|
| Size estimate (inches) | 15.28 (1.26) vs 14.41 (1.59) | F(1,75) = 7.13, r = .295, d = 0.61 | 15.46 (1.94) vs 15.42 (1.84) | F(1,821) = 0.095, p = .758, r = .011, d = 0.02. **Not replicated** |
| Attention (mean of 2 items, 1 to 7) | 5.19 (1.08) vs 4.66 (0.98) | F(1,75) = 4.95, r = .249, d = 0.51 | 5.30 (1.07) vs 4.75 (1.14) | F(1,821) = 49.24, r = .238, d = 0.50. Replicated |
| Arousal (affect grid, 1 to 9) | 6.05 (1.34) vs 5.14 (1.62) | F(1,75) = 7.35, r = .299, d = 0.61 | 5.83 (1.10) vs 5.41 (1.20) | F(1,821) = 27.54, r = .180, d = 0.36. Replicated |
| Mood (1 to 9), placebo | 5.43 vs 5.49, p > .87 (no difference expected) | null | not reported | n/a |

Further benchmark facts to include in `benchmarks.py`:
- r is computed as the square root of F / (F + df); d is computed from the means and SDs. Both should reproduce the published values.
- Per-cell sample sizes are NOT reported in either paper. Use these assumed splits and label them "assumed" everywhere they appear: original about 39 high and 38 low; replication about 411 and 412.
- The original also reports mediation (saturation to arousal to attention to size; PROCESS model 6): total indirect effect B = .53, 95% CI [.16, 1.01]. The replication skipped mediation because the size effect failed.
- The replication paper's own confidence interval for the original size effect, [.076, .487], is a useful cross-check for your r and Fisher-z code.
- Original setting for the "DEVIATIONS" list: group session, image projected on a large screen, paper questionnaire, about $1 of snacks, 77 usable participants (80 recruited, 49% male), undergraduates.

Before you hard-code any number, re-read the source PDFs in `brief/` and confirm each value. If a number in this prompt disagrees with the PDF, trust the PDF and tell me.

**Deliverables the course requires (the code must support all of them):**
- A. Source code, organised and documented well enough that another person can reproduce the simulation.
- B. The AI-generated dataset (CSV) with a variable dictionary and a description of the data-collection procedure.
- C. A 2-page report (background, human results, AI design and results, human-AI comparison, conclusion).
- D. A 12-minute presentation plus 3 minutes of Q&A (the dashboard is my visual aid for this).

**Assessment weight (100 points):** AI-agent system and design 25, human-AI comparison 25, business background 15, original findings and theory 15, presentation quality 10, time management 10. Build with that in mind: the design and the comparison are half the grade.

# 2. SOURCE MATERIAL: READ THIS FIRST

The `brief/` folder is the single source of truth. Read these files before writing any code, and summarise back to me in about 10 lines what you understood (study, design, measures, benchmarks, rules) so I can correct you before you build:

- `brief/Group-Project-Instruction.pdf` (or `.docx`): the five required tasks, deliverables, rubric and the "do not tune" rule.
- `brief/Group-1/Instruction.docx`: our study overview and the **instructor's starting prompt**.
- `brief/Group-1/high-saturation.png` and `low-saturation.png`: the two experimental stimuli.
- `brief/Group-1/original-paper.pdf`: Hagtvedt and Brasel (2017).
- `brief/Sensory marketing replication paper.pdf`: Motoki and Iseki (2022).
- `brief/Sensory marketing replication paper - supplementary materials.docx`: methodological appendix.

Tools: use `pdftotext`, `pandoc` or `python-docx` to read the PDFs and Word files. Look at both images.

**Then read the `reference/` folder** (earlier work by me and Claude on this same study; see "How to use" at the top). Treat it as follows:
- `reference/prompts/v1/*.txt` is the **signed-off v1 prompt text**. Use these files verbatim (see rule 11 in section 3). Do not rewrite the wording.
- `reference/PROMPT_NOTES_v1.md` explains each change from the instructor's prompt and why. Reuse it for `CHANGELOG.md` and `DEVIATIONS.md`.
- `reference/VARIABLE_DICTIONARY.md` defines the dataset columns. Keep these column names so the dataset matches what the team has already reviewed. Extend it only if you add a column, and record that in `CHANGELOG.md`.
- `reference/stimuli/` holds the already-renamed stimulus images and their hashes. Verify the hashes against `brief/Group-1/*.png`.
- The two notes files (requirements analysis, work summary) are the team's own reading of the brief. Use them as a **cross-check**: the brief is the source of truth. If the brief and these notes disagree, tell me before building.
- `reference/gp4_simulation.ipynb` is an earlier notebook, tested on mock data only (no live call was ever made). You may borrow ideas from it, but build the modular project in section 5. Do not assume it is correct: test anything you reuse.

In your Phase 0 summary, list any differences you find between the brief and the reference files.

# 3. NON-NEGOTIABLE EXPERIMENT RULES (from the brief and from earlier design review)

These are scientific-integrity rules. Build them into the code, not just the comments.

1. **Do not tune to match.** The brief says: "Do not change experimental settings simply to make AI results look more similar to human results." All settings (model, temperature, prompt version, persona, sample size, seed) are fixed in a config file BEFORE any live run. Any later change creates a new prompt or config version (`v2`), with a written reason in a change log. Never overwrite v1 results.
2. **Prompts must not reveal the hypothesis or the condition.** Never mention colour saturation, "vivid", "dull", "size effect" or what the study expects. The agent is told only that it is shown a laptop and asked questions.
3. **Image file names must not leak the condition.** Copy the two images into a `stimuli/` folder as neutral names (`stim_A.png` = high saturation, `stim_B.png` = low saturation). Keep the mapping in a separate `stimulus_key.json` (with SHA-256 hashes) that is NEVER sent to the model. The file path must never appear in the prompt text.
4. **One image, one fresh call per agent.** Each agent is an independent API call with no memory of any other agent and only ONE image. This reproduces the between-subjects design (each participant sees one condition).
5. **Send the real image to the model (multimodal input).** Do NOT use a "describe the image in words, then let a text agent answer" pattern. That replaces the stimulus with a verbal description and contaminates the experiment.
6. **Random assignment** to conditions with a seeded shuffle (reproducible), as close to equal groups as possible (for n = 77: 39 and 38).
7. **Preserve the original questions and scales exactly:** size 10 to 20 inches in whole numbers; attention two items on 1 to 7; arousal and mood on 1 to 9. Output must be a strict JSON object with those keys. Validate every answer in Python (integer, in range). Retry invalid or failed responses up to a configurable limit. Keep agents that still fail in the file with `valid = False` and exclude them from analysis, and report how many.
8. **Log everything for audit:** model name, temperature, prompt version and prompt hash, seed, image hash, token counts, timestamps, raw model output, number of attempts, and any error messages.
9. **Mock data must never be mistaken for results.** Provide a dry-run mode that makes no API calls and returns fake answers. Every dry-run row carries `dry_run = True`, the dashboard shows a red "MOCK DATA, NOT RESULTS" banner whenever mock rows are loaded, and mock files go to a separate folder.
10. **Report modifications transparently.** Keep a `DEVIATIONS.md` listing every difference from the original design (for example: small on-screen image instead of a large projected one, no snack incentive, gender and colour-blindness items omitted, an LLM has no real attention or arousal system).
11. **Use the signed-off v1 prompt text verbatim.** Copy `reference/prompts/v1/` into `prompts/v1/` unchanged. After copying, compute and record the hash of the exact text sent to the model, and show me the final assembled prompt (system plus user plus output block) for one agent before any live call. Any wording change means a new version folder (`v2`), a CHANGELOG entry with the reason, and my approval. Never edit v1 in place.
12. **Fix the settings in `config_v1.json` before the first live run.** The defaults below are PROPOSED and still need my sign-off (ask me to confirm them in Phase 2): model `gpt-4o-mini`, temperature 1.0, persona mode `student`, arousal maximum 9, equivalence-test bound plus or minus 0.5 inch. Run sizes: smoke 4 agents, main 77 (39 and 38), diagnostic 20 (with the extra `explanation` field), robustness 823 (replication scale, labelled as robustness in every table and chart).
13. **Persona (when `persona_mode = "student"`).** The system text gets the line " You are a {male / female} undergraduate university student." Gender is assigned by quota at 49% male (matching the original sample), using the seeded shuffle. With `persona_mode = "none"` the line is empty and `gender` is blank. Use the exact placeholder names in the v1 prompt files.
14. **Image handling.** Send the image as base64 inline, placed before the task text, one image per call. Declare the image-detail setting in the config and log it. The two laptops are the same pixel size, but the canvases differ slightly (311 by 213 and 315 by 216 pixels, white space only). Do not change the images silently: if you pad both to one canvas, do it as an explicit, logged option, off by default, and list it in `DEVIATIONS.md`.
15. **Temperature support.** Some OpenAI models do not accept a temperature setting. If the chosen model rejects it, send no temperature, leave the `temperature` column blank, and say so in the run log.

# 4. KNOWN ISSUES TO HANDLE (do not silently resolve these)

- **Arousal scale conflict.** The Group 1 overview text says arousal is a 7-point scale. The instructor's prompt and the original paper's affect grid use 9 points. Make the arousal maximum a single config value, default 9 (matching the instructor's prompt), and flag it in the README as an open question for Dr. Zhang.
- **The instructor's prompt says "the product's size"** without defining it. Our version says "the laptop's screen size", matching the original wording. Document this as a prompt change.
- **Instructor prompt format** is a Python dictionary with keys `"screen size"`, `"attention getting"`, `"capture attention"`, `"arousal"`, `"mood"`. We use JSON with snake_case keys (`screen_size`, `attention_getting`, ...) so a JSON schema can enforce ranges. Document the mapping.
- **No raw human data** is provided for Group 1, only summary statistics (means, SDs, F, r). So the human-AI comparison is at summary level. Per-cell n is not reported; for the original use the total n = 77 split roughly 39 and 38, and say so.
- **Model choice and framework.** The instructor's S4 demo used CrewAI. Build the LLM call behind a small `llm_client.py` interface so the provider can be swapped. Default: the direct OpenAI API (`gpt-4o-mini`, temperature 1.0, as config values). Ask me before changing these. Do NOT install CrewAI unless I tell you to.
- **Training-data risk.** The finding is well known, so a model might recall it. Include an optional diagnostic run (about 20 agents) with an extra `explanation` field, used only to explain results, never to choose settings.

# 5. TARGET PROJECT STRUCTURE

Create this layout in the current folder. Keep the module names. Do not collapse everything into one big file.

```
gp4-sensory-marketing/
├── README.md                  Plain-English guide: purpose, setup, how to run each step, how to deploy
├── DEVIATIONS.md              Every difference from the original experiment, with reasons
├── CHANGELOG.md               Prompt/config versions and why each changed (v1, v2, ...)
├── requirements.txt           Pinned versions (openai, pandas, numpy, scipy, statsmodels, matplotlib, plotly, streamlit, python-dotenv, pytest)
├── .gitignore                 Must exclude .env, secrets, __pycache__, venv, data/mock/, brief/ AND reference/
├── .env.example               Shows OPENAI_API_KEY=your-key-here (NO real key ever)
├── brief/                     Course materials (read-only; do not edit; NEVER committed: it holds copyrighted papers and instructor files)
├── reference/                 My earlier GP4 work (read-only; not committed). See section 2.
├── config/
│   └── config_v1.json         All experiment settings: model, temperature, n, seed, persona mode, arousal_max, retries, image_detail, tost_bound
├── prompts/
│   └── v1/                    system.txt, user.txt, output_main.txt, output_diagnostic.txt (copied VERBATIM from reference/prompts/v1/; plain text with {placeholders})
├── stimuli/                   (committed: needed to reproduce the experiment)
│   ├── stim_A.png             (byte-identical copy of high-saturation.png, neutral name)
│   ├── stim_B.png             (byte-identical copy of low-saturation.png, neutral name)
│   └── stimulus_key.json      Hashes and mapping; never sent to the model
├── src/gp4/
│   ├── __init__.py
│   ├── config.py              Load and validate config; compute the prompt hash
│   ├── benchmarks.py          Human benchmark numbers (original and replication) as clearly labelled constants with source citations
│   ├── prompts.py             Build system/user text from prompt files and persona; no logic hidden here
│   ├── agents.py              Create the agent roster: IDs, seeded condition assignment, persona (gender quota) if enabled
│   ├── llm_client.py          Wrapper: real OpenAI multimodal call with JSON-schema output, and a MockClient for dry runs
│   ├── validate.py            Range/type checks, JSON repair for code-fenced output, retry decisions
│   ├── run_experiment.py      Runs the agents, logs each response to JSONL as it arrives, writes the tidy CSV and a config snapshot
│   ├── analysis.py            Descriptives, ANOVAs, effect sizes (r, Cohen's d, partial eta-squared with CIs), Fisher-z comparison to humans, TOST equivalence, mood placebo, optional mediation
│   └── plots.py               All figures (return Plotly and Matplotlib versions so the dashboard and the report can both use them)
├── app/
│   └── streamlit_app.py       The dashboard (reads saved CSVs; never calls the API unless I explicitly enable a "Run" page)
├── scripts/
│   ├── run_dry.py             Dry run with mock data
│   ├── run_live.py            CLI: --run-label smoke|main|diagnostic|robustness; asks for confirmation before spending money
│   └── analyze.py             Re-run the analysis on any saved CSV and write tables and figures
├── data/
│   ├── real/                  Live results only (committed to GitHub: this is deliverable B)
│   ├── mock/                  Dry-run output (git-ignored)
│   └── VARIABLE_DICTIONARY.md Every column, type and meaning (deliverable B)
├── reports/figures/           Saved PNGs for the 2-page report and slides
└── tests/
    ├── test_validate.py
    ├── test_analysis.py       Checks the r and effect-size maths against the published values
    └── test_assignment.py     Seeded assignment gives 39/38 and is reproducible
```

# 6. CODING STANDARDS (because I am a beginner)

- **Comment heavily, in plain English.** Every file starts with a docstring block: what this file does, where it fits in the pipeline, and what goes in and out. Every function has a docstring with inputs, outputs, and a one-line "why this exists". Add inline comments that explain the reason for non-obvious lines, not just what the line does.
- **Number the pipeline steps** in comments (`# STEP 1 of 5: Load config`) so I can follow the flow of `run_experiment.py` and `analysis.py` from top to bottom.
- **Mark every place I might want to change** with a `# CONFIG:` or `# EDIT HERE:` comment, and keep those values in `config_v1.json`, not buried in code.
- **Keep functions short** (one job each) and use clear names. Use type hints. No clever one-liners.
- **No hard-coded secrets, no hard-coded absolute paths.** Use `pathlib` and paths relative to the project root. The API key comes only from the `OPENAI_API_KEY` environment variable (loaded from `.env` locally, or from Streamlit secrets when deployed).
- **Fail loudly and helpfully.** If the key is missing, a file is missing or a config value is out of range, raise an error that says what is wrong and exactly how to fix it.
- **Add a short "Glossary" section to the README** defining: agent, prompt, temperature, token, JSON schema, between-subjects, ANOVA, effect size (r), TOST, Fisher-z, dry run, virtual environment, repository, commit, push.
- **Statistics must be checked, not assumed.** In `test_analysis.py`, verify that converting the published F values to r reproduces r = .295, .249 and .299 (original) and that the replication F values give r of about .011 (size), .238 (attention) and .180 (arousal). Run the tests and show me the output.

# 7. PHASES (STOP AFTER EACH ONE AND WAIT FOR MY "GO")

**Phase 0: Understand and confirm.** Read the brief and then the `reference/` folder (section 2). Give me the ~10-line summary and list anything ambiguous, including any difference between the brief and the reference files. Also look at the two images and tell me what you see (laptop colour, whether size is identical, any file-name leaks). Stop.

**Phase 1: Environment, one step at a time.** Walk me through creating the folder structure, a Python virtual environment, installing `requirements.txt`, and creating `.env` from `.env.example` (I paste my key myself; you never see or print it). Confirm Python version and that imports work. Stop.

**Phase 2: Foundation modules.** Build `config.py`, `benchmarks.py`, `prompts.py`, `agents.py`, `validate.py`, and `config_v1.json`. Copy the v1 prompt files and the stimuli in verbatim, verify the stimulus hashes against `brief/Group-1/`, and show me the assembled prompt for one agent plus its hash. Ask me to confirm the proposed settings in rule 12 before they are fixed. Write the three tests. Run `pytest` and show me the output. Stop.

**Phase 3: Experiment engine and dry run.** Build `llm_client.py` (with MockClient), `run_experiment.py`, and `scripts/run_dry.py`. Run a dry run with mock data. Prove the edge cases work: every agent giving the same answer, out-of-range answers triggering retries, code-fenced JSON, a simulated API failure. Show me the CSV head and the log. Stop.

**Phase 4: Analysis and figures.** Build `analysis.py` and `plots.py`. Run them on the mock data to prove they execute end to end. Cover: descriptives by condition; one-way ANOVA for size, attention and arousal; mood as a placebo check; effect sizes with confidence intervals; Fisher-z tests comparing the AI effect to the original and to the replication; a TOST equivalence test for the size effect (bound from config); a simple outcome classifier that labels the result as one of: A (full original pattern), B (replication pattern: attention and arousal up, no size effect), C (blind to saturation: no effects), D (exaggerated or halo effect, for example mood also differs). Mediation follows the original's own rule: run it ONLY if the AI size effect appears (bootstrap, same structure as the original's model), and otherwise state that it was skipped and why. Add optional, clearly labelled extras only if I ask: a second model, or a both-images check (that one is a design change, not a replication). Handle zero-variance data gracefully (no crash, no fake confidence interval). Stop.

**Phase 5: Streamlit dashboard.** See section 8. Build it, run it locally, and show me how to open it. It must work fully on mock data and on real data. Stop.

**Phase 6: First live smoke test (only with my approval).** Before any live call, tell me the model, the number of calls (4), and the approximate cost, and ask me to confirm. Run `--run-label smoke`. Check: the JSON schema is accepted, parse rate is 100%, answers look sensible. If the schema is rejected, fix the code, not the prompt wording, and tell me. Stop. (I will run the main 77-agent run myself at the right time, using the script and the confirmation prompt.)

**Phase 7: GitHub, one step at a time.** Only after I say go. Walk me through: `git init`, reviewing `.gitignore`, a check that no `.env` or key is staged (show me `git status`), the first commit, creating a **private** repository on GitHub, adding the remote, and pushing. Ask for my explicit approval before the commit and again before the push. Suggest a repository name. Never commit mock data or any secret. If I want to deploy to Streamlit Community Cloud afterwards, walk me through that separately, including how to enter the API key as a Streamlit secret (not in the repo).

# 8. STREAMLIT DASHBOARD SPEC

A multi-page (or tabbed) app in `app/streamlit_app.py`, organised to follow the 12-minute presentation structure and the grading rubric. Use `st.cache_data` for loading data. Use a sidebar to pick the data file (real or mock) and show a clear banner if mock. Every chart needs a title, labelled axes, units, and a one-line plain-English "what this shows" caption. Make colours consistent across pages (one colour for high saturation, one for low, one for each benchmark source). Do not rely on colour alone to carry meaning.

1. **Overview:** the research question, the one-paragraph marketing context, and the headline answer (which outcome, A to D) with the key numbers.
2. **Original study:** the design (two conditions, measures, scales), the two stimulus images side by side with neutral labels shown as "Condition: high/low" only on this page, and the human benchmark table (original vs replication).
3. **AI-agent system:** how agents are generated and initialised, the exact prompt text (with the version and hash), model and settings, how the image is passed, how answers are validated, and the list of deviations from the original.
4. **Results:** for each measure (size, attention, arousal, mood): the distribution by condition (box plus individual points), mean and SD table, ANOVA result, effect size with confidence interval. Include a data-quality panel: number of agents, valid rate, retries, any zero-variance warning.
5. **Human vs AI comparison (the most important page):** a forest plot of effect size r with 95% CI for original, replication and AI on each measure; a table of Fisher-z comparisons; the TOST result for size; a plain-English reading ("same direction?", "similar magnitude?", "statistical evidence?"). State clearly that a similar average does not by itself mean the human effect was reproduced.
6. **Explore data:** filterable table of agent rows, a download button for the CSV, and the variable dictionary.
7. **Limitations and cautions:** an LLM has no real attention or arousal system; training-data recall; online vs lab setting; single model; small image vs projected image; what researchers should be careful about when using AI agents as substitutes for human participants.

**Optional page 8 (hidden by default behind a config flag):** "Run experiment", which lets me start a smoke or main run from the dashboard with a confirmation checkbox and a cost warning. Default OFF so a deployed public app can never spend money.

# 9. WHAT "DONE" LOOKS LIKE

- `pytest` passes and I have seen the output.
- A dry run completes end to end, and the dashboard renders every page on mock data with the MOCK banner visible.
- A live 4-agent smoke run completes with a 100% parse rate (only after I approve it).
- `README.md` lets someone who has never seen the project install it, run it and reproduce the analysis.
- `DEVIATIONS.md`, `CHANGELOG.md` and `data/VARIABLE_DICTIONARY.md` are complete.
- The repository is on GitHub (private), contains no secrets, and I have seen `git status` before every commit.
- `brief/`, `reference/`, `.env` and mock data are NOT in the repository (check with `git ls-files`).
- The prompt text actually sent to the model is identical to `reference/prompts/v1/` (hash recorded in every data row).

# START NOW

Begin with Phase 0. Read the brief, give me the ~10-line summary and the list of ambiguities, describe the two images, and then stop and wait for my "go".

=== END OF PROMPT ===
