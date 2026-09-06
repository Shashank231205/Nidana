"""Loading predicates and resolving them against the field registries.

ADR 0005. A predicate naming a field no registry declares is a load failure.
Left unchecked it evaluates false forever, which silently disables every rule
that references it while its negative tests continue to pass.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from spine.rules.predicates import DEMOGRAPHIC_FIELDS
from spine.rules.registry_loader import known_fields, rules_root
from spine.schemas.predicate import Predicate
from spine.schemas.registry import ComplaintFamily, FamilyRegistry, FieldType


def predicates_dir(service: str = "consult") -> Path:
    """The predicate directory belonging to `service`."""
    return rules_root(service) / "predicates"


class PredicateLoadError(RuntimeError):
    """Raised when a predicate file is malformed or references an unknown field."""


def _read_file(path: Path) -> list[object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise PredicateLoadError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(raw, dict) or "predicates" not in raw:
        raise PredicateLoadError(
            f"{path} must contain a top-level 'predicates' list; found "
            f"{sorted(raw) if isinstance(raw, dict) else type(raw).__name__}"
        )
    entries = raw["predicates"]
    if not isinstance(entries, list) or not entries:
        raise PredicateLoadError(f"{path} declares no predicates; remove the file or add some")
    return entries


def load_predicates(directory_override: Path | None = None) -> dict[str, Predicate]:
    """Load every predicate, rejecting duplicate ids across files."""
    directory = directory_override if directory_override is not None else predicates_dir()
    if not directory.is_dir():
        raise PredicateLoadError(
            f"predicate directory {directory} does not exist; it holds the named tests "
            f"that red flag rules reference"
        )
    loaded: dict[str, Predicate] = {}
    origin: dict[str, Path] = {}
    for path in sorted(directory.glob("*.yaml")):
        for entry in _read_file(path):
            try:
                predicate = Predicate.model_validate(entry)
            except ValidationError as error:
                raise PredicateLoadError(f"invalid predicate in {path}: {error}") from error
            if predicate.id in loaded:
                raise PredicateLoadError(
                    f"predicate {predicate.id!r} is defined in both {origin[predicate.id]} "
                    f"and {path}; each atom has exactly one definition"
                )
            loaded[predicate.id] = predicate
            origin[predicate.id] = path
    if not loaded:
        raise PredicateLoadError(f"no predicate files found in {directory}")
    return loaded


def resolve_against_registries(
    predicates: dict[str, Predicate],
    registries: dict[ComplaintFamily, FamilyRegistry],
) -> None:
    """Confirm every predicate names a field some registry declares.

    Raises listing every unresolved predicate at once, rather than one per run.
    """
    declared = known_fields(registries) | DEMOGRAPHIC_FIELDS
    unresolved = sorted(
        f"{p.id} -> {p.field}" for p in predicates.values() if p.field not in declared
    )
    if unresolved:
        raise PredicateLoadError(
            f"{len(unresolved)} predicate(s) reference fields no registry declares: "
            f"{'; '.join(unresolved)}. A predicate over an undeclared field evaluates "
            f"false forever and silently disables every rule using it. Add the field to "
            f"rules/fields/<family>.yaml or correct the predicate"
        )


def check_enum_operands(
    predicates: dict[str, Predicate],
    registries: dict[ComplaintFamily, FamilyRegistry],
) -> None:
    """Confirm enum comparisons use values the field actually permits.

    A predicate testing `radiation == 'neck'` where the registry permits no such
    value never fires. This catches the typo at load time.
    """
    problems: list[str] = []
    for predicate in predicates.values():
        operands = [*predicate.values] if predicate.values else (
            [predicate.value] if predicate.value is not None else []
        )
        if not operands:
            continue
        permitted: set[str] = set()
        is_enum_anywhere = False
        for registry in registries.values():
            spec = registry.spec_for(predicate.field)
            if spec is not None and spec.type is FieldType.ENUM:
                is_enum_anywhere = True
                permitted |= set(spec.values)
        if not is_enum_anywhere:
            continue
        unknown = sorted(str(o) for o in operands if str(o) not in permitted)
        if unknown:
            problems.append(
                f"{predicate.id} compares {predicate.field} against "
                f"{', '.join(unknown)} (permitted: {', '.join(sorted(permitted))})"
            )
    if problems:
        raise PredicateLoadError(
            f"{len(problems)} predicate(s) compare an enum field against values it does "
            f"not permit, so they can never fire: {'; '.join(problems)}"
        )
