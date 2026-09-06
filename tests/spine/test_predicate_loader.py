"""Predicate loading and resolution.

ADR 0005. The defect this exists to catch: a rule atom naming a field no
registry declares evaluates false forever, disabling every rule that references
it while its negative tests continue to pass. It is invisible to every other
gate, so it must fail at load time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spine.rules.predicate_loader import (
    PredicateLoadError,
    check_enum_operands,
    load_predicates,
    predicates_dir,
    resolve_against_registries,
)
from spine.rules.registry_loader import fields_dir, load_all, load_family
from spine.schemas.predicate import Comparator
from spine.schemas.registry import ComplaintFamily, FamilyRegistry

Registries = dict[ComplaintFamily, FamilyRegistry]

REGISTRY = """
family: chest_pain
required:
  - field: radiation
    type: enum
    values: [none, jaw, left_arm]
    multi: true
  - field: diaphoresis
    type: boolean
"""

VALID_PREDICATES = """
predicates:
  - id: diaphoresis_present
    field: diaphoresis
    comparator: is_true
  - id: radiates_to_jaw
    field: radiation
    comparator: in
    values: [jaw, left_arm]
"""


@pytest.fixture
def registries(tmp_path: Path) -> Registries:
    directory = tmp_path / "fields"
    directory.mkdir()
    (directory / "chest_pain.yaml").write_text(REGISTRY, encoding="utf-8")
    return {ComplaintFamily.CHEST_PAIN: load_family(ComplaintFamily.CHEST_PAIN, directory)}


@pytest.fixture
def predicate_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "predicates"
    directory.mkdir()
    return directory


def write(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


class TestLoading:
    def test_loads_valid_predicates(self, predicate_dir: Path) -> None:
        write(predicate_dir, "cardiac.yaml", VALID_PREDICATES)
        loaded = load_predicates(predicate_dir)
        assert set(loaded) == {"diaphoresis_present", "radiates_to_jaw"}
        assert loaded["radiates_to_jaw"].comparator is Comparator.IN

    def test_loads_across_multiple_files(self, predicate_dir: Path) -> None:
        write(predicate_dir, "a.yaml", VALID_PREDICATES)
        write(
            predicate_dir,
            "b.yaml",
            "predicates:\n  - id: other\n    field: diaphoresis\n    comparator: is_false\n",
        )
        assert len(load_predicates(predicate_dir)) == 3

    def test_duplicate_id_across_files_names_both(self, predicate_dir: Path) -> None:
        write(predicate_dir, "a.yaml", VALID_PREDICATES)
        write(predicate_dir, "b.yaml", VALID_PREDICATES)
        with pytest.raises(PredicateLoadError, match="exactly one definition"):
            load_predicates(predicate_dir)

    def test_missing_directory_names_itself(self, tmp_path: Path) -> None:
        with pytest.raises(PredicateLoadError, match="does not exist"):
            load_predicates(tmp_path / "absent")

    def test_empty_directory_is_rejected(self, predicate_dir: Path) -> None:
        with pytest.raises(PredicateLoadError, match="no predicate files"):
            load_predicates(predicate_dir)

    def test_malformed_yaml_names_the_file(self, predicate_dir: Path) -> None:
        write(predicate_dir, "bad.yaml", "predicates: [unclosed")
        with pytest.raises(PredicateLoadError, match="not valid YAML"):
            load_predicates(predicate_dir)

    def test_a_file_without_a_predicates_key_is_rejected(self, predicate_dir: Path) -> None:
        write(predicate_dir, "bad.yaml", "rules:\n  - id: x\n")
        with pytest.raises(PredicateLoadError, match="top-level 'predicates' list"):
            load_predicates(predicate_dir)

    def test_an_empty_predicates_list_is_rejected(self, predicate_dir: Path) -> None:
        write(predicate_dir, "bad.yaml", "predicates: []\n")
        with pytest.raises(PredicateLoadError, match="declares no predicates"):
            load_predicates(predicate_dir)

    def test_an_invalid_predicate_names_the_file(self, predicate_dir: Path) -> None:
        write(
            predicate_dir,
            "bad.yaml",
            "predicates:\n  - id: x\n    field: f\n    comparator: in\n",
        )
        with pytest.raises(PredicateLoadError, match="invalid predicate"):
            load_predicates(predicate_dir)


class TestFieldResolution:
    """The ADR 0005 guard."""

    def test_resolved_predicates_pass(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(predicate_dir, "ok.yaml", VALID_PREDICATES)
        resolve_against_registries(load_predicates(predicate_dir), registries)

    def test_an_unresolved_atom_fails_the_load(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "typo.yaml",
            "predicates:\n"
            "  - id: acs_atom\n"
            "    field: radiation_to_jaw_or_left_arm\n"
            "    comparator: is_true\n",
        )
        with pytest.raises(PredicateLoadError, match="false forever"):
            resolve_against_registries(load_predicates(predicate_dir), registries)

    def test_the_error_names_the_predicate_and_the_field(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "typo.yaml",
            "predicates:\n  - id: acs_atom\n    field: no_such_field\n    comparator: is_true\n",
        )
        with pytest.raises(PredicateLoadError) as caught:
            resolve_against_registries(load_predicates(predicate_dir), registries)
        message = str(caught.value)
        assert "acs_atom" in message
        assert "no_such_field" in message

    def test_every_unresolved_atom_is_reported_at_once(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "typos.yaml",
            "predicates:\n"
            "  - id: first\n    field: bogus_one\n    comparator: is_true\n"
            "  - id: second\n    field: bogus_two\n    comparator: is_true\n",
        )
        with pytest.raises(PredicateLoadError) as caught:
            resolve_against_registries(load_predicates(predicate_dir), registries)
        message = str(caught.value)
        assert "bogus_one" in message
        assert "bogus_two" in message
        assert "2 predicate(s)" in message

    def test_demographic_fields_resolve_without_a_registry_entry(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "demo.yaml",
            "predicates:\n"
            "  - id: age_over_40\n    field: age_years\n"
            "    comparator: greater_than\n    value: 40\n"
            "  - id: female\n    field: sex\n    comparator: equals\n    value: female\n"
            "  - id: pregnant\n    field: pregnancy_status\n    comparator: equals\n"
            "    value: confirmed\n"
            "  - id: proxy\n    field: is_proxy\n    comparator: is_true\n",
        )
        resolve_against_registries(load_predicates(predicate_dir), registries)


class TestEnumOperands:
    """A comparison against a value the field cannot hold never fires."""

    def test_valid_enum_operands_pass(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(predicate_dir, "ok.yaml", VALID_PREDICATES)
        check_enum_operands(load_predicates(predicate_dir), registries)

    def test_an_impermissible_enum_value_fails_the_load(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "bad.yaml",
            "predicates:\n  - id: bad\n    field: radiation\n    comparator: equals\n"
            "    value: neck_and_shoulder\n",
        )
        with pytest.raises(PredicateLoadError, match="can never fire"):
            check_enum_operands(load_predicates(predicate_dir), registries)

    def test_the_error_lists_the_permitted_values(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "bad.yaml",
            "predicates:\n  - id: bad\n    field: radiation\n    comparator: in\n"
            "    values: [jaw, elbow]\n",
        )
        with pytest.raises(PredicateLoadError) as caught:
            check_enum_operands(load_predicates(predicate_dir), registries)
        message = str(caught.value)
        assert "elbow" in message
        assert "left_arm" in message
        assert "jaw" in message

    def test_non_enum_fields_are_not_checked(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "num.yaml",
            "predicates:\n  - id: age\n    field: age_years\n    comparator: greater_than\n"
            "    value: 40\n",
        )
        check_enum_operands(load_predicates(predicate_dir), registries)

    def test_operandless_comparators_are_not_checked(
        self, predicate_dir: Path, registries: Registries
    ) -> None:
        write(
            predicate_dir,
            "present.yaml",
            "predicates:\n  - id: any_radiation\n    field: radiation\n"
            "    comparator: is_present\n",
        )
        check_enum_operands(load_predicates(predicate_dir), registries)


class TestShippedRules:
    """The checks that cannot be skipped, run against what actually ships."""

    def test_every_shipped_predicate_resolves(self) -> None:
        resolve_against_registries(load_predicates(), load_all())

    def test_every_shipped_enum_operand_is_permitted(self) -> None:
        check_enum_operands(load_predicates(), load_all())

    def test_predicate_ids_are_unique_across_the_shipped_set(self) -> None:
        assert len(load_predicates()) > 0

    def test_the_shipped_directories_belong_to_consult(self) -> None:
        assert predicates_dir().parent.parent.name == "consult"
        assert fields_dir().parent.parent.name == "consult"
