"""Inference configuration and the startup assertions that guard it.

ADR 0007. A clinic deployment cannot leak, because it cannot boot in a leaking
configuration. The check is a startup assertion with a test, not a convention
someone remembers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from spine.inference.adapter import (
    CLINICAL_TEMPERATURE,
    InferenceProvider,
    ModelSpec,
    Transport,
)
from spine.inference.ollama import DEFAULT_HOST, OllamaProvider


class Mode(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class UnsafeConfigurationError(RuntimeError):
    """Raised when a configuration would send patient data off the machine."""


@dataclass(frozen=True)
class InferenceConfig:
    mode: Mode
    transport: Transport
    ollama_host: str
    primary_model: str
    fallback_models: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> InferenceConfig:
        raw_mode = os.environ.get("NIDANA_MODE", Mode.DEVELOPMENT.value).strip().lower()
        if raw_mode not in {m.value for m in Mode}:
            raise UnsafeConfigurationError(
                f"NIDANA_MODE is {raw_mode!r}; it must be 'development' or 'production'. "
                f"An unrecognised mode is refused rather than defaulted, because "
                f"defaulting it would choose the permissive one"
            )
        raw_transport = (
            os.environ.get("NIDANA_INFERENCE_TRANSPORT", Transport.LOCAL.value).strip().lower()
        )
        if raw_transport not in {t.value for t in Transport}:
            raise UnsafeConfigurationError(
                f"NIDANA_INFERENCE_TRANSPORT is {raw_transport!r}; it must be 'local' or "
                f"'hosted'"
            )
        fallbacks = tuple(
            name.strip()
            for name in os.environ.get("NIDANA_MODEL_FALLBACKS", "").split(",")
            if name.strip()
        )
        return cls(
            mode=Mode(raw_mode),
            transport=Transport(raw_transport),
            ollama_host=os.environ.get("NIDANA_OLLAMA_HOST", DEFAULT_HOST),
            primary_model=os.environ.get("NIDANA_MODEL_PRIMARY", "").strip(),
            fallback_models=fallbacks,
        )


def assert_transport_is_permitted(config: InferenceConfig) -> None:
    """Refuse to run a hosted transport in production.

    Hosted inference sends patient utterances off the machine on every turn.
    That is incompatible with the on-premise requirement, and no configuration
    flag should be able to override it silently.
    """
    if config.mode is Mode.PRODUCTION and config.transport is Transport.HOSTED:
        raise UnsafeConfigurationError(
            "NIDANA_MODE=production with NIDANA_INFERENCE_TRANSPORT=hosted would send "
            "patient utterances off this machine on every turn. Nidana runs on-premise; "
            "set NIDANA_INFERENCE_TRANSPORT=local and run a local model, or set "
            "NIDANA_MODE=development if this is not a clinic deployment"
        )


def build_provider(config: InferenceConfig) -> InferenceProvider:
    """The provider this configuration calls for.

    Asserts the transport is permitted before constructing anything, so an
    unsafe configuration fails at startup rather than at the first patient turn.
    """
    assert_transport_is_permitted(config)
    if config.transport is Transport.HOSTED:
        raise UnsafeConfigurationError(
            "no hosted provider is implemented. Nidana runs local inference only; set "
            "NIDANA_INFERENCE_TRANSPORT=local"
        )
    return OllamaProvider(host=config.ollama_host)


def model_spec(
    config: InferenceConfig,
    temperature: float = CLINICAL_TEMPERATURE,
    max_output_tokens: int = 512,
) -> ModelSpec:
    if not config.primary_model:
        raise UnsafeConfigurationError(
            "NIDANA_MODEL_PRIMARY is not set. Name the model to use, for example "
            "'llama3.1:8b-instruct-q4_K_M', and pull it with 'ollama pull'"
        )
    return ModelSpec(
        name=config.primary_model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        fallbacks=config.fallback_models,
    )


def assert_ready(config: InferenceConfig, provider: InferenceProvider) -> None:
    """Confirm the provider is reachable and the model is present.

    Called at startup. A deployment missing its model fails here with a message
    naming the fix, rather than at the first patient turn with an HTTP 404.
    """
    if not provider.is_available():
        raise UnsafeConfigurationError(
            f"no inference provider is reachable at {config.ollama_host}. Start Ollama "
            f"with 'ollama serve', or set NIDANA_OLLAMA_HOST"
        )
    if isinstance(provider, OllamaProvider) and config.primary_model:
        installed = provider.installed_models()
        wanted = {config.primary_model, *config.fallback_models}
        missing = sorted(name for name in wanted if name not in installed)
        if missing and len(missing) == len(wanted):
            raise UnsafeConfigurationError(
                f"none of the configured models are installed: {', '.join(missing)}. "
                f"Run 'ollama pull {config.primary_model}'"
            )
