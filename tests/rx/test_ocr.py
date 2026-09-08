"""Reading a prescription image.

Tesseract is not installed here, and none of this needs it. What is tested is
the parsing of its output and the refusals around it, both of which are where
the failures that reach a pharmacist actually live.

The one that matters most: an image too poor to read must say so rather than
producing lines the reading agent will faithfully transcribe and nobody can
trust. Retaking a photograph is cheap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.rx.ocr.reader import (
    LOW_CONFIDENCE_FLOOR,
    OcrError,
    OcrResult,
    OcrWord,
    TesseractReader,
    words_from,
)


def data(*rows: tuple[str, float, int]) -> dict[str, list[object]]:
    """Tesseract's column-oriented output, as image_to_data returns it."""
    return {
        "text": [text for text, _, _ in rows],
        "conf": [confidence for _, confidence, _ in rows],
        "line_num": [line for _, _, line in rows],
    }


def result(*words: OcrWord) -> OcrResult:
    mean = sum(w.confidence for w in words) / len(words) if words else 0.0
    return OcrResult(words=words, engine_version="test", mean_confidence=mean)


class TestWordParsing:
    def test_words_are_read_with_their_confidence(self) -> None:
        words = words_from(data(("Crocin", 92.0, 1)))
        assert words[0].text == "Crocin"
        assert words[0].confidence == pytest.approx(0.92)

    def test_blank_text_is_dropped(self) -> None:
        """Tesseract emits empty strings for layout gaps."""
        assert words_from(data(("", 95.0, 1), ("   ", 90.0, 1))) == ()

    def test_an_unscored_word_is_dropped(self) -> None:
        """Tesseract reports -1 for words it did not score.

        Kept, it would land at -100% and drag the mean below the usability
        floor on its own, condemning a readable image.
        """
        assert words_from(data(("Crocin", -1.0, 1))) == ()

    def test_the_line_number_is_carried(self) -> None:
        """Lines are how a prescription separates one drug from the next."""
        words = words_from(data(("Crocin", 90.0, 1), ("Dolo", 88.0, 2)))
        assert [word.line_number for word in words] == [1, 2]

    def test_a_malformed_confidence_is_skipped_not_fatal(self) -> None:
        raw = data(("Crocin", 90.0, 1))
        raw["conf"] = ["not a number"]
        assert words_from(raw) == ()

    def test_empty_output_produces_no_words(self) -> None:
        assert words_from({"text": [], "conf": [], "line_num": []}) == ()


class TestTextAssembly:
    def test_words_join_into_lines(self) -> None:
        built = result(
            OcrWord("Tab", 0.9, 1), OcrWord("Crocin", 0.9, 1), OcrWord("Dolo", 0.9, 2)
        )
        assert built.text == "Tab Crocin\nDolo"

    def test_lines_are_ordered_by_number_not_arrival(self) -> None:
        built = result(OcrWord("second", 0.9, 2), OcrWord("first", 0.9, 1))
        assert built.text == "first\nsecond"

    def test_no_words_is_empty_text(self) -> None:
        assert result().text == ""


class TestConfidence:
    def test_a_poor_word_is_flagged(self) -> None:
        assert OcrWord("smudge", LOW_CONFIDENCE_FLOOR - 0.1, 1).is_low_confidence

    def test_a_clear_word_is_not(self) -> None:
        assert not OcrWord("Crocin", 0.95, 1).is_low_confidence

    def test_poor_words_are_listed(self) -> None:
        built = result(OcrWord("Crocin", 0.95, 1), OcrWord("smudge", 0.2, 1))
        assert len(built.low_confidence_words) == 1

    def test_a_poor_image_says_it_should_be_retaken(self) -> None:
        """Lines nobody can trust are worse than an honest refusal."""
        assert result(OcrWord("smudge", 0.2, 1)).is_probably_unusable

    def test_a_good_image_is_usable(self) -> None:
        assert not result(OcrWord("Crocin", 0.95, 1)).is_probably_unusable

    def test_an_empty_reading_is_unusable(self) -> None:
        assert result().is_probably_unusable


class TestRefusals:
    def test_a_missing_image_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(OcrError, match="no image at"):
            TesseractReader().read(tmp_path / "absent.png")

    def test_an_unsupported_format_lists_the_alternatives(self, tmp_path: Path) -> None:
        path = tmp_path / "prescription.pdf"
        path.write_bytes(b"%PDF")
        with pytest.raises(OcrError, match="readable image format"):
            TesseractReader().read(path)

    def test_a_missing_engine_names_the_install_command(self, tmp_path: Path) -> None:
        """A deployment without Tesseract should be told how to get it."""
        path = tmp_path / "prescription.png"
        path.write_bytes(b"\x89PNG")
        reader = TesseractReader(binary=tmp_path / "no-such-tesseract")
        if reader.is_available():
            pytest.skip("Tesseract is installed here; the refusal cannot be exercised")
        with pytest.raises(OcrError, match="tesseract-ocr"):
            reader.read(path)

    def test_availability_is_false_without_the_binary(self, tmp_path: Path) -> None:
        assert not TesseractReader(binary=tmp_path / "absent").is_available()

    def test_the_engine_version_is_reported_even_when_unavailable(
        self, tmp_path: Path
    ) -> None:
        """Version is metadata; failing to read it must not fail a reading."""
        assert TesseractReader(binary=tmp_path / "absent").engine_version.startswith(
            "tesseract-"
        )
