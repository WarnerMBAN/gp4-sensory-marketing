"""
prompts.py: assemble the exact text each agent receives.

Where it fits
-------------
STEP 4 of the pipeline. Takes the signed-off prompt files (prompts/v1/) and
one agent's persona, and returns the system text and user (task) text. The
image is attached separately by llm_client.py, before the task text.

What goes in and out
--------------------
In:  Config (which prompt version), the agent's gender (or none), and whether
     this is a diagnostic run (adds the explanation field).
Out: an AssembledPrompt with system_text, user_text and prompt_sha.

No hidden logic
---------------
The only changes made to the file text are:
  1. {persona_line} in system.txt is replaced by the persona sentence, or by
     nothing when persona_mode is "none".
  2. {output_block} in user.txt is replaced by output_main.txt (or
     output_diagnostic.txt for diagnostic runs).
  3. Line endings are normalised and the final file newline removed (see
     config.normalise_prompt_text). No words change.
A hygiene check then refuses any text that mentions the manipulation, the
hypothesis, the paper, or a file name, so the condition cannot leak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gp4.config import Config, ConfigError, prompt_hash, read_prompt_file

# The persona sentence, exactly as signed off in PROMPT_NOTES_v1.md. Note the
# leading space: it follows "You are a participant in a research study."
PERSONA_TEMPLATE: str = " You are a {gender} undergraduate university student."

# Words that must never reach the model (lower-case substring match).
# They would reveal the manipulation, the hypothesis, the paper or the file name.
FORBIDDEN_TERMS: tuple[str, ...] = (
    "satur",          # saturation, saturated
    "vivid",
    "dull",
    "colour",
    "color",
    "hue",
    "hypothes",       # hypothesis, hypothesise
    "size effect",
    "condition",
    "hagtvedt",
    "brasel",
    "stim_",          # neutral file names
    ".png",
    "high-saturation",
    "low-saturation",
)

# Matches a leftover placeholder such as {persona_line}.
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


@dataclass(frozen=True)
class AssembledPrompt:
    """The exact text sent to the model for one agent.

    prompt_sha_full: SHA-256 of [system_text, user_text] (see config.prompt_hash).
    prompt_sha:      first 12 characters, stored on every data row.
    """

    system_text: str
    user_text: str
    prompt_sha_full: str

    @property
    def prompt_sha(self) -> str:
        """Short fingerprint for the dataset (12 hex characters)."""
        return self.prompt_sha_full[:12]


def persona_line(persona_mode: str, gender: str) -> str:
    """Return the persona sentence for system.txt, or "" when there is no persona.

    Inputs:  persona_mode ("student" or "none"); gender ("male", "female" or "").
    Why this exists: keeps the one persona rule in one visible place.
    """
    if persona_mode == "none":
        return ""
    if gender not in ("male", "female"):
        raise ConfigError(f"Student persona needs gender 'male' or 'female'; got {gender!r}.")
    return PERSONA_TEMPLATE.format(gender=gender)


def check_hygiene(text: str) -> None:
    """Raise if the text contains a forbidden term or an unfilled placeholder.

    Why this exists: rule "prompts must not reveal the hypothesis or the
    condition", enforced in code rather than trusted to memory.
    """
    lowered = text.lower()
    for term in FORBIDDEN_TERMS:
        if term in lowered:
            raise ConfigError(
                f"Prompt hygiene failure: the text sent to the model contains {term!r}.\n"
                f"Fix: remove it. The model must not learn the manipulation, hypothesis or file name."
            )
    leftover = _PLACEHOLDER.search(text)
    if leftover:
        raise ConfigError(f"Prompt still contains the unfilled placeholder {leftover.group(0)}.")


def build_system_text(config: Config, gender: str) -> str:
    """Fill system.txt with the persona line (or nothing)."""
    template = read_prompt_file(config.prompt_dir, "system.txt")
    return template.replace("{persona_line}", persona_line(config.persona_mode, gender))


def build_user_text(config: Config, diagnostic: bool) -> str:
    """Fill user.txt with the main or diagnostic output block."""
    template = read_prompt_file(config.prompt_dir, "user.txt")
    block_file = "output_diagnostic.txt" if diagnostic else "output_main.txt"
    output_block = read_prompt_file(config.prompt_dir, block_file)
    return template.replace("{output_block}", output_block)


def assemble_prompt(config: Config, gender: str, diagnostic: bool = False) -> AssembledPrompt:
    """Build, check and fingerprint the full prompt for one agent.

    Inputs:  config; the agent's gender ("" when persona_mode is "none");
             diagnostic=True adds the explanation field (diagnostic runs only).
    Output:  AssembledPrompt with the exact system and user text and its hash.
    """
    system_text = build_system_text(config, gender)
    user_text = build_user_text(config, diagnostic)
    check_hygiene(system_text)
    check_hygiene(user_text)
    return AssembledPrompt(
        system_text=system_text,
        user_text=user_text,
        prompt_sha_full=prompt_hash(system_text, user_text),
    )
