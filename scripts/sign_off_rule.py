"""Record that a named clinician has verified a rule.

This is the only thing in the repository that clears `verify_before_ship`, and
it is a script a person runs with their own name rather than anything a model
can reach. That is the whole design: everything else — the citations research,
the dossiers, the review panel — exists to make this five minutes of reading
instead of two hours, and none of it can perform this step.

What setting the flag asserts, in the audit trail of a system that routes real
patients: *this named, qualified person read this criterion and accepts
responsibility for it*. If the rule then under-triages someone, the record says
who signed. That is why the name is required, why it is not defaulted from the
environment, and why a panel review does not substitute for it.

Run:
    python scripts/sign_off_rule.py RF_ACS_001 --by "Dr A Sharma, MD (Emergency Medicine)" \\
        --source "NICE CG95, reviewed against local protocol 2026-09"

    python scripts/sign_off_rule.py --list        # what still needs a signature
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.clinical.actions import RedFlagAction
from spine.rules.rule_loader import all_rules, load_rule_sets, rules_dir
from spine.schemas.rule import VerificationState

MINIMUM_NAME_LENGTH = 4
"""Shorter than this is not a name.

A guard against '-', 'me', or an empty string getting into the field that says
who is accountable. It cannot tell a real clinician from a plausible string,
and is not trying to: it catches the accident, not the lie.
"""


def sign_off(path: Path, rule_id: str, *, by: str, source: str, on: date) -> bool:
    """Set the verification fields on one rule in its YAML file.

    Edits as text rather than round-tripping through the parser, which would
    reformat every rule in the file and drop the comments that carry the
    reasoning.
    """
    text = path.read_text(encoding="utf-8")
    anchor = f"  - id: {rule_id}\n"
    if anchor not in text:
        return False

    start = text.index(anchor)
    end = text.find("\n  - id: ", start + 1)
    end = len(text) if end == -1 else end
    body = text[start:end]

    if "verify_before_ship: false" in body:
        raise SystemExit(f"{rule_id} is already verified; nothing to do")

    updated = body.replace(
        "    verify_before_ship: true",
        f"    source: {_quote(source)}\n"
        f"    verified_on: {on}\n"
        f"    verified_by: {_quote(by)}\n"
        f"    verify_before_ship: false",
        1,
    )
    # The old source line is now duplicated; drop the placeholder one.
    updated = _drop_placeholder_source(updated)
    path.write_text(text[:start] + updated + text[end:], encoding="utf-8")
    return True


def _drop_placeholder_source(body: str) -> str:
    """Remove the original source line, keeping the one just written.

    The placeholder can be a folded block spanning several lines, so this
    walks until the indentation returns to the field level.
    """
    lines = body.splitlines(keepends=True)
    kept: list[str] = []
    skipping = False
    seen_new_source = False
    for line in lines:
        if line.startswith("    source:") and not seen_new_source:
            seen_new_source = True
            kept.append(line)
            continue
        if line.startswith("    source:") and seen_new_source:
            skipping = True
            continue
        if skipping:
            if line.startswith("      ") or not line.strip():
                continue
            skipping = False
        kept.append(line)
    return "".join(kept)


def _quote(value: str) -> str:
    flattened = " ".join(value.split())
    escaped = flattened.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def show_outstanding(service: str) -> int:
    """What still needs a signature, and what has been read already."""
    rule_sets = load_rule_sets(rules_dir(service, "red_flags"), RedFlagAction)
    rules = all_rules(rule_sets)
    by_state: dict[VerificationState, list[str]] = {state: [] for state in VerificationState}
    for rule in rules:
        by_state[rule.state].append(rule.id)

    for state in VerificationState:
        listed = by_state[state]
        print(f"{state.value} ({len(listed)})")
        for rule_id in listed:
            rule = next(r for r in rules if r.id == rule_id)
            suffix = ""
            if rule.review is not None:
                suffix = f"  -> refer to {rule.review.refer_to}"
            if rule.verified_by:
                suffix = f"  signed by {rule.verified_by[:60]}"
            print(f"  {rule_id}{suffix}")
        print()

    blocked = len(by_state[VerificationState.UNREVIEWED]) + len(
        by_state[VerificationState.AI_REVIEWED]
    )
    print(
        f"{blocked} rule(s) block a production release. An AI review does not "
        f"clear one; only a named clinician does."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rule_id", nargs="?", help="the rule being signed off")
    parser.add_argument("--by", help="the clinician's name and qualification")
    parser.add_argument("--source", help="what they actually relied on")
    parser.add_argument("--service", default="consult")
    parser.add_argument(
        "--list", action="store_true", help="show what still needs a signature"
    )
    args = parser.parse_args()

    if args.list or not args.rule_id:
        return show_outstanding(args.service)

    if not args.by or len(args.by.strip()) < MINIMUM_NAME_LENGTH:
        raise SystemExit(
            "--by is required and must name the clinician accepting responsibility, "
            "for example 'Dr A Sharma, MD (Emergency Medicine)'. Setting "
            "verify_before_ship false without a name puts 'a doctor approved this' "
            "into the audit trail of a system that routes patients, and leaves no "
            "way to say which doctor"
        )
    if not args.source or not args.source.strip():
        raise SystemExit(
            "--source is required. It replaces the placeholder and records what the "
            "reviewer actually relied on — a guideline, a local protocol, or their "
            "own assessment against this laboratory and this hospital"
        )

    directory = rules_dir(args.service, "red_flags")
    for path in sorted(directory.glob("*.yaml")):
        if sign_off(path, args.rule_id, by=args.by, source=args.source, on=date.today()):
            print(f"{args.rule_id} signed off by {args.by} in {path.name}")
            print("Run scripts/verify_rules.py to confirm the file still loads.")
            return 0

    raise SystemExit(f"no rule with id {args.rule_id!r} in {directory}")


if __name__ == "__main__":
    sys.exit(main())
