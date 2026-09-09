"""Loading agent prompts from disk.

Prompts live in `services/<name>/prompts/<agent>.md`, versioned in git, loaded
at runtime. Never a string literal in application code: a prompt in a literal
cannot be diffed, reviewed, or versioned, and every model call records the
prompt version it used.

The header block is parsed rather than skipped, because `prompt_version` is
written to the audit log on every call and a prompt without one cannot be
reconstructed after the fact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from spine.inference.adapter import ModelSpec

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

_HEADER_BLOCK: Final[re.Pattern[str]] = re.compile(r"^#[^\n]*\n+```\n(.*?)\n```", re.DOTALL)
_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"version", "module", "model", "temperature", "max_output_tokens", "owner"}
)
_REQUIRED_SECTIONS: Final[tuple[str, ...]] = (
    "ROLE",
    "TASK",
    "CONTEXT",
    "OUTPUT",
)


class PromptLoadError(RuntimeError):
    """Raised when a prompt file is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class Prompt:
    """One agent prompt, with the header the audit log needs."""

    name: str
    version: str
    module: str
    model_class: str
    temperature: float
    max_output_tokens: int
    owner: str
    body: str
    path: Path

    @property
    def is_clinical_temperature(self) -> bool:
        """Whether this prompt runs deterministic.

        Reasoning must. Conversational phrasing may use low non-zero.
        """
        return self.temperature == 0.0


def prompts_dir(service: str) -> Path:
    return REPO_ROOT / "services" / service / "prompts"


def _parse_header(raw: str, path: Path) -> dict[str, str]:
    match = _HEADER_BLOCK.search(raw)
    if match is None:
        raise PromptLoadError(
            f"{path} has no header block. Every prompt opens with a title line then a "
            f"fenced block carrying version, module, model, temperature, "
            f"max_output_tokens and owner"
        )
    header: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise PromptLoadError(
                f"{path} header line {line.strip()!r} is not 'key: value'"
            )
        header[key.strip()] = value.strip()
    missing = sorted(_REQUIRED_KEYS - set(header))
    if missing:
        raise PromptLoadError(
            f"{path} header is missing {', '.join(missing)}. The version in particular "
            f"is written to the audit log on every call, and a decision made under an "
            f"unversioned prompt cannot be reconstructed"
        )
    return header


def _check_sections(raw: str, path: Path) -> None:
    absent = [name for name in _REQUIRED_SECTIONS if f"## {name}" not in raw]
    if absent:
        raise PromptLoadError(
            f"{path} is missing required section(s): {', '.join(absent)}. A prompt "
            f"without an OUTPUT section has no contract, and one without ROLE and TASK "
            f"has no scope"
        )


def load(service: str, agent: str, directory: Path | None = None) -> Prompt:
    """Load one agent's prompt.

    Validates the header and the required sections rather than trusting the file,
    because a prompt that loads but omits its OUTPUT contract fails at the first
    model call rather than at startup.
    """
    base = directory if directory is not None else prompts_dir(service)
    path = base / f"{agent}.md"
    if not path.is_file():
        raise PromptLoadError(
            f"no prompt for agent {agent!r} at {path}. Prompts are files, versioned in "
            f"git and loaded at runtime, never string literals in application code"
        )
    raw = path.read_text(encoding="utf-8")
    header = _parse_header(raw, path)
    _check_sections(raw, path)
    try:
        temperature = float(header["temperature"])
        max_output_tokens = int(header["max_output_tokens"])
    except ValueError as error:
        raise PromptLoadError(
            f"{path} header has a non-numeric temperature or max_output_tokens: {error}"
        ) from error
    return Prompt(
        name=agent,
        version=header["version"],
        module=header["module"],
        model_class=header["model"],
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        owner=header["owner"],
        body=raw,
        path=path,
    )


def load_all(service: str, directory: Path | None = None) -> dict[str, Prompt]:
    """Every prompt belonging to `service`."""
    base = directory if directory is not None else prompts_dir(service)
    if not base.is_dir():
        raise PromptLoadError(f"prompt directory {base} does not exist")
    found = sorted(base.glob("*.md"))
    if not found:
        raise PromptLoadError(f"no prompt files in {base}")
    return {path.stem: load(service, path.stem, base) for path in found}


def assert_clinical_prompts_are_deterministic(
    prompts: dict[str, Prompt],
    conversational: frozenset[str],
) -> None:
    """Confirm every reasoning prompt runs at temperature 0.

    Conversational phrasing may use a low non-zero temperature; reasoning may
    not. Named explicitly rather than inferred, so adding an agent forces the
    decision rather than defaulting it.
    """
    offenders = sorted(
        f"{name} at {prompt.temperature}"
        for name, prompt in prompts.items()
        if name not in conversational and not prompt.is_clinical_temperature
    )
    if offenders:
        raise PromptLoadError(
            f"clinical reasoning must run at temperature 0, but: {', '.join(offenders)}. "
            f"Set temperature to 0 in the prompt header, or add the agent to the "
            f"conversational set if its job is phrasing rather than reasoning"
        )


def spec_for(prompt: Prompt, model: str) -> ModelSpec:
    """The model to call for one agent: name from the caller, tuning from the prompt.

    These come from different places for a reason, and conflating them was a
    live bug in every agent in this repository. `prompt.model_class` documents
    what *class* of model an agent needs — "local instruct, 7-8B quantised" —
    which is guidance for whoever deploys this. It is not a model name. Passed
    to Ollama it returns HTTP 400, so no agent could reach a model at all.

    The tests did not catch it because they mock the provider, which is the
    right thing for them to test. Only calling a real model finds this, which
    is why the eval harness now does.

    `model` is the deployment's choice and arrives from InferenceConfig.
    Temperature and token budget belong to the prompt: they are properties of
    the task rather than of the installation, and a clinical prompt that must
    run deterministic says so in its own header.
    """
    if not model.strip():
        raise PromptLoadError(
            f"no model name given for {prompt.name}. Pass the configured model from "
            f"InferenceConfig; prompt.model_class describes the class of model this "
            f"agent needs and is not a name Ollama will accept"
        )
    return ModelSpec(
        name=model,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
