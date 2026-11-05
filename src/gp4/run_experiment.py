"""
run_experiment.py: run every agent once and save the data.

Where it fits
-------------
STEP 7 of the pipeline. Called by scripts/run_dry.py (mock answers) and
scripts/run_live.py (real API calls, Phase 6). Uses every earlier module.

Flow (numbered to match the comments below)
-------------------------------------------
  STEP 1 of 6  Check settings, prompts and images (and sign-off, if live).
  STEP 2 of 6  Build the roster: who sees which image, with which persona.
  STEP 3 of 6  Load the two images (optionally padded; off by default).
  STEP 4 of 6  Run each agent: call, validate, retry if needed. Each agent's
               full record is appended to the JSONL log the moment it finishes.
  STEP 5 of 6  Write the tidy CSV (one row per agent).
  STEP 6 of 6  Write the config snapshot and the summary in the run log.

What goes in and out
--------------------
In:  Config, run label, a client (OpenAIClient or MockClient).
Out: four files in data/real/ (live) or data/mock/ (dry run), named
     gp4_<run_label>_<run_id>.*:
       .csv          tidy data, one row per agent (columns: data/VARIABLE_DICTIONARY.md)
       _raw.jsonl    one JSON record per agent, including every attempt
       _config.json  every setting, prompt variants, library versions
       _run.log      human-readable log: start, warnings, retries, summary
Existing files are never overwritten.
"""

from __future__ import annotations

import io
import json
import logging
import platform
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from gp4.agents import Agent, build_roster
from gp4.config import (
    DATA_DIR,
    PROJECT_ROOT,
    STIMULI_DIR,
    Config,
    ConfigError,
    require_sign_off,
    sha256_bytes,
    verify_stimuli,
)
from gp4.llm_client import FatalClientError, LLMClient, LLMRequest, LLMResult
from gp4.prompts import AssembledPrompt, assemble_prompt
from gp4.validate import RATING_KEYS, attention_mean, check_response, should_retry

# Column order of the tidy CSV (matches data/VARIABLE_DICTIONARY.md).
CSV_COLUMNS: list[str] = [
    "agent_id", "run_label", "run_id", "dry_run", "condition", "stim_file", "stim_sha256",
    "persona_mode", "gender", "model", "temperature", "image_detail", "prompt_version",
    "prompt_sha", "seed", "screen_size", "attention_getting", "capture_attention",
    "attention", "arousal", "mood", "explanation", "valid", "attempts", "errors",
    "raw_output", "response_id", "input_tokens", "output_tokens", "called_at",
]


@dataclass
class RunOutputs:
    """Paths and headline numbers from one run (returned to the calling script)."""

    run_id: str
    csv_path: Path
    jsonl_path: Path
    config_path: Path
    log_path: Path
    n_agents: int
    n_valid: int
    n_retried: int
    total_attempts: int
    aborted: bool = False
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def output_folder(dry_run: bool) -> Path:
    """data/mock for dry runs, data/real for live runs (kept strictly apart)."""
    folder = DATA_DIR / ("mock" if dry_run else "real")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def display_path(path: Path) -> str:
    """Path relative to the project folder when possible (shorter, no user name in logs)."""
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def new_run_id() -> str:
    """Run start time, local, YYYYMMDD_HHMMSS (used in every file name)."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def make_logger(log_path: Path, echo: bool) -> logging.Logger:
    """A logger that writes to the run's .log file and (optionally) the screen."""
    logger = logging.getLogger(f"gp4.run.{log_path.stem}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if echo:
        screen = logging.StreamHandler()
        screen.setFormatter(formatter)
        logger.addHandler(screen)
    return logger


def pad_to_canvas(image_bytes: bytes, width: int, height: int) -> bytes:
    """Centre an image on a white canvas of the given size. Used ONLY if the config asks.

    Why this exists: the two stimuli have slightly different white margins
    (311 x 213 vs 315 x 216). Padding is a declared, logged option, off by default.
    """
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as original:
        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        left = (width - original.width) // 2
        top = (height - original.height) // 2
        canvas.paste(original.convert("RGB"), (left, top))
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        return buffer.getvalue()


def load_images(config: Config, stimulus_key: dict[str, dict[str, str]], logger: logging.Logger) -> dict[str, bytes]:
    """STEP 3: read both images; pad them to one canvas only if the config says so.

    Output: {condition: image bytes to send}.
    """
    images = {cond: (STIMULI_DIR / info["file"]).read_bytes() for cond, info in stimulus_key.items()}
    if not config.pad_images_to_common_canvas:
        logger.info("Images sent unchanged (pad_images_to_common_canvas = false).")
        return images

    from PIL import Image

    sizes = {c: Image.open(io.BytesIO(b)).size for c, b in images.items()}
    width = max(w for w, _ in sizes.values())
    height = max(h for _, h in sizes.values())
    padded = {c: pad_to_canvas(b, width, height) for c, b in images.items()}
    logger.warning(
        "PADDING ON: images padded to a common %dx%d white canvas (original sizes %s). "
        "This is a deviation and must be listed in DEVIATIONS.md.", width, height, sizes,
    )
    return padded


# --------------------------------------------------------------------------
# One agent
# --------------------------------------------------------------------------

class RunStopped(Exception):
    """Raised inside an agent when the run was stopped by a fatal error elsewhere."""


def run_one_agent(
    agent: Agent,
    prompt: AssembledPrompt,
    image_bytes: bytes,
    config: Config,
    client: LLMClient,
    diagnostic: bool,
    stop: threading.Event,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """STEP 4 (one agent): call the model, check the answer, retry if needed.

    Output: (tidy row for the CSV, list of attempt records for the JSONL log).
    Every attempt is a fresh, independent call with the same prompt and image.
    stop: shared signal. If another agent hit a fatal error (e.g. a bad key),
    this agent makes no further calls, so no money is spent on doomed calls.
    """
    attempt_log: list[dict[str, Any]] = []
    result: LLMResult | None = None
    check = None
    attempts = 0

    while True:
        if stop.is_set():
            raise RunStopped(agent.agent_id)
        attempts += 1
        request = LLMRequest(
            agent_id=agent.agent_id, attempt=attempts, system_text=prompt.system_text,
            user_text=prompt.user_text, image_bytes=image_bytes, image_mime="image/png",
            diagnostic=diagnostic,
        )
        try:
            result = client.complete(request)
        except FatalClientError:
            stop.set()  # tell every other agent to stop before its next call
            raise
        if result.error:
            check = None
            valid = False
            problems = [result.error]
        else:
            check = check_response(result.raw_text, config.arousal_max, diagnostic)
            valid = check.valid
            problems = check.errors
        attempt_log.append({
            "attempt": attempts, "called_at": result.called_at, "valid": valid,
            "problems": problems, "raw_output": result.raw_text, "response_id": result.response_id,
            "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
            "temperature_sent": result.temperature_sent,
        })
        if not should_retry(attempts, config.max_attempts, valid):
            break

    row = build_row(agent, prompt, image_bytes, config, client, result, check, attempt_log, diagnostic)
    return row, attempt_log


def build_row(
    agent: Agent,
    prompt: AssembledPrompt,
    image_bytes: bytes,
    config: Config,
    client: LLMClient,
    final: LLMResult,
    check: Any,
    attempt_log: list[dict[str, Any]],
    diagnostic: bool,
) -> dict[str, Any]:
    """Assemble the tidy CSV row for one agent from its final attempt.

    Ratings are filled only when the final answer is valid, so an invalid
    answer can never slip into the analysis. The raw text is always kept.
    """
    valid = bool(check is not None and check.valid)
    answers = check.answers if valid else {}
    failed = [f"attempt {a['attempt']}: {'; '.join(a['problems'])}" for a in attempt_log if not a["valid"]]
    row: dict[str, Any] = {
        "agent_id": agent.agent_id,
        "run_label": agent.run_label,
        "condition": agent.condition,
        "stim_file": agent.stim_file,
        "stim_sha256": sha256_bytes(image_bytes),  # hash of the bytes actually sent
        "persona_mode": agent.persona_mode,
        "gender": agent.gender,
        "model": client.model_label,
        "temperature": final.temperature_sent,
        "image_detail": config.image_detail,
        "prompt_version": config.prompt_version,
        "prompt_sha": prompt.prompt_sha,
        "seed": config.seed,
        "attention": None,
        "explanation": answers.get("explanation", "") if diagnostic else "",
        "valid": valid,
        "attempts": len(attempt_log),
        "errors": " | ".join(failed),
        "raw_output": final.raw_text,
        "response_id": final.response_id,
        "input_tokens": final.input_tokens,
        "output_tokens": final.output_tokens,
        "called_at": final.called_at,
    }
    for key in RATING_KEYS:
        row[key] = answers.get(key)
    if valid:
        row["attention"] = attention_mean(answers["attention_getting"], answers["capture_attention"])
    return row


# --------------------------------------------------------------------------
# Whole run
# --------------------------------------------------------------------------

def write_csv(rows: list[dict[str, Any]], path: Path) -> pd.DataFrame:
    """STEP 5: write the tidy CSV, rows sorted by agent_id, columns in dictionary order."""
    frame = pd.DataFrame(rows).reindex(columns=CSV_COLUMNS).sort_values("agent_id")
    for column in ["screen_size", "attention_getting", "capture_attention", "arousal", "mood",
                   "attempts", "input_tokens", "output_tokens", "seed"]:
        frame[column] = frame[column].astype("Int64")  # whole numbers, blanks allowed
    frame.to_csv(path, index=False, encoding="utf-8")
    return frame


def library_versions() -> dict[str, str]:
    """Versions of Python and the key packages, for the config snapshot."""
    import numpy
    import openai
    import scipy

    return {"python": platform.python_version(), "openai": openai.__version__,
            "pandas": pd.__version__, "numpy": numpy.__version__, "scipy": scipy.__version__}


def write_snapshot(
    path: Path, config: Config, run_label: str, run_id: str, dry_run: bool, client: LLMClient,
    prompts: dict[str, AssembledPrompt], image_hashes: dict[str, str], n_agents: int,
) -> None:
    """STEP 6: save every setting and the exact prompt variants used, for audit."""
    snapshot = {
        "run_id": run_id,
        "run_label": run_label,
        "dry_run": dry_run,
        "n_agents": n_agents,
        "client": client.model_label,
        "mock_scenario": getattr(client, "scenario", None),
        "temperature_note": getattr(client, "temperature_note", ""),
        "settings": config.as_dict(),
        "image_sha256_sent": image_hashes,
        "prompt_variants": {p.prompt_sha: {"system_text": p.system_text, "user_text": p.user_text}
                            for p in prompts.values()},
        "library_versions": library_versions(),
    }
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")


def run_experiment(
    config: Config,
    run_label: str,
    client: LLMClient,
    dry_run: bool,
    n_agents: int | None = None,
    echo: bool = True,
    out_dir: Path | None = None,
) -> RunOutputs:
    """Run every agent for one run label and save all outputs. Main entry point.

    Inputs:
      config     checked settings (load_config())
      run_label  smoke, main, diagnostic or robustness
      client     OpenAIClient (live) or MockClient (dry run)
      dry_run    True for mock data: rows marked dry_run = True, saved in data/mock/
      n_agents   optional override of the run size (tests and quick checks only)
      echo       also print the log to the screen
      out_dir    optional output folder (tests only); default data/mock or data/real
    Output: RunOutputs with file paths and headline counts.
    """
    # STEP 1 of 6: settings, prompts and images were verified by load_config();
    # live runs additionally need the sign-off, and must use a real client.
    if not dry_run:
        require_sign_off(config)
        if client.model_label == "MOCK":
            raise ConfigError("A live run cannot use the MockClient. Use run_dry.py for mock data.")
    stimulus_key = verify_stimuli()
    diagnostic = run_label == "diagnostic"

    run_id = new_run_id()
    folder = Path(out_dir) if out_dir is not None else output_folder(dry_run)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"gp4_{run_label}_{run_id}"
    paths = {ext: folder / f"{stem}{ext}" for ext in (".csv", "_raw.jsonl", "_config.json", "_run.log")}
    for existing in (p for p in paths.values() if p.exists()):
        raise FileExistsError(f"{existing} already exists; refusing to overwrite. Wait a second and rerun.")
    logger = make_logger(paths["_run.log"], echo)
    logger.info("START run %s | label=%s | dry_run=%s | client=%s | config=%s | prompt=%s",
                run_id, run_label, dry_run, client.model_label, config.config_version, config.prompt_version)
    if dry_run:
        logger.warning("DRY RUN: answers are MOCK DATA, NOT RESULTS. Saved to %s", display_path(folder))

    # STEP 2 of 6: roster.
    roster = build_roster(config, run_label, stimulus_key, n_agents)
    n_high = sum(a.condition == "high" for a in roster)
    logger.info("Roster: %d agents (%d high, %d low), seed %d, persona %s",
                len(roster), n_high, len(roster) - n_high, config.seed, config.persona_mode)

    # STEP 3 of 6: images.
    images = load_images(config, stimulus_key, logger)
    image_hashes = {cond: sha256_bytes(b) for cond, b in images.items()}

    # Prompts: one per distinct gender (same text for every agent of that persona).
    prompts = {g: assemble_prompt(config, g, diagnostic) for g in sorted({a.gender for a in roster})}
    for gender, prompt in prompts.items():
        logger.info("Prompt variant persona=%s prompt_sha=%s", gender or "(none)", prompt.prompt_sha)

    # STEP 4 of 6: run the agents (independent calls, a few at a time).
    rows: list[dict[str, Any]] = []
    jsonl_lock = threading.Lock()
    aborted = False
    temperature_noted = False  # print the "temperature rejected" note once, not per agent
    stop = threading.Event()
    with open(paths["_raw.jsonl"], "a", encoding="utf-8") as jsonl, ThreadPoolExecutor(config.workers) as pool:
        futures = {
            pool.submit(run_one_agent, agent, prompts[agent.gender], images[agent.condition],
                        config, client, diagnostic, stop): agent
            for agent in roster
        }
        for future in as_completed(futures):
            agent = futures[future]
            try:
                row, attempt_log = future.result()
            except FatalClientError as err:
                if not aborted:
                    aborted = True
                    logger.error("ABORTED at %s: %s", agent.agent_id, err)
                    for pending in futures:
                        pending.cancel()  # agents not yet started never start
                continue
            except (RunStopped, CancelledError):
                continue  # stopped because of the fatal error above; no call was made
            # Agents that finished are always saved, even if the run is aborting.
            row.update(run_id=run_id, dry_run=dry_run)
            rows.append(row)
            with jsonl_lock:  # one complete line per agent, written as soon as it finishes
                jsonl.write(json.dumps({**row, "attempt_log": attempt_log}, ensure_ascii=False) + "\n")
                jsonl.flush()
            if row["attempts"] > 1 or not row["valid"]:
                logger.warning("%s: %s after %d attempt(s). %s", agent.agent_id,
                               "valid" if row["valid"] else "INVALID", row["attempts"], row["errors"])
            if getattr(client, "temperature_note", "") and not temperature_noted:
                logger.warning(client.temperature_note)
                temperature_noted = True

    # STEP 5 of 6: tidy CSV.
    frame = write_csv(rows, paths[".csv"])

    # STEP 6 of 6: snapshot and summary.
    write_snapshot(paths["_config.json"], config, run_label, run_id, dry_run, client, prompts,
                   image_hashes, len(roster))
    n_valid = int(frame["valid"].sum())
    n_retried = int((frame["attempts"] > 1).sum())
    total_attempts = int(frame["attempts"].sum())
    logger.info("SUMMARY: %d of %d agents completed; %d valid (%.1f%%); %d invalid (excluded from analysis); "
                "%d needed a retry; %d calls in total.",
                len(frame), len(roster), n_valid, 100 * n_valid / max(len(frame), 1),
                len(frame) - n_valid, n_retried, total_attempts)
    if not dry_run and frame["input_tokens"].notna().any():
        logger.info("Tokens (final attempts): %d input, %d output.",
                    int(frame["input_tokens"].sum()), int(frame["output_tokens"].sum()))
    for p in paths.values():
        logger.info("Wrote %s", display_path(p))
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    if aborted:
        raise FatalClientError(f"Run {run_id} stopped early; partial results saved. See {paths['_run.log'].name}.")

    return RunOutputs(run_id, paths[".csv"], paths["_raw.jsonl"], paths["_config.json"], paths["_run.log"],
                      len(frame), n_valid, n_retried, total_attempts, aborted)
