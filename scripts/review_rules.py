"""Run the review panel over every unreviewed rule, and record that it happened.

Writes two things per rule: a brief for a clinician to read, and an `review:`
block in the rule's own YAML recording that the panel has been through it, which
models did it, what they were concerned about, and which specialty should look
at it next.

**This does not verify anything.** A rule carrying a review is
AI_REVIEWED, which blocks a production release exactly as UNREVIEWED does. The
only thing that clears `verify_before_ship` is a named clinician, and the
command for that is `scripts/sign_off_rule.py`, which requires a person's name
and refuses to run without one.

Needs Ollama. Four model calls per rule — three seats and the chair — so roughly
five minutes per rule on a 3B model, and around two hours for all thirty.

Run:
    python scripts/review_rules.py --out docs/verification/panel
    python scripts/review_rules.py --only RF_ACS_001      # one rule, to check a prompt change
    python scripts/review_rules.py --dry-run              # write briefs, do not touch the YAML
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.agents.rule_panel import PanelResult, render, review_rule
from services.consult.clinical.actions import RedFlagAction
from spine.inference.config import (
    InferenceConfig,
    assert_transport_is_permitted,
    model_spec,
)
from spine.inference.ollama import OllamaProvider
from spine.inference.prompts import load
from spine.rules.predicate_loader import load_predicates, predicates_dir
from spine.rules.rule_loader import all_rules, load_rule_sets, rules_dir

PANEL_TIMEOUT_SECONDS: Final[float] = 900.0
"""How long to wait for one seat.

Measured: a 3B model takes 60-150s for a review of this length. The product
default of 120s is right for a patient turn and too short here, and raising it
in the product would let a slow turn hang rather than fail.
"""


def record_review(path: Path, result: PanelResult) -> bool:
    """Write the review into the rule's YAML, beside the rule it reviewed.

    Edited as text rather than by reloading and dumping the whole file. A
    round-trip through the parser would reformat every rule in the file and
    lose the comments, which on these files carry the reasoning that matters
    most — the blocks explaining what is unverified and why.
    """
    text = path.read_text(encoding="utf-8")
    anchor = f"  - id: {result.rule_id}\n"
    if anchor not in text:
        return False
    if f"# panel review for {result.rule_id}" in text:
        return False

    concerns = "\n".join(f"        - {_quote(c)}" for c in result.review.concerns)
    block = (
        f"    # panel review for {result.rule_id}: a record that the reading was\n"
        f"    # done, not a verification. This rule still blocks a release.\n"
        f"    review:\n"
        f"      reviewed_on: {result.review.reviewed_on}\n"
        f"      models: [{', '.join(result.review.models)}]\n"
        f"      panel_version: {result.review.panel_version}\n"
        f"      refer_to: {_quote(result.review.refer_to)}\n"
    )
    if result.review.dossier_path:
        block += f"      dossier_path: {_quote(result.review.dossier_path)}\n"
    if concerns:
        block += f"      concerns:\n{concerns}\n"

    start = text.index(anchor)
    end = text.find("\n  - id: ", start + 1)
    end = len(text) if end == -1 else end
    rule_text = text[start:end].rstrip("\n")
    path.write_text(
        text[:start] + rule_text + "\n" + block + text[end:], encoding="utf-8"
    )
    return True


def _quote(value: str) -> str:
    """A YAML scalar that survives colons, quotes and newlines."""
    flattened = " ".join(value.split())
    escaped = flattened.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("docs/verification/panel"))
    parser.add_argument("--service", default="consult")
    parser.add_argument("--only", default=None, help="review one rule by id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write the briefs but do not add review blocks to the rule files",
    )
    parser.add_argument(
        "--rereview",
        action="store_true",
        help="review rules that already carry a panel review",
    )
    args = parser.parse_args()

    directory = rules_dir(args.service, "red_flags")
    rule_sets = load_rule_sets(directory, RedFlagAction)
    rules = [rule for rule in all_rules(rule_sets) if rule.is_unverified]
    if not args.rereview:
        rules = [rule for rule in rules if rule.review is None]
    if args.only:
        rules = [rule for rule in rules if rule.id == args.only]
        if not rules:
            raise SystemExit(
                f"no rule with id {args.only!r} needs review; it may already carry one "
                f"(use --rereview) or already be verified"
            )
    if not rules:
        print("every unverified rule already carries a panel review")
        return 0

    vocabulary = frozenset(load_predicates(predicates_dir(args.service)))
    config = InferenceConfig.from_environment()
    assert_transport_is_permitted(config)
    model_spec(config)  # fails fast if no model is configured
    provider = OllamaProvider(timeout=PANEL_TIMEOUT_SECONDS)
    prompt = load(args.service, "rule_panel")

    args.out.mkdir(parents=True, exist_ok=True)
    flagged: list[str] = []
    recorded = 0
    today = date.today()

    for number, rule in enumerate(rules, start=1):
        print(f"[{number}/{len(rules)}] {rule.id}", flush=True)
        brief_path = args.out / f"{rule.id}.md"
        result = review_rule(
            rule,
            provider,
            prompt,
            config.primary_model,
            vocabulary=vocabulary,
            today=today,
            dossier_path=str(brief_path).replace("\\", "/"),
        )
        brief_path.write_text(render(result), encoding="utf-8")
        if not result.is_clean:
            flagged.append(rule.id)
        if not args.dry_run:
            for path in sorted(directory.glob("*.yaml")):
                if record_review(path, result):
                    recorded += 1
                    break

    print(f"\nreviewed {len(rules)} rule(s); briefs in {args.out}")
    if not args.dry_run:
        print(f"recorded {recorded} review block(s) in {directory}")
    if flagged:
        print(f"\n{len(flagged)} carry a warning and should be read with care:")
        for rule_id in flagged:
            print(f"  {rule_id}")

    print(
        "\nNo rule was verified. Every one of these still carries "
        "verify_before_ship and still blocks a production release.\n"
        "A named clinician signs off with scripts/sign_off_rule.py."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
