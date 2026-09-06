"""Fetch the local models Nidana runs on.

Nothing downloads until this is run. Weights are never committed and never baked
into an image; they live in models/ which .gitignore excludes, and mount as a
volume.

ASR is local in every mode. There is no hosted transcription path.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
MODELS_DIR: Final[Path] = REPO_ROOT / "models"

ASR_MODELS: Final[dict[str, str]] = {
    "indicwhisper": "parthiv11/indic_whisper_nodcil",
    "whisper-small": "openai/whisper-small",
    "whisper-base": "openai/whisper-base",
}
"""ASR options.

indicwhisper is fine-tuned on Indian languages, which is the harder half of the
requirement: drug names and anatomical terms in code-switched speech are the
failure surface. whisper-small is the fallback when it is unavailable or its
licence does not permit the deployment.

Verify the identifier and licence before depending on either. These are pointers
to check, not citations to trust.
"""


def have(command: str) -> bool:
    return shutil.which(command) is not None


def pull_ollama(model: str) -> int:
    if not have("ollama"):
        print(
            "ollama is not on PATH. Install it from https://ollama.com, or run the "
            "compose stack which provides it as a service."
        )
        return 1
    print(f"pulling {model} ...")
    return subprocess.run(["ollama", "pull", model], check=False).returncode


def download_asr(key: str) -> int:
    identifier = ASR_MODELS.get(key)
    if identifier is None:
        print(f"unknown ASR model {key!r}; choose from: {', '.join(ASR_MODELS)}")
        return 1
    # Imported here, not at module scope: huggingface_hub fetches weights once
    # and is not a runtime dependency of the inference path.
    try:
        from huggingface_hub import snapshot_download  # noqa: PLC0415
    except ImportError:
        print(
            "huggingface_hub is not installed. Run: pip install huggingface_hub\n"
            "It is not a runtime dependency; it is only needed to fetch weights once."
        )
        return 1
    target = MODELS_DIR / "asr" / key
    target.mkdir(parents=True, exist_ok=True)
    print(f"downloading {identifier} to {target} ...")
    snapshot_download(repo_id=identifier, local_dir=str(target))
    print(f"done. Set NIDANA_ASR_MODEL_PATH={target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--llm",
        default="llama3.1:8b-instruct-q4_K_M",
        help="Ollama model for intake, structuring, and triage. Quantised by default, "
        "because the target hardware is a laptop.",
    )
    parser.add_argument(
        "--asr",
        choices=sorted(ASR_MODELS),
        default="indicwhisper",
        help="ASR model. indicwhisper handles Indian languages; whisper-small is smaller.",
    )
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-asr", action="store_true")
    arguments = parser.parse_args()

    failures = 0
    if not arguments.skip_llm:
        failures += 1 if pull_ollama(arguments.llm) else 0
    if not arguments.skip_asr:
        failures += 1 if download_asr(arguments.asr) else 0

    if failures:
        print(f"\n{failures} step(s) failed.")
        return 1
    print("\nModels ready. Set NIDANA_MODEL_PRIMARY to the model you pulled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
