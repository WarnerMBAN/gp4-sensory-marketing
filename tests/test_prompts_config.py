"""
test_prompts_config.py: prompt integrity and config safety checks.

Why this exists
---------------
Integrity rules are enforced in code, and these tests prove the enforcement
works:
  * prompts/v1 is identical to the signed-off reference/prompts/v1;
  * the assembled prompt contains no leaks (colour, saturation, file names);
  * placeholders are filled exactly as signed off;
  * a changed prompt file or a mismatched arousal maximum blocks the run;
  * live runs are blocked until the settings are signed off.
"""

import dataclasses
import filecmp

import pytest

from gp4.config import (
    PROJECT_ROOT,
    PROMPT_FILES,
    ConfigError,
    load_config,
    require_sign_off,
    verify_arousal_scale,
    verify_prompt_files,
)
from gp4.prompts import FORBIDDEN_TERMS, assemble_prompt, check_hygiene

REFERENCE_PROMPTS = PROJECT_ROOT / "reference" / "prompts" / "v1"


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.mark.skipif(not REFERENCE_PROMPTS.is_dir(), reason="reference/ folder not present (it is not on GitHub)")
@pytest.mark.parametrize("name", PROMPT_FILES)
def test_v1_files_byte_identical_to_reference(name):
    assert filecmp.cmp(REFERENCE_PROMPTS / name, PROJECT_ROOT / "prompts" / "v1" / name, shallow=False)


def test_config_loads_and_verifies(config):
    assert config.prompt_version == "v1"
    assert config.arousal_max == 9


@pytest.mark.parametrize("gender", ["male", "female"])
@pytest.mark.parametrize("diagnostic", [False, True])
def test_assembled_prompt_is_clean(config, gender, diagnostic):
    prompt = assemble_prompt(config, gender, diagnostic)
    full = (prompt.system_text + "\n" + prompt.user_text).lower()
    for term in FORBIDDEN_TERMS:
        assert term not in full
    assert "{" + "persona_line}" not in full and "{" + "output_block}" not in full
    assert len(prompt.prompt_sha) == 12


def test_persona_line_exact(config):
    prompt = assemble_prompt(config, "female")
    assert prompt.system_text == (
        "You are a participant in a research study. You are a female undergraduate university student."
    )


def test_no_persona_system_text(config):
    none_cfg = dataclasses.replace(config, persona_mode="none")
    assert assemble_prompt(none_cfg, "").system_text == "You are a participant in a research study."


def test_diagnostic_adds_explanation_only_in_diagnostic(config):
    assert '"explanation"' not in assemble_prompt(config, "male", diagnostic=False).user_text
    assert '"explanation"' in assemble_prompt(config, "male", diagnostic=True).user_text


def test_hash_differs_by_persona_and_is_stable(config):
    male_1 = assemble_prompt(config, "male").prompt_sha_full
    male_2 = assemble_prompt(config, "male").prompt_sha_full
    female = assemble_prompt(config, "female").prompt_sha_full
    assert male_1 == male_2 and male_1 != female


def test_hygiene_catches_leaks():
    for leak in ["This laptop has high saturation.", "See stim_A.png", "a vivid red laptop", "{persona_line}"]:
        with pytest.raises(ConfigError):
            check_hygiene(leak)


def test_edited_prompt_is_blocked(config):
    tampered = dataclasses.replace(config, prompt_file_sha256={**config.prompt_file_sha256, "user.txt": "0" * 64})
    with pytest.raises(ConfigError, match="changed since it was signed off"):
        verify_prompt_files(tampered)


def test_arousal_mismatch_is_blocked(config):
    with pytest.raises(ConfigError, match="arousal_max is 7"):
        verify_arousal_scale(dataclasses.replace(config, arousal_max=7))


def test_live_runs_blocked_until_signed_off(config):
    with pytest.raises(ConfigError, match="not signed off"):
        require_sign_off(dataclasses.replace(config, signed_off=False))
    require_sign_off(dataclasses.replace(config, signed_off=True))  # no error once signed off
