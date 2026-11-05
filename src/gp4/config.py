"""
config.py: load, check and fingerprint the experiment settings.

Where it fits
-------------
STEP 1 of the pipeline. Every other module asks this one for settings, so
there is exactly one place where settings live: config/config_v1.json.

What goes in and out
--------------------
In:  config/config_<version>.json, the prompt files in prompts/<version>/,
     and the images plus stimulus_key.json in stimuli/.
Out: a checked Config object, plus helpers to hash text and files.

Why it is strict
----------------
The course brief forbids changing settings to make AI results look more
human. So this module refuses to run if:
  * a setting is missing or out of range,
  * the prompt files no longer match the signed-off v1 fingerprints
    (this stops anyone editing v1 in place),
  * the arousal maximum in the config disagrees with the prompt text,
  * a stimulus image does not match its recorded hash.
Each error message says what is wrong and how to fix it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The project root is two folders above this file: <root>/src/gp4/config.py.
# Using it means no absolute paths are hard-coded anywhere.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_DIR: Path = PROJECT_ROOT / "config"
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
STIMULI_DIR: Path = PROJECT_ROOT / "stimuli"
DATA_DIR: Path = PROJECT_ROOT / "data"

# CONFIG: the default settings file. A v2 would be config_v2.json.
DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "config_v1.json"

# The four prompt files every prompt version folder must contain.
PROMPT_FILES: tuple[str, ...] = (
    "system.txt",
    "user.txt",
    "output_main.txt",
    "output_diagnostic.txt",
)

RUN_LABELS: tuple[str, ...] = ("smoke", "main", "diagnostic", "robustness")
IMAGE_DETAIL_OPTIONS: tuple[str, ...] = ("low", "high", "auto")
PERSONA_OPTIONS: tuple[str, ...] = ("student", "none")


class ConfigError(Exception):
    """Raised when a setting, prompt file or stimulus is wrong.

    Why this exists: one clear error type with a "how to fix" message is
    easier for a beginner to act on than a Python traceback.
    """


@dataclass(frozen=True)
class Config:
    """All checked experiment settings. Frozen, so code cannot change them.

    Field meanings are documented in config/config_v1.json (the _note keys).
    """

    config_version: str
    signed_off: bool
    signed_off_by: str
    signed_off_date: str
    model: str
    temperature: float | None
    image_detail: str
    pad_images_to_common_canvas: bool
    prompt_version: str
    prompt_file_sha256: dict[str, str]
    persona_mode: str
    pct_male: float
    arousal_max: int
    seed: int
    run_sizes: dict[str, int]
    agent_id_prefix: dict[str, str]
    max_attempts: int
    workers: int
    request_timeout_seconds: int
    max_output_tokens: int
    tost_bound_inches: float
    alpha: float
    mediation_bootstrap_samples: int
    enable_run_page: bool
    source_path: Path = field(compare=False)

    @property
    def prompt_dir(self) -> Path:
        """Folder holding this version's prompt files, e.g. prompts/v1."""
        return PROMPTS_DIR / self.prompt_version

    def as_dict(self) -> dict[str, Any]:
        """Settings as a plain dictionary, for the config snapshot saved with each run."""
        out = {k: v for k, v in self.__dict__.items() if k != "source_path"}
        out["source_path"] = self.source_path.relative_to(PROJECT_ROOT).as_posix()
        return out


# --------------------------------------------------------------------------
# Hashing helpers
# --------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 fingerprint of raw bytes as 64 hex characters.

    Why this exists: one function used for every hash, so they are comparable.
    """
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 fingerprint of a text string (encoded as UTF-8)."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """Return the SHA-256 fingerprint of a file's exact bytes (used for images)."""
    return sha256_bytes(Path(path).read_bytes())


def normalise_prompt_text(raw: str) -> str:
    """Normalise prompt-file text before it is used or hashed.

    Input:  the text of a prompt file.
    Output: the same words, with Windows line endings (CRLF) turned into plain
            line breaks (LF) and the final end-of-file newline removed.
    Why this exists: Git or another operating system can change line endings
    without changing a single word. Normalising first means the hash tracks
    the wording, not the file format. Nothing else is changed.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n")


def read_prompt_file(prompt_dir: Path, name: str) -> str:
    """Read one prompt file and return its normalised text.

    Fails with a helpful message if the file is missing.
    """
    path = Path(prompt_dir) / name
    if not path.is_file():
        raise ConfigError(
            f"Prompt file not found: {path}\n"
            f"Fix: copy the signed-off files from reference/prompts/v1/ into "
            f"{prompt_dir} without editing them."
        )
    # newline="" keeps the raw line endings so normalise_prompt_text sees them.
    with open(path, encoding="utf-8", newline="") as handle:
        return normalise_prompt_text(handle.read())


def prompt_hash(system_text: str, user_text: str) -> str:
    """Fingerprint of the exact system and user text sent to the model.

    Input:  the assembled system text and user (task) text for one agent.
    Output: 64-character SHA-256 hex string. The dataset stores the first 12.
    Why this exists: every data row records which exact wording produced it.
    The two parts are hashed as a JSON list so "ab"+"c" and "a"+"bc" differ.
    """
    payload = json.dumps([system_text, user_text], ensure_ascii=False)
    return sha256_text(payload)


# --------------------------------------------------------------------------
# Loading and checking
# --------------------------------------------------------------------------

def _require(raw: dict[str, Any], key: str, path: Path) -> Any:
    """Return raw[key] or raise a ConfigError naming the missing key."""
    if key not in raw:
        raise ConfigError(
            f"Setting '{key}' is missing from {path.name}.\n"
            f"Fix: add \"{key}\" to the file (see config_v1.json for an example)."
        )
    return raw[key]


def _check_choice(name: str, value: Any, options: tuple[str, ...]) -> None:
    """Raise if value is not one of the allowed options."""
    if value not in options:
        raise ConfigError(
            f"Setting '{name}' is {value!r}, which is not allowed.\n"
            f"Fix: use one of {', '.join(options)}."
        )


def _check_number(name: str, value: Any, low: float, high: float, integer: bool = False) -> None:
    """Raise if value is not a number within [low, high] (and an integer if required)."""
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if not is_number or (integer and not isinstance(value, int)):
        kind = "a whole number" if integer else "a number"
        raise ConfigError(f"Setting '{name}' must be {kind}; got {value!r}.")
    if not low <= value <= high:
        raise ConfigError(
            f"Setting '{name}' is {value}, outside the allowed range {low} to {high}.\n"
            f"Fix: change it in the config file."
        )


def _build_config(raw: dict[str, Any], path: Path) -> Config:
    """Turn the raw JSON dictionary into a Config, checking each value."""
    def get(key: str) -> Any:
        """Fetch a required setting, with a helpful error if it is missing."""
        return _require(raw, key, path)

    temperature = get("temperature")
    if temperature is not None:
        _check_number("temperature", temperature, 0.0, 2.0)
        temperature = float(temperature)

    _check_choice("image_detail", get("image_detail"), IMAGE_DETAIL_OPTIONS)
    _check_choice("persona_mode", get("persona_mode"), PERSONA_OPTIONS)
    _check_number("pct_male", get("pct_male"), 0.0, 1.0)
    # Only 7 or 9 are meaningful here: 9 = original affect grid, 7 = replication.
    _check_choice("arousal_max", get("arousal_max"), (7, 9))  # type: ignore[arg-type]
    _check_number("seed", get("seed"), 0, 2**32 - 1, integer=True)
    _check_number("max_attempts", get("max_attempts"), 1, 10, integer=True)
    _check_number("workers", get("workers"), 1, 16, integer=True)
    _check_number("request_timeout_seconds", get("request_timeout_seconds"), 5, 600, integer=True)
    _check_number("max_output_tokens", get("max_output_tokens"), 50, 4000, integer=True)
    _check_number("tost_bound_inches", get("tost_bound_inches"), 0.01, 5.0)
    _check_number("alpha", get("alpha"), 0.001, 0.2)
    _check_number("mediation_bootstrap_samples", get("mediation_bootstrap_samples"), 100, 100000, integer=True)

    run_sizes = get("run_sizes")
    prefixes = get("agent_id_prefix")
    for label in RUN_LABELS:
        if label not in run_sizes or label not in prefixes:
            raise ConfigError(
                f"Run label '{label}' is missing from run_sizes or agent_id_prefix.\n"
                f"Fix: both must list smoke, main, diagnostic and robustness."
            )
        _check_number(f"run_sizes.{label}", run_sizes[label], 2, 5000, integer=True)

    if not isinstance(get("model"), str) or not get("model").strip():
        raise ConfigError("Setting 'model' must be a model name such as \"gpt-4o-mini\".")

    return Config(
        config_version=str(get("config_version")),
        signed_off=bool(get("signed_off")),
        signed_off_by=str(get("signed_off_by")),
        signed_off_date=str(get("signed_off_date")),
        model=get("model").strip(),
        temperature=temperature,
        image_detail=get("image_detail"),
        pad_images_to_common_canvas=bool(get("pad_images_to_common_canvas")),
        prompt_version=str(get("prompt_version")),
        prompt_file_sha256=dict(get("prompt_file_sha256")),
        persona_mode=get("persona_mode"),
        pct_male=float(get("pct_male")),
        arousal_max=int(get("arousal_max")),
        seed=int(get("seed")),
        run_sizes={k: int(v) for k, v in run_sizes.items()},
        agent_id_prefix={k: str(v) for k, v in prefixes.items()},
        max_attempts=int(get("max_attempts")),
        workers=int(get("workers")),
        request_timeout_seconds=int(get("request_timeout_seconds")),
        max_output_tokens=int(get("max_output_tokens")),
        tost_bound_inches=float(get("tost_bound_inches")),
        alpha=float(get("alpha")),
        mediation_bootstrap_samples=int(get("mediation_bootstrap_samples")),
        enable_run_page=bool(get("enable_run_page")),
        source_path=path,
    )


def verify_prompt_files(config: Config) -> None:
    """Check the prompt files still match their signed-off fingerprints.

    Why this exists: rule "never edit v1 in place". If any word in a v1 prompt
    file changes, its fingerprint changes and the run is blocked.
    """
    for name in PROMPT_FILES:
        expected = config.prompt_file_sha256.get(name)
        if not expected:
            raise ConfigError(f"prompt_file_sha256 has no entry for {name} in {config.source_path.name}.")
        actual = sha256_text(read_prompt_file(config.prompt_dir, name))
        if actual != expected:
            raise ConfigError(
                f"{config.prompt_dir.name}/{name} has changed since it was signed off.\n"
                f"  expected fingerprint {expected[:12]}..., found {actual[:12]}...\n"
                f"Fix: restore the file from reference/prompts/{config.prompt_version}/. "
                f"If the wording must change, create a new version folder (v2), a new "
                f"config file, and a CHANGELOG.md entry; never edit {config.prompt_version} in place."
            )


def verify_arousal_scale(config: Config) -> None:
    """Check the arousal maximum in the config matches the prompt wording.

    Why this exists: arousal_max is a single setting (open question: 7 or 9),
    but the v1 prompt text spells out "1-9". If they disagree the agents would
    be shown one scale and validated against another.
    """
    user = read_prompt_file(config.prompt_dir, "user.txt")
    output = read_prompt_file(config.prompt_dir, "output_main.txt")
    phrase_user = f"{config.arousal_max} = high arousal"
    phrase_output = f'"arousal": <integer 1-{config.arousal_max}>'
    if phrase_user not in user or phrase_output not in output:
        raise ConfigError(
            f"arousal_max is {config.arousal_max}, but the {config.prompt_version} prompt text "
            f"does not describe a 1-{config.arousal_max} arousal scale.\n"
            f"Fix: set arousal_max back to the value written in the prompt, or create a "
            f"new prompt version whose text uses the new scale."
        )


def load_stimulus_key() -> dict[str, dict[str, Any]]:
    """Read stimuli/stimulus_key.json and return {condition: {file, sha256}}.

    Why this exists: the mapping from neutral file name to condition is needed
    in Python to assign images, but it is NEVER sent to the model.
    """
    key_path = STIMULI_DIR / "stimulus_key.json"
    if not key_path.is_file():
        raise ConfigError(
            f"Stimulus key not found: {key_path}\n"
            f"Fix: copy reference/stimuli/stimulus_key.json into stimuli/."
        )
    raw = json.loads(key_path.read_text(encoding="utf-8"))
    by_condition: dict[str, dict[str, Any]] = {}
    for file_name, info in raw.items():
        by_condition[info["condition"]] = {"file": file_name, "sha256": info["sha256"]}
    if set(by_condition) != {"high", "low"}:
        raise ConfigError("stimulus_key.json must map exactly one file to 'high' and one to 'low'.")
    return by_condition


def verify_stimuli() -> dict[str, dict[str, Any]]:
    """Check both stimulus images exist and match their recorded hashes.

    Output: the stimulus key, {condition: {file, sha256}}, once verified.
    """
    key = load_stimulus_key()
    for condition, info in key.items():
        path = STIMULI_DIR / info["file"]
        if not path.is_file():
            raise ConfigError(
                f"Stimulus image missing: {path}\n"
                f"Fix: copy it from reference/stimuli/ (it must be byte-identical)."
            )
        actual = sha256_file(path)
        if actual != info["sha256"]:
            raise ConfigError(
                f"{info['file']} ({condition}) does not match its recorded hash.\n"
                f"Fix: restore the byte-identical copy from reference/stimuli/."
            )
    return key


def load_config(path: Path | str | None = None, verify: bool = True) -> Config:
    """Load a config file, check every value, and (by default) verify prompts and stimuli.

    Inputs:  path to a config JSON file (default config/config_v1.json);
             verify=False skips the prompt and image checks (used only in tests).
    Output:  a frozen Config object.
    Why this exists: a single front door for settings, so nothing runs on
    unchecked values.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(
            f"Config file not found: {config_path}\n"
            f"Fix: run from the project folder, or pass the correct path."
        )
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ConfigError(
            f"{config_path.name} is not valid JSON (line {err.lineno}, column {err.colno}): {err.msg}.\n"
            f"Fix: check for a missing comma or quote near that line."
        ) from err

    # Keys starting with "_" are human notes; drop them before checking.
    settings = {k: v for k, v in raw.items() if not k.startswith("_")}
    config = _build_config(settings, config_path)

    if verify:
        verify_prompt_files(config)
        verify_arousal_scale(config)
        verify_stimuli()
    return config


def require_sign_off(config: Config) -> None:
    """Block live (paid) runs until the settings are signed off.

    Why this exists: rule "settings are fixed before any live run". Dry runs
    do not call this, so testing still works before sign-off.
    """
    if not config.signed_off:
        raise ConfigError(
            f"{config.source_path.name} is not signed off, so live runs are blocked.\n"
            f"Fix: after Dale approves every PROPOSED value, set \"signed_off\": true and fill in "
            f"signed_off_by and signed_off_date. Do this once, before the first live run."
        )
