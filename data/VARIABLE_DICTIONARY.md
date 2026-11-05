# GP4 Group 1: AI-agent dataset, variables and collection procedure

*Drafted 2026-11-01 with Claude (Anthropic); updated 2026-11-05 for the modular project. Applies to files `gp4_<run_label>_<run_id>.csv` written by `src/gp4/run_experiment.py` (via `scripts/run_live.py`, or `scripts/run_dry.py` for mock data). Column names are unchanged from the version the team reviewed.*

## Collection procedure

1. Each row is one AI agent acting as one participant in Hagtvedt & Brasel (2017), Study 3.
2. Agents are assigned to the high- or low-saturation condition by a seeded shuffle (39 / 38 for n = 77). With the student persona, gender is assigned by quota (49% male).
3. Each agent gets **one fresh API call** with no memory of other agents. The call contains the instructions (system text), **one** stimulus image (base64, neutral file name), and the task text with the original questions and scales (`prompts/<version>/`).
4. Answers are constrained by a JSON schema and re-validated in Python. An invalid or failed answer is retried up to `max_attempts` times. Agents still invalid after that are kept in the file with `valid = False` and excluded from analysis.
5. Every agent's full record, including every attempt, is appended to `*_raw.jsonl` as soon as that agent finishes. The tidy `.csv`, the run settings (`*_config.json`, including the exact prompt text of every variant) and a readable log (`*_run.log`) are written at the end of the run. Existing files are never overwritten.
6. Rows with `dry_run = True` are mock data used only to test the code and must never be analysed as results. They are saved in `data/mock/` (not uploaded to GitHub); live results are saved in `data/real/`.
7. If a fatal error occurs (for example an invalid API key), the run stops at once: agents that finished are saved, the rest make no calls, and the log says ABORTED.

## Variables

| Variable | Type | Meaning |
|---|---|---|
| `agent_id` | text | Agent identifier; prefix S = smoke, M = main, R = robustness, D = diagnostic |
| `run_label` | text | `smoke`, `main`, `robustness` or `diagnostic` |
| `run_id` | text | Run start time, local, `YYYYMMDD_HHMMSS` |
| `dry_run` | bool | True = mock answers (no API call) |
| `condition` | text | `high` or `low` colour saturation (independent variable) |
| `stim_file` | text | Neutral stimulus file shown (`stim_A.png` = high, `stim_B.png` = low) |
| `stim_sha256` | text | Hash of the image bytes actually sent; matches the instructor's original files (it would differ only if the off-by-default padding option were switched on) |
| `persona_mode` | text | `student` or `none` |
| `gender` | text | Persona gender (`male` / `female`), empty if no persona |
| `model` | text | OpenAI model used; `MOCK` in dry runs |
| `temperature` | number | Temperature sent; empty when the model does not accept one, and in dry runs |
| `image_detail` | text | Image detail setting sent to the API |
| `prompt_version` | text | Prompt folder used (e.g. `v1`) |
| `prompt_sha` | text | First 12 characters of the SHA-256 of the exact system and task text sent (v1 values listed in CHANGELOG.md; the full text of each variant is in `*_config.json`) |
| `seed` | integer | Random seed for assignment |
| `screen_size` | integer 10-20 | Estimated laptop screen size, inches (DV 1). All rating columns are blank when `valid` is False |
| `attention_getting` | integer 1-7 | "The laptop is attention-getting." 1 = Not at all, 7 = Definitely |
| `capture_attention` | integer 1-7 | "The laptop captures my attention." Same scale |
| `attention` | number 1-7 | Mean of the two attention items (DV 2), as in the original |
| `arousal` | integer 1-9 | Affect grid arousal, 1 = low, 9 = high (DV 3) |
| `mood` | integer 1-9 | Affect grid mood, 1 = displeasure, 9 = pleasure (placebo; humans showed no difference) |
| `explanation` | text | Diagnostic runs only: the agent's short account of its answers, written after the answers |
| `valid` | bool | True if all five answers parsed and were within range |
| `attempts` | integer | Number of calls needed (1 = first try) |
| `errors` | text | Reasons for any failed attempts, e.g. `attempt 1: screen_size=27 is outside 10-20` |
| `raw_output` | text | Exact text returned by the model on the final attempt |
| `response_id` | text | OpenAI response ID, for audit |
| `input_tokens`, `output_tokens` | integer | Token usage for the final attempt |
| `called_at` | text | UTC time of the final attempt |

## Companion files

| File | Content |
|---|---|
| `*_raw.jsonl` | One JSON record per agent (the CSV row plus `attempt_log`: every attempt's raw output, problems, tokens and time), written as each agent finishes |
| `*_run.log` | Readable log: start, roster, prompt variants, retries, warnings, summary |
| `*_config.json` | All run settings, image hashes sent, the exact text of each prompt variant, library versions |
| `*_comparison.csv` | Live runs: r with 95% CI for original, replication and AI per measure, with Fisher-z tests of AI vs each human study (written by `scripts/analyze.py`) |
| `*_analysis/` | Every analysis table (`descriptives.csv`, `anova.csv`, `comparison.csv`, `plain_reading.csv`), `details.json` (data quality, TOST, mood placebo, outcome label, mediation) and `summary.md` |
| `reports/figures/*_fig1_size_distribution.png` | AI screen-size answers by condition (box plus every agent), with original and replication human means |
| `reports/figures/*_fig2_effect_sizes.png` | Forest plot: effect size r with 95% CI for each measure, original vs replication vs AI |
| `reports/figures/*_fig3_size_histogram.png` | Share of agents choosing each screen size, by condition |
| `reports/figures/*_fig4..6_*_distribution.png` | Same as fig1 for attention, arousal and mood |

For mock (dry-run) data, all analysis tables and figures stay in `data/mock/<stem>_analysis/` and every figure title begins "MOCK DATA, NOT RESULTS".
