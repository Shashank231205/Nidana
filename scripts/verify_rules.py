"""Verify every shipped rule set can actually fire.

Run in CI. This check cannot be skipped, because the defect it catches is
invisible to every other gate: a rule referencing an atom that resolves to
nothing evaluates false forever, disabling the rule while its negative tests
continue to pass.

Exits non-zero with a message naming the rule, the atom, and the fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.clinical import red_flags, routing
from services.consult.clinical.actions import RedFlagAction
from spine.rules.predicate_loader import (
    check_enum_operands,
    load_predicates,
    resolve_against_registries,
)
from spine.rules.predicates import DEMOGRAPHIC_FIELDS
from spine.rules.registry_loader import known_fields, load_all
from spine.rules.rule_loader import all_rules, load_rule_sets, resolve_atoms, rules_dir


def main() -> int:
    registries = load_all()
    predicates = load_predicates()
    resolve_against_registries(predicates, registries)
    check_enum_operands(predicates, registries)

    rule_sets = load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction)
    resolve_atoms(rule_sets, predicates)

    declared = known_fields(registries) | DEMOGRAPHIC_FIELDS
    dead: list[str] = []
    unrouted: list[str] = []
    uncapable: list[str] = []
    for rule in all_rules(rule_sets):
        for atom in sorted(rule.atoms):
            field = predicates[atom].field
            if field not in declared:
                dead.append(f"{rule.id} -> {atom} -> {field}")
        if rule.id not in routing.RULE_SPECIALTY:
            unrouted.append(rule.id)
        if (
            rule.action is RedFlagAction.TERMINATE_EMERGENCY
            and rule.id not in red_flags.RULE_CAPABILITIES
        ):
            uncapable.append(rule.id)

    problems = 0
    if dead:
        print(f"DEAD RULES ({len(dead)}): atoms testing fields no registry declares")
        for entry in dead:
            print(f"  {entry}")
        problems += len(dead)
    if unrouted:
        print(f"UNROUTED RULES ({len(unrouted)}): {', '.join(unrouted)}")
        problems += len(unrouted)
    if uncapable:
        print(f"TERMINATING RULES WITH NO CAPABILITY ({len(uncapable)}): {', '.join(uncapable)}")
        problems += len(uncapable)

    if problems:
        print(f"\n{problems} problem(s). See services/consult/rules/ and clinical/.")
        return 1

    rules = all_rules(rule_sets)
    total = len(rules)
    blocking = sum(1 for rule in rules if rule.blocks_release)
    attested = sum(1 for rule in rules if rule.attestation is not None)
    print(
        f"OK: {len(registries)} registries, {len(predicates)} predicates, {total} rules, "
        f"every atom resolves and every rule is reachable."
    )
    if blocking:
        print(
            f"NOTE: {blocking}/{total} rules block a production release and cannot ship "
            f"until a clinician verifies each criterion."
        )
    # Counted separately from the blocking total rather than folded into it. An
    # attested rule ships, so reporting it as blocked would be wrong; reporting
    # only the blocking count would hide that some rules ship on a model's
    # reading, which is the more important of the two facts.
    if attested:
        print(
            f"NOTE: {attested}/{total} rules ship on a model's reading with no "
            f"clinician review. Every triage they contribute to discloses that."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
