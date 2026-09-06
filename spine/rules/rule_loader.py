"""Loading rule sets and refusing the configurations that would ship unsafely.

Two gates live here.

Atom resolution: every atom in every shipped rule must resolve to a loaded
predicate. ADR 0005.

Verification: a rule encoding a clinical criterion carries a citation and a
verify_before_ship flag. A release build refuses to start while any active rule
still carries it, so an unverified threshold cannot reach a patient by being
forgotten.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from spine.rules.registry_loader import rules_root
from spine.schemas.predicate import Predicate
from spine.schemas.rule import ActionT, Rule, RuleSet


class RuleLoadError(RuntimeError):
    """Raised when a rule file is malformed or its rules cannot be trusted."""


class UnverifiedRulesError(RuntimeError):
    """Raised when a release build would ship a clinically unverified rule."""


def rules_dir(service: str, kind: str) -> Path:
    """The directory holding one kind of rule for `service`, e.g. red_flags."""
    return rules_root(service) / kind


def _read_rule_file(path: Path) -> dict[str, object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RuleLoadError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(raw, dict):
        raise RuleLoadError(
            f"{path} must contain a mapping with 'name', 'version' and 'rules'; found "
            f"{type(raw).__name__}"
        )
    return raw


def load_rule_set(
    path: Path,
    action_type: type[ActionT],
) -> RuleSet[ActionT]:
    """Load and validate one rule set file against `action_type`.

    The action type is the service's vocabulary. A rule declaring an action the
    service does not define fails here rather than at the moment it fires.
    """
    if not path.is_file():
        raise RuleLoadError(
            f"no rule set at {path}; create it, or correct the path the service passes"
        )
    raw = _read_rule_file(path)
    try:
        return RuleSet[action_type].model_validate(raw)  # type: ignore[valid-type]
    except ValidationError as error:
        raise RuleLoadError(f"{path} is not a valid rule set: {error}") from error


def load_rule_sets(
    directory: Path,
    action_type: type[ActionT],
) -> tuple[RuleSet[ActionT], ...]:
    """Load every rule set in `directory`, rejecting duplicate rule ids across files."""
    if not directory.is_dir():
        raise RuleLoadError(
            f"rule directory {directory} does not exist; it holds the declarative rule "
            f"sets for this service"
        )
    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        raise RuleLoadError(f"no rule files found in {directory}")
    loaded = tuple(load_rule_set(path, action_type) for path in paths)
    _reject_duplicate_rule_ids(loaded, paths)
    return loaded


def _reject_duplicate_rule_ids(
    rule_sets: tuple[RuleSet[ActionT], ...],
    paths: tuple[Path, ...] | list[Path],
) -> None:
    origin: dict[str, Path] = {}
    for rule_set, path in zip(rule_sets, paths, strict=True):
        for rule in rule_set.rules:
            if rule.id in origin:
                raise RuleLoadError(
                    f"rule id {rule.id} is defined in both {origin[rule.id]} and {path}; "
                    f"a firing must identify exactly one rule"
                )
            origin[rule.id] = path


def resolve_atoms(
    rule_sets: tuple[RuleSet[ActionT], ...],
    predicates: dict[str, Predicate],
) -> None:
    """Confirm every atom in every rule resolves to a loaded predicate.

    ADR 0005. Reports every unresolved atom at once, naming its rule.
    """
    unresolved = sorted(
        f"{rule.id} -> {atom}"
        for rule_set in rule_sets
        for rule in rule_set.rules
        for atom in sorted(rule.atoms)
        if atom not in predicates
    )
    if unresolved:
        raise RuleLoadError(
            f"{len(unresolved)} rule atom(s) reference predicates that are not defined: "
            f"{'; '.join(unresolved)}. A rule with an unresolved atom cannot fire and "
            f"reports green on its negative tests. Define the predicate in the "
            f"service's rules/predicates/, or correct the atom"
        )


def require_verified(
    rule_sets: tuple[RuleSet[ActionT], ...],
    allow_unverified: bool,
) -> None:
    """Refuse to proceed when a release build would ship an unverified criterion.

    `allow_unverified` comes from NIDANA_ALLOW_UNVERIFIED_RULES and is true in
    development. In a release build it is false, and this raises listing every
    rule still awaiting clinician sign-off.
    """
    if allow_unverified:
        return
    pending = tuple(
        rule for rule_set in rule_sets for rule in rule_set.unverified
    )
    if pending:
        listing = "; ".join(f"{rule.id} ({rule.source})" for rule in pending)
        raise UnverifiedRulesError(
            f"{len(pending)} rule(s) carry verify_before_ship and cannot ship: {listing}. "
            f"A qualified clinician must verify each criterion against its cited source, "
            f"then set verify_before_ship false with the verified_on date. To run anyway "
            f"in development, set NIDANA_ALLOW_UNVERIFIED_RULES=true"
        )


def all_rules(rule_sets: tuple[RuleSet[ActionT], ...]) -> tuple[Rule[ActionT], ...]:
    return tuple(rule for rule_set in rule_sets for rule in rule_set.rules)
