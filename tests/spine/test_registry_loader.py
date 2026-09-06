"""Loading field registries, and refusing to load a half-configured system.

The failure this guards against: a complaint family with no registry file has
no required fields, so every record for it reports as sufficient while empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spine.rules.registry_loader import (
    RegistryLoadError,
    known_fields,
    load_all,
    load_family,
)
from spine.schemas.registry import ComplaintFamily, FieldType

MINIMAL_FAMILY = """
family: chest_pain
required:
  - field: onset_duration_hours
    type: number
    unit: hours
  - field: radiation
    type: enum
    values: [none, jaw]
    multi: true
optional:
  - field: nausea
    type: boolean
"""


@pytest.fixture
def fields_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "fields"
    directory.mkdir()
    return directory


class TestLoadFamily:
    def test_loads_a_valid_registry(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(MINIMAL_FAMILY, encoding="utf-8")
        registry = load_family(ComplaintFamily.CHEST_PAIN, fields_dir)
        assert registry.family is ComplaintFamily.CHEST_PAIN
        assert registry.required_field_names == ("onset_duration_hours", "radiation")

    def test_spec_for_finds_optional_fields_too(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(MINIMAL_FAMILY, encoding="utf-8")
        registry = load_family(ComplaintFamily.CHEST_PAIN, fields_dir)
        spec = registry.spec_for("nausea")
        assert spec is not None
        assert spec.type is FieldType.BOOLEAN

    def test_missing_file_names_the_path_and_the_remedy(self, fields_dir: Path) -> None:
        with pytest.raises(RegistryLoadError, match=r"chest_pain\.yaml"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)

    def test_malformed_yaml_names_the_file(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text("family: [unclosed", encoding="utf-8")
        with pytest.raises(RegistryLoadError, match="not valid YAML"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)

    def test_a_non_mapping_document_is_rejected(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text("- just\n- a list\n", encoding="utf-8")
        with pytest.raises(RegistryLoadError, match="must contain a mapping"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)

    def test_a_file_declaring_a_different_family_is_rejected(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(
            MINIMAL_FAMILY.replace("family: chest_pain", "family: headache"), encoding="utf-8"
        )
        with pytest.raises(RegistryLoadError, match="rename the file"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)

    def test_an_invalid_field_spec_is_rejected(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(
            "family: chest_pain\nrequired:\n  - field: onset\n    type: number\n", encoding="utf-8"
        )
        with pytest.raises(RegistryLoadError, match="not a valid field registry"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)

    def test_a_field_declared_twice_is_rejected(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(
            "family: chest_pain\n"
            "required:\n"
            "  - field: nausea\n"
            "    type: boolean\n"
            "optional:\n"
            "  - field: nausea\n"
            "    type: boolean\n",
            encoding="utf-8",
        )
        with pytest.raises(RegistryLoadError, match="declared twice"):
            load_family(ComplaintFamily.CHEST_PAIN, fields_dir)


class TestLoadAll:
    def test_refuses_when_a_family_has_no_registry(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(MINIMAL_FAMILY, encoding="utf-8")
        with pytest.raises(RegistryLoadError, match="reports as sufficient while empty"):
            load_all(fields_dir)

    def test_names_every_missing_family_at_once(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(MINIMAL_FAMILY, encoding="utf-8")
        with pytest.raises(RegistryLoadError) as caught:
            load_all(fields_dir)
        message = str(caught.value)
        assert "headache" in message
        assert "trauma" in message
        assert "chest_pain" not in message

    def test_a_missing_directory_names_itself(self, tmp_path: Path) -> None:
        with pytest.raises(RegistryLoadError, match="does not exist"):
            load_all(tmp_path / "absent")

    def test_the_shipped_registries_all_load(self) -> None:
        registries = load_all()
        assert set(registries) == set(ComplaintFamily)

    def test_every_shipped_family_declares_required_fields(self) -> None:
        for family, registry in load_all().items():
            assert registry.required, f"{family.value} declares no required fields"


class TestKnownFields:
    def test_collects_required_and_optional_across_families(self, fields_dir: Path) -> None:
        (fields_dir / "chest_pain.yaml").write_text(MINIMAL_FAMILY, encoding="utf-8")
        loaded = load_family(ComplaintFamily.CHEST_PAIN, fields_dir)
        registries = {ComplaintFamily.CHEST_PAIN: loaded}
        assert known_fields(registries) == frozenset(
            {"onset_duration_hours", "radiation", "nausea"}
        )

    def test_is_empty_for_no_registries(self) -> None:
        assert known_fields({}) == frozenset()
