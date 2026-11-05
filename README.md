# GP4: Can AI agents reproduce a sensory marketing effect?

MBAN 5640 Visualization and Data Mining, Sobey School of Business, Saint Mary's University. Group Project 4, Group 1 (Soni, Toner, Warner).

We simulate **Hagtvedt and Brasel (2017), Study 3**, "Color Saturation Increases Perceived Product Size", with AI agents. Each agent is one independent call to a vision-language model that sees **one** image of a red laptop, high or low in colour saturation, and answers the original questions: the laptop's screen size (10 to 20 inches), two attention items (1 to 7), and arousal and mood (1 to 9). We then compare the AI effects with two human benchmarks that disagree: the original study (n = 77; size, attention and arousal effects) and the Motoki and Iseki (2022) replication (n = 823; attention and arousal, but **no** size effect).

**Status:** code complete and tested on mock data. Live runs are made with `scripts/run_live.py` after the 4-agent smoke test. Check `data/real/` for live results.

---

## Quick start (Windows, PowerShell)

You need Python 3.13 and, for live runs only, an OpenAI API key.

```powershell
# 1. Get the code and open the folder
git clone <repository-url> mban5640-GP4
cd mban5640-GP4

# 2. Create and activate a virtual environment (a private Python for this project)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # the prompt now starts with (.venv)

# 3. Install the exact package versions
python -m pip install -r requirements.txt

# 4. Check everything works (about 15 seconds)
python -m pytest                      # expect: all tests passed

# 5. Try the whole pipeline on fake data (no API calls, no cost)
python scripts/run_dry.py --scenario fake_effect
python scripts/analyze.py --latest mock

# 6. Open the dashboard
streamlit run app/streamlit_app.py    # then open http://localhost:8501
```

macOS or Linux: activate with `source .venv/bin/activate`.

**For live runs only:** copy `.env.example` to `.env` and put your key after `OPENAI_API_KEY=`. Never commit `.env` (Git ignores it).

---

## How to run each step

| Step | Command | What you get |
|---|---|---|
| See the exact prompt an agent receives | `python scripts/show_prompt.py --agent 5` | System text, where the image goes, task text, and the prompt hash. No API call. |
| Dry run (fake answers) | `python scripts/run_dry.py` | 77 mock agents in `data/mock/`. Options: `--scenario normal, fake_effect, identical, out_of_range, code_fenced, api_failure, always_fail, mixed`; `--run-label diagnostic`; `--n 12`. |
| Live run (spends money) | `python scripts/run_live.py --run-label smoke` | Shows the model, number of calls and estimated cost, and asks you to confirm. Labels: `smoke` (4), `main` (77), `diagnostic` (20), `robustness` (823). Output in `data/real/`. |
| Analyse a run | `python scripts/analyze.py data/real/gp4_main_<run_id>.csv` or `--latest real` | Tables, `summary.md` and 6 figures. Real runs: figures in `reports/figures/`, comparison table in `data/real/`. Mock runs: everything stays in `data/mock/`. |
| Dashboard | `streamlit run app/streamlit_app.py` | Seven pages that follow the presentation. Pick the data file in the sidebar. A red banner marks mock data. |
| Tests | `python -m pytest` | Checks the statistics against the published values and against scipy/statsmodels, plus the prompts, assignment, engine, figures and dashboard. |

---

## How it works

```
config/config_v1.json ──► agents.py (roster: 39 high / 38 low, seeded; 49% male persona)
prompts/v1/*.txt ───────► prompts.py (exact text, hygiene check, hash)
stimuli/stim_A|B.png ───► llm_client.py (one call: system text + ONE image + task text; JSON schema)
                          validate.py (whole numbers in range; retry up to 3 tries)
                          run_experiment.py ──► data/real|mock/gp4_<label>_<run_id>.csv, _raw.jsonl, _config.json, _run.log
                          analysis.py + plots.py ──► tables, figures, dashboard
```

| Folder or file | Contents |
|---|---|
| `config/config_v1.json` | Every experimental setting, signed off before any live run |
| `prompts/v1/` | The signed-off prompt text, byte-identical to the team's reviewed version |
| `stimuli/` | `stim_A.png` (high), `stim_B.png` (low), byte-identical to the instructor's files; `stimulus_key.json` (never sent to the model) |
| `src/gp4/` | The pipeline, one job per module (each file starts with an explanation) |
| `scripts/` | Command-line entry points listed above |
| `app/streamlit_app.py` | The dashboard |
| `data/real/` | Live results: **the AI-generated dataset (deliverable B)** |
| `data/VARIABLE_DICTIONARY.md` | Every column and the data-collection procedure (deliverable B) |
| `reports/figures/` | Figures from live data for the report and slides |
| `DEVIATIONS.md` | Every difference from the original experiment, with reasons |
| `CHANGELOG.md` | Versions of prompt and settings, and why each changed |
| `tests/` | Automated checks |

---

## Reproducibility and integrity

- **Settings fixed before results.** `config_v1.json` was signed off on 2026-11-05. Live runs refuse to start until it is signed off. Any later change becomes `config_v2.json` with a reason in `CHANGELOG.md`. We do not change settings to make AI results look more human (course brief).
- **Prompt cannot drift.** The fingerprints of the four v1 prompt files are stored in the config; the code refuses to run if any word changes. Every data row records `prompt_sha`, the hash of the exact text that agent received.
- **No condition leaks.** The prompt never mentions colour, saturation, the conditions, the hypothesis or the paper, and the image is sent without its file name. Both are checked in code.
- **Same inputs, same outputs.** Assignment and the mediation bootstrap are seeded. Mock data are seeded too. Model answers are random by design (temperature 1.0), so a live rerun gives a new sample; the saved CSV is the record.
- **Everything is logged.** Every attempt's raw output, tokens, timestamps and errors are in `*_raw.jsonl`; settings, prompt text and library versions in `*_config.json`.
- **Mock data are never results.** Dry runs are marked `dry_run = True`, saved in `data/mock/` (not uploaded), and flagged in red on the dashboard and in every figure title.
- **Exact package versions:** `requirements.txt` (direct) and `requirements-lock.txt` (everything).

---

## Open questions for Dr. Zhang

1. **Arousal scale.** The Group 1 overview says 7-point (as in the replication); the instructor's prompt and the original paper use the 9-point affect grid. We use 9 (`arousal_max` in the config; the prompt text matches). The replication's arousal means are therefore compared on effect size only.
2. **Framework.** The S4 demo used CrewAI. We call the OpenAI API directly (behind a swappable `llm_client.py`) so the model sees the real image. Is that acceptable?
3. **Raw human data.** None was provided for Group 1, so the comparison uses published summary statistics. Is raw data available?
4. **Robustness run.** May we report an 823-agent run at the replication's sample size, clearly labelled as robustness?

---

## Deploying the dashboard (Streamlit Community Cloud)

The dashboard only reads saved CSVs and never calls the API (the "Run experiment" page is off: `enable_run_page = false`), so a deployed copy cannot spend money.

1. Push the repository to GitHub (private). `brief/`, `reference/`, `.env` and `data/mock/` are excluded by `.gitignore`.
2. At share.streamlit.io, sign in with GitHub, choose **New app**, pick the repository, branch `main`, and main file `app/streamlit_app.py`. Choose Python 3.13 under advanced settings.
3. No API key is needed for the dashboard. If one is ever needed, enter it under the app's **Settings > Secrets** as `OPENAI_API_KEY = "..."`, never in a file in the repository.

---

## Glossary

| Term | Meaning |
|---|---|
| **Agent** | One simulated participant: a single, independent call to the AI model, with no memory of other agents. |
| **Prompt** | The text instructions sent to the model (here: a short system text plus the task text with the questions). |
| **Temperature** | A model setting for randomness. 0 gives nearly the same answer every time; 1.0 (our setting) lets answers vary as people's do. |
| **Token** | The unit models read and write, roughly three quarters of a word. Cost is charged per token. Images also count as tokens. |
| **JSON schema** | A formal description of the answer's shape (which keys, which values are allowed). We use it so the model can only answer, for example, a whole number from 10 to 20. |
| **Between-subjects** | Each participant sees only one condition. Here, each agent sees only one image. |
| **ANOVA** | Analysis of variance: a test of whether group means differ more than chance would explain. With two groups, its F equals t squared. |
| **Effect size (r)** | How strong the difference between conditions is, from 0 (none) to 1. Computed as r = sqrt(F / (F + df)). Lets studies of different sizes be compared. |
| **TOST** | Two one-sided tests: an equivalence test. It asks whether a difference is small enough (here, within plus or minus 0.5 inch) to call it zero, which "not significant" alone cannot show. |
| **Fisher-z** | A transformation of r that makes it roughly normal, used for confidence intervals and to test whether two r values (AI vs human) differ. |
| **Dry run** | A run with fake (mock) answers and no API calls, to test the code without cost. |
| **Virtual environment** | A private folder (`.venv`) holding this project's Python and packages, separate from other projects. |
| **Repository** | The project folder tracked by Git, and its copy on GitHub. |
| **Commit** | A saved snapshot of the project's files in Git, with a message saying what changed. |
| **Push** | Uploading your commits from your computer to GitHub. |

---

## Sources

- Hagtvedt, H., and Brasel, S. A. (2017). Color saturation increases perceived product size. *Journal of Consumer Research*, 44(2), 396-413.
- Motoki, K., and Iseki, S. (2022). Evaluating replicability of ten influential research on sensory marketing. *Frontiers in Communication*, 7, 1048896.

---
*Built with AI assistance from Claude (Anthropic): code, tests and documentation were drafted with Claude and reviewed by the team.*
