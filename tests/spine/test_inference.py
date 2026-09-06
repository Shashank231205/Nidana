"""The inference adapter and the configuration assertions that guard it.

The assertion that matters: a clinic deployment cannot boot in a configuration
that sends patient utterances off the machine. It is tested here because ADR
0007 requires it to be a startup assertion with a test rather than a convention.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from spine.inference.adapter import (
    CLINICAL_TEMPERATURE,
    MAX_TEMPERATURE,
    Completion,
    InferenceProvider,
    ModelSpec,
    StructuredOutputError,
    Transport,
    complete_structured,
)
from spine.inference.config import (
    InferenceConfig,
    Mode,
    UnsafeConfigurationError,
    assert_transport_is_permitted,
    build_provider,
    model_spec,
)
from spine.inference.ollama import DEFAULT_HOST, OllamaProvider


class Answer(BaseModel):
    band: str
    reason: str


class ScriptedProvider(InferenceProvider):
    """Returns prepared responses in order, recording how many times it was called."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.prompts: list[str] = []
        self.systems: list[str] = []

    @property
    def transport(self) -> Transport:
        return Transport.LOCAL

    def is_available(self) -> bool:
        return True

    def complete(
        self, *, prompt: str, system: str, spec: ModelSpec, prompt_version: str
    ) -> Completion:
        self.calls += 1
        self.prompts.append(prompt)
        self.systems.append(system)
        return Completion(
            text=self.responses.pop(0),
            model_version=spec.name,
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
        )


def config(mode: str = "development", transport: str = "local") -> InferenceConfig:
    return InferenceConfig(
        mode=Mode(mode),
        transport=Transport(transport),
        ollama_host=DEFAULT_HOST,
        primary_model="llama3.1:8b",
        fallback_models=(),
    )


SPEC = ModelSpec(name="test-model")


class TestProductionSafety:
    """ADR 0007. A clinic deployment cannot leak because it cannot boot."""

    def test_production_refuses_hosted_transport(self) -> None:
        with pytest.raises(UnsafeConfigurationError, match="off this machine"):
            assert_transport_is_permitted(config("production", "hosted"))

    def test_production_permits_local_transport(self) -> None:
        assert_transport_is_permitted(config("production", "local"))

    def test_development_permits_hosted_transport(self) -> None:
        assert_transport_is_permitted(config("development", "hosted"))

    def test_the_refusal_names_both_variables_and_the_fix(self) -> None:
        with pytest.raises(UnsafeConfigurationError) as caught:
            assert_transport_is_permitted(config("production", "hosted"))
        message = str(caught.value)
        assert "NIDANA_MODE" in message
        assert "NIDANA_INFERENCE_TRANSPORT" in message

    def test_build_provider_asserts_before_constructing(self) -> None:
        with pytest.raises(UnsafeConfigurationError, match="off this machine"):
            build_provider(config("production", "hosted"))

    def test_no_hosted_provider_exists_even_in_development(self) -> None:
        with pytest.raises(UnsafeConfigurationError, match="local inference only"):
            build_provider(config("development", "hosted"))

    def test_local_transport_builds_the_ollama_provider(self) -> None:
        assert isinstance(build_provider(config("production", "local")), OllamaProvider)


class TestConfigFromEnvironment:
    def test_defaults_are_development_and_local(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("NIDANA_MODE", "NIDANA_INFERENCE_TRANSPORT", "NIDANA_MODEL_FALLBACKS"):
            monkeypatch.delenv(name, raising=False)
        loaded = InferenceConfig.from_environment()
        assert loaded.mode is Mode.DEVELOPMENT
        assert loaded.transport is Transport.LOCAL

    def test_an_unrecognised_mode_is_refused_not_defaulted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NIDANA_MODE", "staging")
        with pytest.raises(UnsafeConfigurationError, match="refused rather than defaulted"):
            InferenceConfig.from_environment()

    def test_an_unrecognised_transport_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NIDANA_INFERENCE_TRANSPORT", "carrier_pigeon")
        with pytest.raises(UnsafeConfigurationError, match="local"):
            InferenceConfig.from_environment()

    def test_fallbacks_parse_as_a_comma_separated_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NIDANA_MODEL_FALLBACKS", "a:8b, b:7b ,")
        assert InferenceConfig.from_environment().fallback_models == ("a:8b", "b:7b")


class TestModelSpec:
    def test_clinical_temperature_is_zero(self) -> None:
        assert CLINICAL_TEMPERATURE == 0.0
        assert ModelSpec(name="m").temperature == 0.0

    def test_a_nameless_model_is_refused(self) -> None:
        with pytest.raises(ValueError, match="NIDANA_MODEL_PRIMARY"):
            ModelSpec(name="")

    @pytest.mark.parametrize("temperature", [-0.1, MAX_TEMPERATURE + 0.1])
    def test_temperature_outside_the_range_is_refused(self, temperature: float) -> None:
        with pytest.raises(ValueError, match="outside"):
            ModelSpec(name="m", temperature=temperature)

    def test_an_unset_primary_model_is_named_in_the_error(self) -> None:
        empty = InferenceConfig(
            mode=Mode.DEVELOPMENT,
            transport=Transport.LOCAL,
            ollama_host=DEFAULT_HOST,
            primary_model="",
            fallback_models=(),
        )
        with pytest.raises(UnsafeConfigurationError, match="ollama pull"):
            model_spec(empty)


class TestStructuredOutput:
    """Enforced, not requested. One retry, then loud failure."""

    def test_valid_output_returns_on_the_first_call(self) -> None:
        provider = ScriptedProvider('{"band":"U2","reason":"stated"}')
        result = complete_structured(
            provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
        )
        assert result.band == "U2"
        assert provider.calls == 1

    def test_malformed_output_is_retried_once(self) -> None:
        provider = ScriptedProvider("not json", '{"band":"U1","reason":"stated"}')
        result = complete_structured(
            provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
        )
        assert result.band == "U1"
        assert provider.calls == 2

    def test_the_retry_carries_the_validation_error_back(self) -> None:
        provider = ScriptedProvider("not json", '{"band":"U1","reason":"stated"}')
        complete_structured(
            provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
        )
        assert "did not match the required schema" in provider.prompts[1]
        assert "not json" in provider.prompts[1]

    def test_two_failures_raise_rather_than_retrying_again(self) -> None:
        provider = ScriptedProvider("bad", "still bad")
        with pytest.raises(StructuredOutputError):
            complete_structured(
                provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
            )
        assert provider.calls == 2

    def test_the_failure_says_to_fix_the_prompt(self) -> None:
        provider = ScriptedProvider("bad", "still bad")
        with pytest.raises(StructuredOutputError, match="fix the"):
            complete_structured(
                provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
            )

    def test_output_missing_a_required_field_is_a_failure(self) -> None:
        provider = ScriptedProvider('{"band":"U2"}', '{"band":"U2"}')
        with pytest.raises(StructuredOutputError):
            complete_structured(
                provider, Answer, prompt="p", system="s", spec=SPEC, prompt_version="1.0"
            )


class TestOllamaProvider:
    def test_it_reports_the_local_transport(self) -> None:
        assert OllamaProvider().transport is Transport.LOCAL

    def test_a_trailing_slash_in_the_host_is_tolerated(self) -> None:
        assert OllamaProvider(host="http://localhost:11434/")._host == "http://localhost:11434"

    def test_availability_is_false_when_nothing_is_listening(self) -> None:
        assert OllamaProvider(host="http://127.0.0.1:1", timeout=0.5).is_available() is False
