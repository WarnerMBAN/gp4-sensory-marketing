# Deviations from the original experiment

Hagtvedt and Brasel (2017), Study 3, compared with our AI-agent simulation (config v1, prompt v1). The course brief asks us to "distinguish between the original design and any modifications". Each row says what differs, why, and what it might do to the results. None of these choices was made after seeing AI results.

## Participants

| # | Original | Our simulation | Why | Possible effect |
|---|---|---|---|---|
| 1 | 77 undergraduates (80 recruited, 49% male) | 77 independent calls to one vision-language model (gpt-4o-mini) | The task of the project | An LLM has no visual attention system, no physiological arousal and no mood. Any "effect" comes from learned associations between images and words, not from the mechanism the paper proposes. |
| 2 | Real people differ in many ways | Variation comes only from sampling randomness (temperature 1.0) and a one-sentence persona | Keeps the persona to what the original recorded (student status, gender) without inventing traits | Agents may vary less than people; answers may bunch on a few values (checked by the duplicate-answer and zero-variance warnings). |
| 3 | Gender asked at the end of the questionnaire | Gender given in the persona ("You are a male / female undergraduate university student."), 49% male, balanced within each condition | Reproduces the sample's composition; the original found gender was not a significant covariate | Gender is an instruction, not a measured trait. |
| 4 | Colour-blindness asked (one participant reported it) | Not asked | Not meaningful for a model | None expected. |
| 5 | Undergraduates (original); Japanese online adults (replication) | Student persona matches the original only | The original is the study being simulated | The replication sample is not mirrored; compare with it on effect sizes only. |

## Setting and stimulus

| # | Original | Our simulation | Why | Possible effect |
|---|---|---|---|---|
| 6 | Group session; image projected on a large screen | One image sent to the model as a small file (311 x 213 or 315 x 216 pixels), image detail "low" | The image the instructor supplied; there is no "projection" for a model | Size cues from a large projection are lost; the model sees the same small image whatever it is asked. |
| 7 | Paper questionnaire | The same questions as text, one message | Only practical form | Minor. |
| 8 | About $1 of snacks as payment | No incentive | Not meaningful for a model | None expected. |
| 9 | File names did not matter | Images renamed `stim_A.png` (high) and `stim_B.png` (low); the name is never sent | The supplied names (`high-saturation.png`) would reveal the condition | None: pixels are byte-identical (hash-checked). |
| 10 | Two image canvases | Sent unchanged (the canvases differ by a few pixels of white space; the laptop is the same size). Padding to one canvas is available but off | Avoid altering the stimulus | None expected; recorded so a reader can check. |

## Questions and answers

| # | Original | Our simulation | Why | Possible effect |
|---|---|---|---|---|
| 11 | Affect grid: one 9 x 9 grid giving arousal and mood together | Two separate 9-point scales with the same anchors (arousal: low to high; mood: displeasure to pleasure) | A grid cannot be drawn in text | The two ratings may be less linked than on a grid. |
| 12 | Arousal 9-point (original) | 9-point. The replication used 7-point (1 = Very calm, 7 = Very aroused); the Group 1 overview text says 7 | Follows the original paper and the instructor's prompt; open question for Dr. Zhang | Replication arousal means cannot be compared with ours directly; we compare effect sizes only. |
| 13 | Instructor's prompt: "the product", "the product's size" | "a laptop computer", "the laptop's screen size" (original wording, p. 400) | "Product size" was undefined | Restores the original task. |
| 14 | Answers ticked on paper | JSON with five whole-number answers; a schema allows only valid values, and Python re-checks every answer | Mirrors a paper form where only valid boxes exist | None expected. |
| 15 | Each person answers once | An invalid or failed answer is re-asked up to 3 times in a fresh call; every attempt is logged | A malformed reply is a technical failure, not an answer | Counts of retries and exclusions are reported with the results. |
| 16 | 3 of 80 excluded (incomplete) | Agents still invalid after 3 attempts are kept in the file with `valid = False` and excluded from analysis | Same principle: incomplete answers are not analysed | Reported in the data-quality panel. |
| 17 | Humans know nothing about the hypothesis | The prompt never mentions colour, saturation, conditions, the hypothesis or the paper (checked in code) | Prompt hygiene | The finding is published, so the model may still "know" it from training data; the diagnostic run (20 agents with an explanation field) is used to look for this. |

## Analysis

| # | Original | Our simulation | Why | Possible effect |
|---|---|---|---|---|
| 18 | Raw data analysed | No raw human data was provided for Group 1; the human-AI comparison uses published summary statistics | Only what is available | Comparisons are of effect sizes (r with 95% CI, Fisher-z tests), means and SDs. |
| 19 | Per-cell n not reported | Assumed 39 high / 38 low (original), 411 / 412 (replication), labelled "assumed" everywhere | Needed to compute d | Negligible: d changes in the third decimal. |
| 20 | Mediation run because the size effect appeared | Mediation runs only if the AI size effect appears (same rule; the replication skipped it for the same reason) | Follows the original's logic | Mediation may be "skipped", with the reason shown. |
| 21 | Results reported as supporting the hypotheses | Results labelled A (full original pattern), B (replication pattern), C (blind to saturation), D (exaggerated or halo), or Mixed (none of these) | A transparent, pre-set reading rule | "Mixed" was added so unusual patterns are not forced into A to D. |
| 22 | One sample | Optional robustness run at the replication's size (823 agents), always labelled "robustness" | Small AI samples can miss small effects | Reported separately; the main comparison uses n = 77. |

---
*Prepared with AI assistance from Claude (Anthropic).*
