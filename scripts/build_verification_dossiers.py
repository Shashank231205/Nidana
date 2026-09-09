"""Assemble the reviewing clinician's reading for every unverified rule.

Thirty red flag rules carry `verify_before_ship: true` and a release build
refuses to start while they do. Clearing that flag is a clinician's signature
and this script does not touch it. What it removes is the hours of reading
before their first decision: it writes one dossier per rule holding the
criteria as encoded, whatever the local corpus actually contains, and the
questions that remain open.

Needs the knowledge index built (scripts/build_knowledge_index.py) and Ollama
running, because it embeds a query per rule. Without them it still writes
dossiers, each recording that retrieval was unavailable rather than implying
the corpus was silent.

Run:
    python scripts/build_verification_dossiers.py --out docs/verification
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.consult.clinical.actions import RedFlagAction
from spine.knowledge.index import KnowledgeIndex, KnowledgeIndexError, load_index
from spine.rules.dossier import build_dossier, render
from spine.rules.rule_loader import all_rules, load_rule_sets, rules_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/verification"),
        help="directory to write the dossiers into",
    )
    parser.add_argument(
        "--service", default="consult", help="which service's red flag rules to read"
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "knowledge_index.json",
        help="the knowledge index to retrieve from",
    )
    args = parser.parse_args()

    rule_sets = load_rule_sets(rules_dir(args.service, "red_flags"), RedFlagAction)
    rules = all_rules(rule_sets)
    unverified = [rule for rule in rules if rule.is_unverified]

    try:
        index: KnowledgeIndex | None = load_index(args.index)
    except KnowledgeIndexError as error:
        print(f"knowledge index unavailable: {error}", file=sys.stderr)
        print("dossiers will record that retrieval was unavailable", file=sys.stderr)
        index = None

    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    silent = 0
    for rule in unverified:
        if index is None:
            body = (
                f"## {rule.id} — {rule.label}\n\n"
                f"**Status: unverified.**\n\n"
                f"The knowledge index was not available when this was built, so "
                f"no evidence was retrieved. Build it with "
                f"scripts/build_knowledge_index.py and rerun.\n"
            )
        else:
            dossier = build_dossier(rule, index)
            silent += int(dossier.corpus_silent)
            body = render(dossier)
        (args.out / f"{rule.id}.md").write_text(body, encoding="utf-8")
        written += 1

    print(f"{len(rules)} rules, {len(unverified)} unverified")
    print(f"wrote {written} dossiers to {args.out}")
    if index is not None:
        print(f"  the corpus was silent on {silent} of them")
        print(
            "  silence is expected: the corpus holds facility standards, and most "
            "clinical criteria are not in it"
        )
    print("\nNo flag was changed. Every rule still carries verify_before_ship.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
