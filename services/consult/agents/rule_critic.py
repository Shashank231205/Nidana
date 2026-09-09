"""Challenging a draft rule before a clinician spends time on it.

This runs at design time, not in a patient's session. Nothing here touches a
record, and no output reaches a patient. It exists because a reviewing
clinician facing thirty unverified rules spends most of their first hour doing
something that is not judgement — working out, for each rule, which patient it
would miss.

The output is prose for that clinician, deliberately. It is not a patch, not a
proposed criterion, and not a verdict the system acts on. A structured verdict
would be tempting to consume automatically, and the moment anything consumes
it, a model's opinion has entered the clinical path.

Three guarantees are made in code rather than in the prompt, because a prompt
instruction is a tendency and these need to be facts:

The rule is returned unchanged and still unverified. `Challenge` holds the rule
it reviewed, and `verify_before_ship` is asserted on the way out. A critique
that could clear a flag would be a model verifying a clinical criterion, which
is the one thing this repository does not do.

A critique that reads as approval is rejected. The model is asked for a verdict
that is never approving; if it returns one anyway, the challenge is marked
`approving_verdict_rejected` and the text is kept for a human to read rather
than silently discarded.

Numbers the model invented are counted. The prompt forbids proposing
thresholds, because a fabricated clinical constant reads as a sourced one.
Counting them lets a reviewer see when the model drifted rather than trusting
that it did not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from spine.inference.adapter import InferenceProvider
from spine.inference.prompts import Prompt, spec_for
from spine.schemas.rule import ActionT, Rule

APPROVING: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bis (?:clinically )?(?:correct|sound|adequate|appropriate)\b", re.I),
    re.compile(r"\b(?:no|nothing) (?:changes?|action)\w*\s+(?:\w+\s+)?(?:required|needed)\b", re.I),
    re.compile(r"\bready (?:to|for) ship\b", re.I),
    re.compile(r"\bsafe to (?:ship|release|deploy|verify)\b", re.I),
    re.compile(r"\b(?:can|should) be (?:verified|approved|signed off)\b", re.I),
    re.compile(r"\bverify_before_ship\s*:\s*false\b", re.I),
)
"""Phrases that would let a reader take a critique as a pass.

The prompt says the verdict is never approving. This is the check that it was
not, and it is deliberately broad: a false positive costs a reviewer one
glance at a flagged critique, and a false negative puts "this rule is
clinically sound" in front of someone deciding whether to sign it.
"""

PROPOSED_THRESHOLD: Final[re.Pattern[str]] = re.compile(
    r"""(?:^|[\s(])
        (?:>|<|>=|<=|greater\ than|less\ than|more\ than|fewer\ than|
        above|below|over|under|at\ least|at\ most|exceeding|longer\ than)
        \s*
        \d+(?:\.\d+)?
        \s*
        (?:mg|ml|mmol|mmhg|bpm|g/dl|mm/hr|hours?|hrs?|minutes?|mins?|days?|weeks?|years?|%)
    """,
    re.I | re.X,
)
"""A numeric clinical threshold stated as a proposal.

Not every number is one — "58-year-old woman" is a patient and "CG95" is a
citation — so this matches only a comparison against a number with a clinical
unit, which is the shape a fabricated cut-off takes.
"""


@dataclass(frozen=True)
class Challenge:
    """One rule's critique, and what was wrong with the critique itself."""

    rule_id: str
    rule_label: str
    text: str
    model_version: str
    approving_verdict_rejected: bool
    proposed_thresholds: tuple[str, ...]
    truncated: bool = False

    @property
    def still_unverified(self) -> bool:
        """Always true. Stated so a caller cannot read a critique as a sign-off."""
        return True

    @property
    def is_trustworthy(self) -> bool:
        """Whether this critique can be read without a warning attached.

        False when the model approved the rule, invented a threshold, or ran
        out of tokens mid-argument. The critique is still shown — a reviewer
        reads it and judges — but it is shown flagged.
        """
        return not (
            self.approving_verdict_rejected or self.proposed_thresholds or self.truncated
        )


REQUIRED_SECTION: Final[str] = "Questions for the verifying clinician"
"""The last section the prompt asks for.

Its absence is how truncation is detected. It is also the section a reviewer
most needs, so a critique missing it is worth flagging even if the model
simply skipped it.
"""


def find_approving_language(text: str) -> bool:
    """Whether a critique reads as clearing the rule."""
    return any(pattern.search(text) for pattern in APPROVING)


def looks_truncated(text: str) -> bool:
    """Whether the model ran out of tokens before finishing.

    A critique cut mid-argument loses the questions section, which is the part
    a reviewer acts on. Worse, it usually stops partway through a concession —
    so what survives reads more one-sided than the model actually was.

    Two signals, either sufficient: the final required heading never appeared,
    or the text ends mid-sentence.
    """
    if not text:
        return True
    if REQUIRED_SECTION.lower() not in text.lower():
        return True
    return text.rstrip()[-1] not in ".!?)`\"'"


def find_proposed_thresholds(text: str) -> tuple[str, ...]:
    """Numeric clinical cut-offs the model proposed.

    Returned rather than stripped. A reviewer needs to see what the model
    reached for; silently removing it would hide the drift and leave a
    sentence that no longer parses.
    """
    return tuple(match.group().strip() for match in PROPOSED_THRESHOLD.finditer(text))


def build_brief(
    rule: Rule[ActionT],
    *,
    vocabulary: frozenset[str] = frozenset(),
    passages: tuple[str, ...] = (),
) -> str:
    """What the critic is shown about one rule.

    The criteria are given as encoded rather than as prose, because the label
    describes the intent and the criteria describe what actually fires, and the
    gap between those two is where several of these rules are wrong.
    """
    lines = [
        f"RULE: {rule.id}",
        f"LABEL: {rule.label}",
        f"ACTION: {rule.action}",
        "",
        "CRITERIA AS ENCODED — the rule fires when any one line holds in full:",
    ]
    lines.extend(f"  - {' AND '.join(clause.all_of)}" for clause in rule.any_of)
    if rule.modifiers.escalate_if:
        lines.append(f"  escalates further on: {', '.join(rule.modifiers.escalate_if)}")

    lines.extend(["", f"CURRENT SOURCE LINE: {rule.source}"])
    if rule.notes:
        lines.extend(["", f"NOTE LEFT BY THE AUTHOR: {rule.notes}"])

    if vocabulary:
        available = sorted(vocabulary - rule.atoms)
        lines.extend(
            [
                "",
                "PREDICATES AVAILABLE TO THIS SYSTEM BUT NOT USED BY THIS RULE.",
                "A criticism needing anything outside this list is a schema gap, "
                "and should be reported as one:",
                "  " + ", ".join(available) if available else "  (none)",
            ]
        )

    lines.extend(["", "RETRIEVED PASSAGES FROM THE LOCAL CORPUS:"])
    if passages:
        lines.extend(f"  [{n}] {text}" for n, text in enumerate(passages, start=1))
        lines.append(
            "  These are facility standards and may be irrelevant to this rule. "
            "Say so if they are."
        )
    else:
        lines.append("  (none — the corpus does not cover this rule)")

    lines.extend(
        [
            "",
            "Write the challenge. Construct the patient this rule misses.",
        ]
    )
    return "\n".join(lines)


def challenge_rule(
    rule: Rule[ActionT],
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
    *,
    vocabulary: frozenset[str] = frozenset(),
    passages: tuple[str, ...] = (),
) -> Challenge:
    """Critique one rule.

    Returns the critique with its own defects recorded rather than raising on
    them. A reviewer working through thirty rules is better served by
    twenty-nine clean critiques and one flagged than by an exception.
    """
    if not rule.verify_before_ship:
        raise ValueError(
            f"rule {rule.id} is already verified; the critic reviews draft rules "
            f"before a clinician signs them, and re-opening a signed rule is a "
            f"clinical decision rather than an automated one"
        )

    # Built from the prompt header rather than taken from the caller, as the
    # other agents do. model_spec() defaults to 512 output tokens, which cuts a
    # critique off partway through its concession and leaves something that
    # reads more one-sided than the critic was.
    spec = spec_for(prompt, model)
    completion = provider.complete(
        prompt=build_brief(rule, vocabulary=vocabulary, passages=passages),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    text = completion.text.strip()
    return Challenge(
        rule_id=rule.id,
        rule_label=rule.label,
        text=text,
        model_version=completion.model_version,
        approving_verdict_rejected=find_approving_language(text),
        proposed_thresholds=find_proposed_thresholds(text),
        truncated=looks_truncated(text),
    )


def render(challenge: Challenge) -> str:
    """One critique as Markdown, with its warnings above the text.

    The warnings lead because a reviewer skimming thirty of these must not
    have to reach the bottom to learn that the model invented a number in the
    middle.
    """
    lines = [f"# {challenge.rule_id} — {challenge.rule_label}", ""]
    lines.append(
        "**This rule remains unverified.** A critique is not a review and does "
        "not clear `verify_before_ship`. It was written by a model to shorten "
        "a clinician's reading, and the clinician's judgement is the only thing "
        "that signs this rule off."
    )
    lines.append("")

    if challenge.approving_verdict_rejected:
        lines.extend(
            [
                "> **Warning: this critique contains approving language.** The critic "
                "was asked never to approve a rule and appears to have done so. Read "
                "the reasoning, not the conclusion.",
                "",
            ]
        )
    if challenge.proposed_thresholds:
        listed = ", ".join(f"`{t}`" for t in challenge.proposed_thresholds)
        lines.extend(
            [
                f"> **Warning: the critic proposed numeric thresholds** ({listed}). "
                f"These are not sourced and must not be treated as clinical values. "
                f"They are shown because seeing what the model reached for is more "
                f"useful than hiding it.",
                "",
            ]
        )

    if challenge.truncated:
        lines.extend(
            [
                "> **Warning: this critique is incomplete.** It stops before the "
                "questions section, most likely at the token limit. A truncated "
                "critique usually breaks off partway through the concession, so "
                "what survives reads more one-sided than the critic was.",
                "",
            ]
        )

    lines.extend([challenge.text, "", "---", "", f"Model: {challenge.model_version}."])
    return "\n".join(lines)
