"""Reading a prescription image into text.

OCR is local in every mode, for the same reason transcription is: a photograph
of a prescription carries the patient's name, the prescriber's name and the
clinic's address, and no configuration flag creates a hosted path.

What this layer does not do is decide anything. It produces text and per-word
confidence; the reading agent separates that text into lines and the brand
index resolves them. A three-stage pipeline rather than one, because each stage
has a different failure and a different remedy: an unreadable image is retaken,
an unreadable line is confirmed by the pharmacist, and an unresolved brand is
looked up.

Handwritten Indian prescriptions are the hard case and this will often fail on
them. That is expected and is why `legible` exists on every line: a line the
OCR could not read is recorded as unreadable rather than dropped, and a
pharmacist reads it from the original.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOW_CONFIDENCE_FLOOR: Final[float] = 0.55
"""Below this a word is marked uncertain.

Lower than the ASR floor deliberately. Handwriting scores worse than speech on
every engine, and a floor tuned for audio would mark most of a real
prescription uncertain, which tells a pharmacist nothing they did not know.
"""

SUPPORTED_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)


class OcrError(RuntimeError):
    """Raised when an image cannot be read."""


@dataclass(frozen=True)
class OcrWord:
    """One word the engine found, and how sure it was."""

    text: str
    confidence: float
    line_number: int

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < LOW_CONFIDENCE_FLOOR


@dataclass(frozen=True)
class OcrResult:
    """What the engine produced for one image.

    `text` is what the reading agent receives and what its spans are checked
    against, so it is assembled from the words rather than taken from a second
    call to the engine. Two calls could disagree, and a span checked against
    text the agent never saw would fail for the wrong reason.
    """

    words: tuple[OcrWord, ...]
    engine_version: str
    mean_confidence: float

    @property
    def text(self) -> str:
        lines: dict[int, list[str]] = {}
        for word in self.words:
            lines.setdefault(word.line_number, []).append(word.text)
        return "\n".join(" ".join(lines[key]) for key in sorted(lines))

    @property
    def low_confidence_words(self) -> tuple[OcrWord, ...]:
        return tuple(word for word in self.words if word.is_low_confidence)

    @property
    def is_probably_unusable(self) -> bool:
        """Whether this image should be retaken rather than processed.

        A prescription read at 30% mean confidence produces lines the agent
        will faithfully transcribe and the pharmacist cannot trust. Retaking
        the photograph is cheap; reconstructing a wrong medication list from
        the record later is not.
        """
        return not self.words or self.mean_confidence < LOW_CONFIDENCE_FLOOR


class OcrReader(ABC):
    """What every OCR backend must do."""

    @property
    @abstractmethod
    def engine_version(self) -> str:
        """Recorded with the result, so a reading is reproducible."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the engine is installed and callable.

        Checked at startup so a deployment missing Tesseract fails there rather
        than at the first prescription.
        """

    @abstractmethod
    def read(self, image_path: Path) -> OcrResult:
        """Read one image."""


class TesseractReader(OcrReader):
    """Tesseract, run locally.

    Chosen because it installs offline from a distribution package, runs on
    CPU, and ships Devanagari and Tamil traineddata — a prescription's printed
    letterhead is routinely not in Latin script even when the drug names are.

    It is weak on cursive handwriting. That is a property of the problem rather
    than of this choice, and the pipeline is built to surface a bad reading
    instead of hiding it.
    """

    def __init__(self, *, languages: str = "eng", binary: Path | None = None) -> None:
        self._languages = languages
        self._binary = binary

    @property
    def engine_version(self) -> str:
        try:
            import pytesseract  # noqa: PLC0415

            return f"tesseract-{pytesseract.get_tesseract_version()}"
        except Exception:
            # Version is metadata; failing to read it must not fail a reading.
            return "tesseract-unknown"

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: PLC0415

            if self._binary is not None:
                pytesseract.pytesseract.tesseract_cmd = str(self._binary)
            pytesseract.get_tesseract_version()
        except Exception:
            return False
        return True

    def read(self, image_path: Path) -> OcrResult:
        """Read a prescription image.

        Refuses before touching the engine where it can: a missing file and an
        unsupported format are the caller's bugs, and an error naming them is
        more useful than whatever the engine says about them.
        """
        if not image_path.is_file():
            raise OcrError(
                f"no image at {image_path}; the upload was not written or the path "
                f"is wrong"
            )
        if image_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise OcrError(
                f"{image_path.suffix!r} is not a readable image format; use one of "
                f"{', '.join(sorted(SUPPORTED_SUFFIXES))}"
            )
        if not self.is_available():
            raise OcrError(
                "Tesseract is not installed or not on PATH. Install it from your "
                "distribution ('apt install tesseract-ocr' or the Windows installer) "
                "and install the python extra with 'pip install -e .[ocr]'"
            )

        try:
            import pytesseract  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415

            if self._binary is not None:
                pytesseract.pytesseract.tesseract_cmd = str(self._binary)
            with Image.open(image_path) as image:
                data = pytesseract.image_to_data(
                    image,
                    lang=self._languages,
                    output_type=pytesseract.Output.DICT,
                )
        except OcrError:
            raise
        except Exception as error:
            raise OcrError(
                f"could not read {image_path}: {error}. The file may be corrupt, or "
                f"the language pack {self._languages!r} may not be installed"
            ) from error

        words = words_from(data)
        return OcrResult(
            words=words,
            engine_version=self.engine_version,
            mean_confidence=_mean_confidence(words),
        )


def words_from(data: Mapping[str, Sequence[object]]) -> tuple[OcrWord, ...]:
    """Turn Tesseract's column-oriented output into words.

    Tesseract reports -1 for words it did not score, and blank strings for
    layout gaps. Both are dropped: a word with no text is not a word, and an
    unscored one would otherwise land at -1% and drag the mean below the
    usability floor on its own.

    Pure, so the parsing is testable without the engine installed.
    """
    texts = data.get("text", [])
    confidences = data.get("conf", [])
    lines = data.get("line_num", [])
    words: list[OcrWord] = []
    for position, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue
        try:
            confidence = float(str(confidences[position]))
        except (IndexError, TypeError, ValueError):
            continue
        if confidence < 0:
            continue
        line_number = int(str(lines[position])) if position < len(lines) else 0
        words.append(
            OcrWord(text=text, confidence=confidence / 100.0, line_number=line_number)
        )
    return tuple(words)


def _mean_confidence(words: tuple[OcrWord, ...]) -> float:
    if not words:
        return 0.0
    return sum(word.confidence for word in words) / len(words)
