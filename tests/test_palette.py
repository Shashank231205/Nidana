"""The urgency palette must stay legible.

Colour in this product is not decoration: it marks how urgently someone needs
care. A band that fails contrast is a band somebody misreads on a clinic tablet
in daylight.

Parsed from web/src/styles/tokens.css rather than duplicated here, so the test
fails when the stylesheet changes and not when a copy of it drifts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STYLES = Path(__file__).resolve().parents[1] / "web" / "src" / "styles"
TOKENS = STYLES / "tokens.css"
BASE = STYLES / "base.css"

AA_NORMAL = 4.5
"""WCAG 2.1 minimum for normal-weight body text."""


def _channels(colour: str) -> tuple[float, float, float]:
    value = colour.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    red, green, blue = (_linear(c) for c in _channels(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    first, second = luminance(one), luminance(other)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;", text))


BANDS = ("u1", "u2", "u3", "u4", "u5")


class TestUrgencyBands:
    @pytest.mark.parametrize("band", BANDS)
    def test_a_band_is_legible_as_text_on_the_page(self, band: str) -> None:
        palette = tokens()
        assert contrast(palette[band], palette["page"]) >= AA_NORMAL

    @pytest.mark.parametrize("band", BANDS)
    def test_a_band_is_legible_as_a_fill(self, band: str) -> None:
        """The band as a background, with --on-urgency written over it."""
        palette = tokens()
        assert contrast(palette["on-urgency"], palette[band]) >= AA_NORMAL

    def test_every_band_is_defined(self) -> None:
        palette = tokens()
        assert all(band in palette for band in BANDS)

    def test_no_two_bands_share_a_colour(self) -> None:
        """Two bands the same colour is two urgencies that look identical."""
        palette = tokens()
        used = [palette[band] for band in BANDS]
        assert len(set(used)) == len(used)


class TestInk:
    @pytest.mark.parametrize("shade", ["ink", "ink-2", "ink-3"])
    def test_every_ink_shade_is_legible_on_the_page(self, shade: str) -> None:
        """--ink-3 is the meta shade and was the one that failed, at 3.20:1."""
        palette = tokens()
        assert contrast(palette[shade], palette["page"]) >= AA_NORMAL

    @pytest.mark.parametrize("shade", ["ink", "ink-2", "ink-3"])
    def test_every_ink_shade_is_legible_on_a_surface(self, shade: str) -> None:
        palette = tokens()
        assert contrast(palette[shade], palette["surface"]) >= AA_NORMAL


class TestNoAccent:
    def test_the_urgency_palette_is_not_reused_elsewhere(self) -> None:
        """A button in --u1 is a button a patient reads as an emergency.

        Checked by value rather than by name: a token that merely copies the
        hex of a band defeats the rule while looking like it obeys it.
        """
        palette = tokens()
        band_values = {palette[band] for band in BANDS}
        reused = {
            name: value
            for name, value in palette.items()
            if value in band_values and name not in BANDS
        }
        assert reused == {}


class TestAccessibilityFloor:
    """Unannounced, and therefore easy to delete without noticing.

    Each of these is a rule a keyboard or screen-reader user depends on and
    nobody else sees. A CSS regression removing one is silent.
    """

    def test_keyboard_focus_is_visible(self) -> None:
        assert ":focus-visible" in BASE.read_text(encoding="utf-8")

    def test_reduced_motion_is_respected(self) -> None:
        assert "prefers-reduced-motion" in BASE.read_text(encoding="utf-8")

    def test_a_visually_hidden_class_exists_for_labels(self) -> None:
        """Fields whose visible label would be redundant still need one."""
        assert ".visually-hidden" in BASE.read_text(encoding="utf-8")
