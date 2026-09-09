"""Run the rule critic across every unverified rule.

Produces one critique per rule for a clinician to read. Nothing here verifies
anything: `verify_before_ship` is untouched, and a rule that has already been
signed off is skipped rather than re-opened, because re-opening a signed rule
is a clinical decision.

Pairs with scripts/build_verification_dossiers.py. The dossier says what the
corpus holds; this says what a sceptical colleague would say about the rule.
A reviewer wants both, and neither is a review.

Needs Ollama running. Roughly a minute per rule on a 3B model, so about half an
hour for all thirty.

Run:
    python scripts/challenge_rules.py --out docs/verification/challenges
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.agents.rule_critic import challenge_rule, render
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

CRITIQUE_TIMEOUT_SECONDS: Final[float] = 600.0
"""How long to wait for one critique.

Measured: a 3B model takes 60-80s for a 2,000-character critique, and a larger
model on a cold CPU is slower still. The product default of 120s is right for a
patient turn and too short here.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/verification/challenges"),
        help="directory to write the critiques into",
    )
    parser.add_argument("--service", default="consult", help="whose rules to review")
    parser.add_argument(
        "--only",
        default=None,
        help="review a single rule by id, for checking a prompt change quickly",
    )
    args = parser.parse_args()

    rule_sets = load_rule_sets(rules_dir(args.service, "red_flags"), RedFlagAction)
    rules = [rule for rule in all_rules(rule_sets) if rule.is_unverified]
    if args.only:
        rules = [rule for rule in rules if rule.id == args.only]
        if not rules:
            raise SystemExit(f"no unverified rule with id {args.only!r}")

    registry = load_predicates(predicates_dir(args.service))
    vocabulary = frozenset(registry)

    config = InferenceConfig.from_environment()
    # A critique is several times longer than a patient turn, and this is a
    # batch job nobody is waiting on. The product default of 120s is right for
    # a turn and too short here; raising it in the product would let a slow
    # patient turn hang instead of failing.
    provider = OllamaProvider(timeout=CRITIQUE_TIMEOUT_SECONDS)
    assert_transport_is_permitted(config)
    prompt = load(args.service, "rule_critic")
    model_spec(config)  # fails fast if no model is configured

    args.out.mkdir(parents=True, exist_ok=True)
    flagged: list[str] = []
    for number, rule in enumerate(rules, start=1):
        print(f"[{number}/{len(rules)}] {rule.id}", flush=True)
        challenge = challenge_rule(
            rule, provider, prompt, config.primary_model, vocabulary=vocabulary
        )
        (args.out / f"{rule.id}.md").write_text(render(challenge), encoding="utf-8")
        if not challenge.is_trustworthy:
            reasons = []
            if challenge.approving_verdict_rejected:
                reasons.append("approving language")
            if challenge.proposed_thresholds:
                reasons.append(f"invented {len(challenge.proposed_thresholds)} threshold(s)")
            flagged.append(f"{rule.id}: {', '.join(reasons)}")

    print(f"\nwrote {len(rules)} critiques to {args.out}")
    if flagged:
        print(f"\n{len(flagged)} carry a warning and should be read with care:")
        for line in flagged:
            print(f"  {line}")
    print("\nNo flag was changed. Every rule still carries verify_before_ship.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
