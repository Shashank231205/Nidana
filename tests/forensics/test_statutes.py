"""Reading an archived citation across the IPC-to-BNS renumbering.

Two things are tested. That the transcription is faithful to the published
table — spot-checked against the sections a wound certificate actually cites —
and that the module refuses to be more useful than it is: it translates a
number and never classifies an injury.

The merge case matters most. The BNS folded IPC 376DA and 376DB into BNS
70(2), so the reverse lookup is not one-to-one, and a function returning the
first match would silently drop a provision from an archived report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.forensics.clinical.statutes import (
    BNS_COMMENCEMENT,
    Correspondence,
    StatuteMap,
    StatuteMapError,
    load_statute_map,
    statute_map,
)


class TestTranscription:
    """Spot checks against the published correspondence table."""

    def test_hurt_maps_to_its_bns_section(self) -> None:
        found = statute_map().from_ipc("319")
        assert found is not None
        assert found.bns == "114"
        assert found.title == "Hurt"

    def test_grievous_hurt_maps_and_is_flagged_as_changed(self) -> None:
        """The provision a wound certificate turns on.

        The table marks it changed, not merely renumbered, so the clinical
        inputs to the test may differ from the IPC wording.
        """
        found = statute_map().from_ipc("320")
        assert found is not None
        assert found.bns == "116"
        assert found.changed
        assert found.needs_legal_check

    def test_acid_attack_maps_to_its_subsection(self) -> None:
        found = statute_map().from_ipc("326A")
        assert found is not None
        assert found.bns == "124(1)"

    def test_causing_death_by_negligence_maps(self) -> None:
        found = statute_map().from_ipc("304A")
        assert found is not None
        assert found.bns == "106"

    def test_dowry_death_maps(self) -> None:
        found = statute_map().from_ipc("304B")
        assert found is not None
        assert found.bns == "80"

    def test_causing_miscarriage_maps(self) -> None:
        found = statute_map().from_ipc("312")
        assert found is not None
        assert found.bns == "88"

    def test_an_unlisted_section_is_not_invented(self) -> None:
        """The table covers the medico-legal sections, not all 511.

        Returning None is correct; returning a guess would point a court at a
        provision nobody transcribed.
        """
        assert statute_map().from_ipc("420") is None


class TestSectionNumberFormatting:
    def test_case_is_ignored(self) -> None:
        assert statute_map().from_ipc("326a") == statute_map().from_ipc("326A")

    def test_internal_spacing_is_ignored(self) -> None:
        """A report typed by hand contains '376 DA'."""
        assert statute_map().from_ipc("376 DA") == statute_map().from_ipc("376DA")


class TestTheMergeIsNotHidden:
    def test_both_merged_sections_map_forward(self) -> None:
        for ipc in ("376DA", "376DB"):
            found = statute_map().from_ipc(ipc)
            assert found is not None
            assert found.bns == "70(2)"

    def test_the_reverse_lookup_returns_both(self) -> None:
        """BNS 70(2) came from two IPC sections.

        Returning one would drop the other from an archived report.
        """
        found = statute_map().from_bns("70(2)")
        assert {entry.ipc for entry in found} == {"376DA", "376DB"}

    def test_a_reverse_lookup_of_an_unmerged_section_returns_one(self) -> None:
        assert len(statute_map().from_bns("114")) == 1

    def test_an_unknown_bns_section_returns_nothing(self) -> None:
        assert statute_map().from_bns("999") == ()


class TestRepealedSections:
    def test_a_repealed_section_is_found_with_no_counterpart(self) -> None:
        """Saying 'this was deleted' beats returning nothing.

        A report citing IPC 377 cites a provision that no longer exists, and
        the reader needs to know that rather than assume a lookup failure.
        """
        found = statute_map().from_ipc("377")
        assert found is not None
        assert found.bns is None
        assert found.repealed
        assert found.needs_legal_check

    def test_repealed_sections_are_listed(self) -> None:
        assert "377" in {entry.ipc for entry in statute_map().repealed}


class TestTheCaveatTravels:
    def test_no_entry_claims_legal_review(self) -> None:
        """The transcription is faithful; it is not advice.

        Every result carries this rather than the file documenting it once,
        because a caller rendering a citation into a report needs the caveat
        at the point of use.
        """
        assert not any(e.legally_reviewed for e in statute_map().repealed)
        for section in ("319", "320", "376DA", "377"):
            found = statute_map().from_ipc(section)
            assert found is not None
            assert not found.legally_reviewed

    def test_the_commencement_date_is_recorded(self) -> None:
        """A stored citation is ambiguous without the report's date."""
        assert BNS_COMMENCEMENT == "2024-07-01"


class TestLoading:
    def test_a_missing_table_says_the_install_is_incomplete(self, tmp_path: Path) -> None:
        with pytest.raises(StatuteMapError, match="installation is incomplete"):
            load_statute_map(tmp_path / "absent.yaml")

    def test_malformed_yaml_is_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("sections: [unclosed", encoding="utf-8")
        with pytest.raises(StatuteMapError, match="not valid YAML"):
            load_statute_map(path)

    def test_a_non_mapping_document_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- one\n- two\n", encoding="utf-8")
        with pytest.raises(StatuteMapError, match="does not contain a mapping"):
            load_statute_map(path)

    def test_an_empty_table_is_refused(self, tmp_path: Path) -> None:
        """A silently empty map makes every citation look unrecognised."""
        path = tmp_path / "empty.yaml"
        path.write_text("name: nothing\nsections: []\n", encoding="utf-8")
        with pytest.raises(StatuteMapError, match="lists no sections"):
            load_statute_map(path)

    def test_a_duplicated_ipc_section_is_refused(self) -> None:
        with pytest.raises(StatuteMapError, match="appears twice"):
            StatuteMap(
                (
                    Correspondence(ipc="319", bns="114", title="Hurt"),
                    Correspondence(ipc="319", bns="115", title="Hurt again"),
                )
            )

    def test_the_shipped_table_loads(self) -> None:
        assert len(statute_map()) > 30
