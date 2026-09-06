"""Local inference via Ollama.

The production path and, for now, the only one. Patient utterances never leave
the machine.

Ollama is reached over HTTP on localhost. That is a loopback call, not network
egress: nothing crosses the premises boundary, which is what the on-premise
requirement is about.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Final

from spine.inference.adapter import (
    Completion,
    InferenceError,
    InferenceProvider,
    ModelSpec,
    Transport,
)

DEFAULT_HOST: Final[str] = "http://localhost:11434"
HTTP_OK_RANGE: Final[range] = range(200, 300)
REQUEST_TIMEOUT_SECONDS: Final[float] = 120.0
"""Generous, because a quantised model on a cold CPU is slow on first load.

The per-turn latency budget is a product requirement measured in eval, not a
transport timeout. Cutting a call off here would fail a turn that was merely
slow.
"""


class OllamaProvider(InferenceProvider):
    """Talks to a local Ollama daemon.

    Uses urllib rather than a client library, so the inference path carries no
    dependency that could phone home.
    """

    def __init__(self, host: str = DEFAULT_HOST, timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        self._host = host.rstrip("/")
        self._timeout = timeout

    @property
    def transport(self) -> Transport:
        return Transport.LOCAL

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self._host}/api/tags", timeout=5.0) as response:
                return response.status in HTTP_OK_RANGE
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def installed_models(self) -> tuple[str, ...]:
        """Model names the daemon has pulled.

        Used at startup to fail with a useful message rather than at the first
        turn with a 404.
        """
        try:
            with urllib.request.urlopen(f"{self._host}/api/tags", timeout=5.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as error:
            raise InferenceError(
                f"cannot reach Ollama at {self._host}: {error}. Start it with 'ollama "
                f"serve', or set NIDANA_OLLAMA_HOST to where it is running"
            ) from error
        models = payload.get("models", [])
        return tuple(str(entry.get("name", "")) for entry in models if entry.get("name"))

    def complete(
        self, *, prompt: str, system: str, spec: ModelSpec, prompt_version: str
    ) -> Completion:
        attempted: list[str] = []
        last_error: Exception | None = None
        for candidate in (spec.name, *spec.fallbacks):
            attempted.append(candidate)
            try:
                return self._generate(
                    model=candidate,
                    prompt=prompt,
                    system=system,
                    spec=spec,
                    prompt_version=prompt_version,
                    used_fallback=candidate != spec.name,
                )
            except InferenceError as error:
                last_error = error
        raise InferenceError(
            f"every model failed: tried {', '.join(attempted)}. Last error: {last_error}. "
            f"Check 'ollama list' shows the model, and pull it if not"
        )

    def _generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str,
        spec: ModelSpec,
        prompt_version: str,
        used_fallback: bool,
    ) -> Completion:
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": spec.temperature,
                    "num_predict": spec.max_output_tokens,
                    **({"num_ctx": spec.context_window} if spec.context_window else {}),
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise InferenceError(
                f"Ollama rejected the call to {model}: HTTP {error.code}. If this is 404, "
                f"run 'ollama pull {model}'"
            ) from error
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
            raise InferenceError(f"Ollama call to {model} failed: {error}") from error

        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise InferenceError(
                f"{model} returned no text. The model may be loaded but unable to answer "
                f"within num_predict={spec.max_output_tokens}"
            )
        return Completion(
            text=text,
            model_version=model,
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
            input_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
            latency_ms=int((time.monotonic() - started) * 1000),
            used_fallback=used_fallback,
        )
