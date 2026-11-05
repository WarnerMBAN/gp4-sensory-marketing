# CHANGELOG

Every prompt and configuration version, and why it changed. The course brief says: "Do not change experimental settings simply to make AI results look more similar to human results." So settings are fixed before any live run, and any later change becomes a new version (v2, v3, ...) with a reason recorded here. Earlier versions and their results are never edited or overwritten.

## v1: config_v1.json and prompts/v1 (signed off 2026-11-05 by Dale Warner)

**Status:** fixed. No live run has been made yet.

### Prompt v1

- Copied byte for byte from the team's signed-off `reference/prompts/v1/` (files `system.txt`, `user.txt`, `output_main.txt`, `output_diagnostic.txt`). Checked identical with a byte comparison on 2026-11-05.
- Changes from the instructor's prompt (`brief/Group-1/Instruction.docx`) and the reasons are listed in `reference/PROMPT_NOTES_v1.md`. In short:
  1. "the product" and "the product's size" became "a laptop computer" and "the laptop's screen size", restoring the original study's wording (Hagtvedt and Brasel 2017, p. 400). "Product size" was undefined.
  2. Attention items say "The laptop is ..." (original item wording).
  3. The 9 x 9 affect grid is presented as two 9-point scales (arousal, mood) with the original anchors, because a grid cannot be drawn in text.
  4. The output is JSON with snake_case keys instead of a Python dictionary with spaced keys. Mapping: "screen size" to `screen_size`, "attention getting" to `attention_getting`, "capture attention" to `capture_attention`, "arousal" to `arousal`, "mood" to `mood`. Same five answers; a JSON schema can enforce the ranges.
  5. Ranges are stated in the text and also enforced by a JSON schema and re-checked in Python.
  6. An optional minimal persona: " You are a {male / female} undergraduate university student."
  7. Nothing about colour, saturation, conditions, the hypothesis or the paper. Enforced in code (`prompts.check_hygiene`).
- **Text handling (format only, no wording change):** when the files are read, Windows line endings (CRLF) become plain line breaks (LF) and the final end-of-file newline is removed. The prompt hash is computed on this exact text, so it tracks the wording, not the file format. The fingerprints of the four files are stored in `config_v1.json` (`prompt_file_sha256`); the code refuses to run if a file changes.
- **Prompt hash on each data row (`prompt_sha`):** first 12 characters of the SHA-256 of the exact system and user text for that agent. There are five v1 variants:

  | Persona | Run type | prompt_sha |
  |---|---|---|
  | student, male | main | d5a6a020a5c5 |
  | student, female | main | c65fb54da733 |
  | student, male | diagnostic | 339c649a4799 |
  | student, female | diagnostic | ab9cdc6257d4 |
  | none | main | a07759c67ecc |

### Config v1 settings (approved 2026-11-05)

| Setting | Value | Reason |
|---|---|---|
| model | gpt-4o-mini | Vision-capable, low cost, used in the course S4 demo. Availability on our key to be confirmed by the smoke run. |
| temperature | 1.0 | Default sampling, so agents vary as participants do. Sent only if the model accepts it. |
| image_detail | low | The stimuli (about 311 x 213 px) are smaller than the 512 x 512 low-detail size, so no detail should be lost; a fixed value is more reproducible than "auto". Changed from the earlier notebook's "auto" before any live run. |
| pad_images_to_common_canvas | false | Images sent unchanged. |
| persona_mode, pct_male | student, 0.49 | Original sample: undergraduates, 49% male. Quota applied within each condition (n = 77: 19 of 39 high, 19 of 38 low) so gender cannot be confounded with condition. |
| arousal_max | 9 | Original affect grid and instructor's prompt. Open question for Dr. Zhang (the overview text, copied from the replication, says 7). |
| seed | 20261114 | Reproducible assignment. Chosen before any run. |
| run sizes | smoke 4, main 77, diagnostic 20, robustness 823 | Main matches the original n; robustness matches the replication n. |
| max_attempts, workers | 3, 4 | Up to 3 tries per agent; 4 independent calls at a time. |
| tost_bound_inches | 0.5 | Equivalence bound for the size effect, about 60% of the original 0.87-inch difference. |
| alpha | 0.05 | Conventional significance level. |

### Dataset columns

Column names follow `reference/data/VARIABLE_DICTIONARY.md` unchanged. Any added column will be listed here.

- 2026-11-05: `data/VARIABLE_DICTIONARY.md` copied from the reviewed reference version. Column names and order unchanged. Text updated only to name the new scripts, the `*_run.log` file, the `attempt_log` in the JSONL, `model = MOCK` and blank temperature in dry runs, blank ratings when `valid` is False, and the stop-on-fatal-error rule.

### Engine behaviour fixed during Phase 3 testing (before any live run)

- A fatal API error (for example an invalid key) now stops every agent before its next call, through a shared stop signal. Found by an automated test: previously, queued agents kept calling after the error. Agents that had already finished are still saved.

### Live runs under v1

| Date (local) | Run | Agents | Valid | Retries | Tokens (in / out) | Cost (USD) | Notes |
|---|---|---|---|---|---|---|---|
| 2026-11-05 19:02 | smoke `gp4_smoke_20261105_190229` | 4 (2 high, 2 low) | 4 (100%) | 0 | 13,260 / 176 | about 0.002 | First live call, approved by Dale. JSON schema accepted; temperature 1.0 accepted; raw outputs clean JSON. Pipeline check only, not a result. |
| 2026-11-05 19:10 | **main** `gp4_main_20261105_191049` | 77 (39 high, 38 low) | 77 (100%) | 0 | 255,255 / 3,388 | about 0.040 | Run by Dale. The run to report. A first attempt at 19:10 was cancelled at the confirmation prompt (no calls, no files). Analysis: outcome D (size effect larger than the original's; mood differs). 86% of agents share an answer pattern with another agent. |
| 2026-11-05 19:17 | main (REPEAT) `gp4_main_20261105_191715` | 77 (39 high, 38 low) | 77 (100%) | 0 | 255,255 / 3,388 | about 0.040 | Started by Dale after believing an earlier run had been interrupted (it had not reached any call); confirmed with "main again". NOT the primary result: by the rule fixed before any results, the first main run (19:10) is reported. Kept and shown as a stability check: size r = +.63, attention r = +.16 (n.s.), arousal r = +.31, mood r = +.19 (p = .101, n.s.); outcome D (size larger than the original's). |
| 2026-11-05 19:23 | diagnostic `gp4_diagnostic_20261105_192353` | 20 (10 high, 10 low) | 20 (100%) | 0 | 66,800 / 1,749 | about 0.011 | Run by Dale. Explanation field, used only to interpret results (never to choose settings). Mean size 15.0 (high) vs 13.1 (low), the same pattern as main. Word counts: high explanations all say "red" (10/10); low explanations say "vibrant" (9/10) and "pink" only 2/10; no explanation mentions size, screen or inches. |

### Other changes (no effect on the experiment)

- 2026-11-05: `config/pricing.json` added for cost estimates only (gpt-4o-mini: $0.15 / $0.60 per million input / output tokens; 2,833 tokens per low-detail image), from the OpenAI model page and vision guide. Measured input tokens in the smoke run (3,315 per call) were within 1% of the estimate (3,292).
- 2026-11-05: OpenAI lists gpt-4o-mini as **Deprecated** (no shutdown date). The smoke run shows it still works. v1 keeps it; if it stops working before the main run, a v2 config with a new model and a reason will be needed, and v1 results (if any) kept.
- 2026-11-05: dashboard opens on a main run by default and marks smoke files "a pipeline check, not a result".

---
*Prepared with AI assistance from Claude (Anthropic).*
