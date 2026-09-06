"""The one inference adapter.

Every model call in every service goes through this interface. Model identity,
quantisation, and sampling are configuration, so a model swap is a config change
plus an evaluation re-run, never a code change.

ADR 0007 permitted a hosted transport for development. That option was
subsequently dropped: the platform is local only, so there is no dev-to-prod
behaviour gap and no key management. If a hosted transport is ever wanted, it
implements `InferenceProvider` and the production-mode assertion in `config.py`
is what keeps it out of a clinic.

Structured output is enforced, not requested. `complete_structured` validates
against a schema and retries once, then fails loudly. "Please respond in JSON"
is not a contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel, ValidationError

SchemaT = TypeVar("SchemaT", bound=BaseModel)

CLINICAL_TEMPERATURE = 0.0
"""Reasoning runs deterministic. Conversational phrasing may use low non-zero."""

MAX_TEMPERATURE = 2.0
"""Above this no provider behaves usefully; a value beyond it is a typo."""


class Transport(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"


class InferenceError(RuntimeError):
    """Raised when a model call cannot be completed."""


class StructuredOutputError(InferenceError):
    """Raised when output does not validate against its schema after one retry."""


@dataclass(frozen=True)
class ModelSpec:
    """Which model to call and how.

    `fallbacks` are tried in order when the primary is unreachable. They are not
    tried on a schema validation failure: a model that produced malformed output
    is a prompt problem, and silently swapping models would hide it.
    """

    name: str
    temperature: float = CLINICAL_TEMPERATURE
    max_output_tokens: int = 512
    fallbacks: tuple[str, ...] = ()
    context_window: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ModelSpec needs a model name; set NIDANA_MODEL_PRIMARY")
        if not 0.0 <= self.temperature <= MAX_TEMPERATURE:
            raise ValueError(
                f"temperature {self.temperature} is outside 0.0-{MAX_TEMPERATURE}; "
                f"clinical reasoning uses 0.0"
            )


@dataclass(frozen=True)
class Completion:
    """One model response, with what is needed to audit it.

    `model_version` is the model that actually answered, which may be a fallback
    rather than the primary. The audit log records this one.
    """

    text: str
    model_version: str
    transport: Transport
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    used_fallback: bool = False


@dataclass
class CallRecord:
    """What a provider did, for the audit log."""

    model_version: str
    transport: Transport
    attempts: int = 1
    fallback_chain: list[str] = field(default_factory=list)


class InferenceProvider(ABC):
    """What every transport must do.

    Deliberately narrow. A provider generates text; it does not decide what to
    ask, retry policy above one schema retry, or what the answer means.
    """

    @property
    @abstractmethod
    def transport(self) -> Transport:
        """Which transport this is, recorded on every audit entry."""

    @abstractmethod
    def complete(
        self, *, prompt: str, system: str, spec: ModelSpec, prompt_version: str
    ) -> Completion:
        """Generate a completion, trying fallbacks if the primary is unreachable."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider can be reached right now.

        Called at startup so a misconfigured deployment fails immediately rather
        than at the first patient turn.
        """


def complete_structured(
    provider: InferenceProvider,
    schema: type[SchemaT],
    *,
    prompt: str,
    system: str,
    spec: ModelSpec,
    prompt_version: str,
) -> SchemaT:
    """Generate output that validates against `schema`, with one retry.

    The retry sends the validation error back, because a model given the specific
    failure usually corrects it, while one told merely to try again usually
    repeats itself. After the retry the call fails loudly: a third attempt that
    produced valid-looking output would be the least trustworthy of the three.
    """
    first = provider.complete(
        prompt=prompt, system=system, spec=spec, prompt_version=prompt_version
    )
    try:
        return schema.model_validate_json(first.text)
    except ValidationError as first_error:
        repair = (
            f"{prompt}\n\n"
            f"Your previous response did not match the required schema.\n"
            f"Response was:\n{first.text}\n\n"
            f"Validation errors:\n{first_error}\n\n"
            f"Return only valid JSON matching the schema. No prose, no code fence."
        )
        second = provider.complete(
            prompt=repair, system=system, spec=spec, prompt_version=prompt_version
        )
        try:
            return schema.model_validate_json(second.text)
        except ValidationError as second_error:
            raise StructuredOutputError(
                f"{spec.name} did not produce valid {schema.__name__} after one retry. "
                f"First failure: {first_error}. Second failure: {second_error}. "
                f"This is a prompt or grammar problem, not a transient one; fix the "
                f"prompt in the service's prompts/ directory rather than retrying"
            ) from second_error
