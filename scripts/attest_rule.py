"""Record a deployment's decision to run a rule on a model's reading alone.

This is the honest middle path between two worse options: pretending a doctor
signed a rule nobody read, or refusing to start at all when no clinician is
available. It says exactly what happened — a panel of models read the rule, a
named person in the deploying organisation accepted the risk — and it makes
that statement travel with every output the rule contributes to.

**What it is not.** It does not set `verify_before_ship`, does not write
`verified_by`, and cannot produce `CLINICIAN_VERIFIED`. A rule attested this
way reports `MODEL_ATTESTED` for as long as the attestation stands, and
`Rule.disclosure` returns a line naming the models and the drift count. Only
`scripts/sign_off_rule.py`, run by a clinician, reaches the verified state.

**Read the drift count before attesting.** The panel is a 3B model and it is
not reliable about itself. On the first full run over eight rules it invented
four clinical thresholds — `> 500 mL` for obstetric bleeding among them — used
approving language it was told never to use, and truncated ten of twenty-four
seat reviews. The guards caught all of it, and the count is carried into the
attestation so it sits beside the rule rather than in a log.

Run:
    python scripts/attest_rule.py --list
    python scripts/attest_rule.py RF_ACS_001 --accepted-by "S Shashank, CTO"
    python scripts/attest_rule.py --all --accepted-by "S Shashank, CTO"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.clinical.actions import RedFlagAction
from spine.rules.rule_loader import all_rules, load_rule_sets, rules_dir
from spine.schemas.rule import Rule, VerificationState

MINIMUM_NAME_LENGTH: Final[int] = 4
"""Shorter than this is not a person.

Catches the accident — an empty string, a dash, "me" — not the lie. Whoever is
named here is accepting that a rule routing real patients was never read by a
clinician, and the name is the only thing making that decision attributable.
"""


def drift_for(brief_path: Path) -> tuple[str, ...]:
    """The warnings the panel raised about its own output for this rule.

    Read back from the brief rather than recomputed, so what the attestation
    records is what a reader of that brief actually saw.
    """
    if not brief_path.is_file():
        return ()
    return tuple(
        line.strip().lstrip("> ").replace("**", "")
        for line in brief_path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("> **Warning")
    )


def attest(
    path: Path,
    rule_id: str,
    *,
    accepted_by: str,
    models: tuple[str, ...],
    panel_version: str,
    drift: tuple[str, ...],
    on: date,
) -> bool:
    """Write the attestation into the rule's YAML.

    Edited as text rather than round-tripped through the parser, which would
    reformat every rule in the file and drop the comments carrying the
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

    if "    attestation:" in body:
        raise SystemExit(f"{rule_id} already carries an attestation")
    if "verify_before_ship: false" in body:
        raise SystemExit(
            f"{rule_id} is already verified by a clinician; attesting it would "
            f"replace a signature with a model's reading"
        )

    block = (
        f"    # A deployment decision, not a clinical one: this rule runs on a\n"
        f"    # model's reading because no clinician reviewed it. Every output it\n"
        f"    # contributes to carries Rule.disclosure saying so.\n"
        f"    attestation:\n"
        f"      attested_on: {on}\n"
        f"      attested_by: [{', '.join(models)}]\n"
        f"      accepted_by: {_quote(accepted_by)}\n"
        f"      panel_version: {panel_version}\n"
    )
    if drift:
        listed = "\n".join(f"        - {_quote(item)}" for item in drift)
        block += f"      drift:\n{listed}\n"

    path.write_text(
        text[:start] + body.rstrip("\n") + "\n" + block + text[end:], encoding="utf-8"
    )
    return True


def _quote(value: str) -> str:
    flattened = " ".join(value.split())
    escaped = flattened.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def show(service: str) -> int:
    """Every rule by state, and what attesting the rest would mean."""
    rules = all_rules(load_rule_sets(rules_dir(service, "red_flags"), RedFlagAction))
    by_state: dict[VerificationState, list[Rule[RedFlagAction]]] = {
        state: [] for state in VerificationState
    }
    for rule in rules:
        by_state[rule.state].append(rule)

    for state in VerificationState:
        listed = by_state[state]
        print(f"{state.value} ({len(listed)})")
        for rule in listed:
            suffix = ""
            if rule.attestation is not None:
                suffix = f"  — {len(rule.attestation.drift)} drift warning(s)"
            elif rule.review is not None:
                suffix = f"  — refer to {rule.review.refer_to}"
            print(f"  {rule.id}{suffix}")
        print()

    blocking = sum(1 for rule in rules if rule.blocks_release)
    attested = len(by_state[VerificationState.MODEL_ATTESTED])
    print(f"{blocking} rule(s) block a production release.")
    if attested:
        print(
            f"{attested} rule(s) run on a model's reading. Every triage they "
            f"contribute to discloses that."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rule_id", nargs="?")
    parser.add_argument(
        "--accepted-by",
        help="who in the deploying organisation accepts that no clinician read this",
    )
    parser.add_argument("--all", action="store_true", help="attest every reviewed rule")
    parser.add_argument("--service", default="consult")
    parser.add_argument("--briefs", type=Path, default=Path("docs/verification/panel"))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list or (not args.rule_id and not args.all):
        return show(args.service)

    if not args.accepted_by or len(args.accepted_by.strip()) < MINIMUM_NAME_LENGTH:
        raise SystemExit(
            "--accepted-by is required and must name a person, for example "
            "'S Shashank, CTO'. Attesting a rule means accepting that a criterion "
            "routing real patients was never read by a clinician, and the name is "
            "what makes that decision attributable"
        )

    directory = rules_dir(args.service, "red_flags")
    rules = all_rules(load_rule_sets(directory, RedFlagAction))
    if args.all:
        targets = [rule for rule in rules if rule.state is VerificationState.AI_REVIEWED]
        if not targets:
            raise SystemExit(
                "no rule is in the ai_reviewed state. Run scripts/review_rules.py "
                "first: attesting a rule no panel has read would record a reading "
                "that did not happen"
            )
    else:
        targets = [rule for rule in rules if rule.id == args.rule_id]
        if not targets:
            raise SystemExit(f"no rule with id {args.rule_id!r}")
        if targets[0].review is None:
            raise SystemExit(
                f"{targets[0].id} has no panel review. Run "
                f"'python scripts/review_rules.py --only {targets[0].id}' first"
            )

    today = date.today()
    done = 0
    total_drift = 0
    for rule in targets:
        review = rule.review
        if review is None:
            continue
        drift = drift_for(args.briefs / f"{rule.id}.md")
        total_drift += len(drift)
        for path in sorted(directory.glob("*.yaml")):
            if attest(
                path,
                rule.id,
                accepted_by=args.accepted_by,
                models=review.models,
                panel_version=review.panel_version,
                drift=drift,
                on=today,
            ):
                done += 1
                print(f"{rule.id}: attested ({len(drift)} drift warning(s))")
                break

    print(f"\nattested {done} rule(s), accepted by {args.accepted_by}")
    if total_drift:
        print(
            f"{total_drift} drift warning(s) across them: thresholds the panel "
            f"invented, approving language it was told not to use, reviews cut "
            f"short. These are recorded on each rule."
        )
    print(
        "\nNo rule was verified. These run on a model's reading, and every "
        "output they contribute to says so. A clinician signs off with "
        "scripts/sign_off_rule.py."
    )
    print("Run scripts/verify_rules.py to confirm the files still load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
