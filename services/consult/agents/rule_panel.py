"""A panel of reviewers over one draft rule, converging to a single brief.

Design time, not a patient session. Nothing here touches a record and no output
reaches a patient.

Three reviewers and a chair, rather than one critic, because the seats find
different things. Run over the same rules, the emergency physician produces the
missed patient, the safety engineer produces the rule interaction nobody
noticed, and the Indian practice reviewer produces the reason a Western
threshold does not transfer. A single reviewer asked to do all three produces
the first and gestures at the others.

The chair exists because three reviews is worse than one for the person who has
to read them. A clinician with fifteen minutes needs one brief, and the useful
thing a chair does is not summarise but **keep the disagreements**: where the
practice reviewer wants a rule widened and the safety engineer says widening
makes it fire on everything, that tension is the finding, and averaging it away
would leave a bland paragraph that decides nothing.

What the panel produces is an `AiReview`, which records that the reading was
done and refers the rule to a named specialty. It is not a verification and
cannot become one: `AiReview.clears_release` is false, `Rule.blocks_release`
ignores the review entirely, and nothing in this module writes
`verify_before_ship`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from services.consult.agents.rule_critic import (
    build_brief,
    find_approving_language,
    find_proposed_thresholds,
    looks_truncated,
)
from spine.inference.adapter import InferenceProvider
from spine.inference.prompts import Prompt, spec_for
from spine.schemas.rule import ActionT, AiReview, Rule

PANEL_VERSION: Final[str] = "1.0.0"

SEATS: Final[tuple[tuple[str, str], ...]] = (
    (
        "emergency physician",
        "You are the emergency physician. You have seen what walks through the "
        "door at 2am. Your question is which patient this rule misses.",
    ),
    (
        "safety engineer",
        "You are the safety engineer. You do not treat patients; you study how "
        "protocols fail. Your question is how this rule behaves at its edges, "
        "against other rules, and when its inputs are wrong.",
    ),
    (
        "Indian practice reviewer",
        "You are the Indian practice reviewer, working in a district hospital "
        "in India. Your question is whether a rule written from Western "
        "guidance survives contact with this population, this disease burden, "
        "and this referral network.",
    ),
)
"""The reviewing seats, in the order they are run.

Three is a judgement rather than a measurement: they are the three angles that
produced findings the others missed when the single critic was run over the
same rules. A fourth seat that duplicates an existing one costs a minute per
rule and adds nothing.
"""

CHAIR: Final[str] = (
    "You are the chair. You did not review the rule. Read the three reviews "
    "below and produce the single brief a clinician will read. Keep the "
    "disagreements: where two seats conflict, report both positions and say "
    "what the choice turns on."
)

DEFAULT_REFERRAL: Final[str] = "emergency physician"
"""Who to refer a rule to when the chair did not name a specialty.

Not "a clinician": the point of the field is to route a rule to the right desk,
and the emergency physician is the safest default for a triage rule because
every rule here fires in an emergency context.
"""


@dataclass(frozen=True)
class SeatReview:
    """What one seat wrote, and what was wrong with how it wrote it."""

    seat: str
    text: str
    model_version: str
    approving: bool
    proposed_thresholds: tuple[str, ...]
    truncated: bool

    @property
    def is_clean(self) -> bool:
        return not (self.approving or self.proposed_thresholds or self.truncated)


@dataclass(frozen=True)
class PanelResult:
    """Everything the panel produced for one rule.

    `review` is the record that goes on the rule. `seats` and `brief` are the
    reading material behind it, kept so a clinician can go from the summary to
    what a particular seat actually said.
    """

    rule_id: str
    rule_label: str
    seats: tuple[SeatReview, ...]
    brief: str
    review: AiReview

    @property
    def is_clean(self) -> bool:
        """Whether every seat wrote something readable without a warning."""
        return all(seat.is_clean for seat in self.seats)

    @property
    def still_blocks_release(self) -> bool:
        """Always true. Stated so no caller can read a panel run as clearance."""
        return True


def extract_concerns(brief: str, limit: int = 12) -> tuple[str, ...]:
    """The chair's numbered concerns, as lines.

    Parsed loosely rather than with a schema. A structured verdict would be
    tempting to consume automatically, and the moment anything consumes it a
    model's opinion has entered the clinical path. These are for a human to
    read; the parse only needs to be good enough to list them.
    """
    concerns: list[str] = []
    in_section = False
    for raw in brief.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("#"):
            in_section = "agree" in lowered or "disagree" in lowered
            continue
        if not in_section or not line:
            continue
        stripped = line.lstrip("0123456789.-* ").strip()
        if stripped and stripped != line:
            concerns.append(stripped)
        if len(concerns) >= limit:
            break
    return tuple(concerns)


def extract_referral(brief: str) -> str:
    """The specialty the chair named, or the default.

    Looked for under the heading rather than anywhere in the text, because the
    word "cardiology" appears in a cardiology rule's brief many times without
    being the referral.
    """
    lines = brief.splitlines()
    for index, raw in enumerate(lines):
        if not raw.strip().lower().lstrip("# ").startswith("refer to"):
            continue
        for following in lines[index + 1 : index + 4]:
            candidate = following.strip().lstrip("-*0123456789. ").strip()
            if candidate and not candidate.startswith("#"):
                return candidate.split(".")[0].strip()[:120] or DEFAULT_REFERRAL
    return DEFAULT_REFERRAL


def _run_seat(
    seat: str,
    instruction: str,
    brief: str,
    *,
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
) -> SeatReview:
    completion = provider.complete(
        prompt=f"{instruction}\n\n{brief}",
        system=prompt.body,
        spec=spec_for(prompt, model),
        prompt_version=prompt.version,
    )
    text = completion.text.strip()
    return SeatReview(
        seat=seat,
        text=text,
        model_version=completion.model_version,
        approving=find_approving_language(text),
        proposed_thresholds=find_proposed_thresholds(text),
        truncated=looks_truncated(text),
    )


def review_rule(
    rule: Rule[ActionT],
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
    *,
    vocabulary: frozenset[str] = frozenset(),
    passages: tuple[str, ...] = (),
    today: date | None = None,
    dossier_path: str | None = None,
) -> PanelResult:
    """Run the panel over one rule.

    Refuses a rule a clinician has already signed. Re-opening a verified rule
    is a clinical decision, and a model deciding to reopen one is the same
    category of mistake as a model closing one.
    """
    if not rule.verify_before_ship:
        raise ValueError(
            f"rule {rule.id} is already verified by {rule.verified_by!r}; the panel "
            f"reviews draft rules, and re-opening a signed rule is a clinical "
            f"decision rather than an automated one"
        )

    rule_brief = build_brief(rule, vocabulary=vocabulary, passages=passages)
    seats = tuple(
        _run_seat(
            seat, instruction, rule_brief, provider=provider, prompt=prompt, model=model
        )
        for seat, instruction in SEATS
    )

    transcript = "\n\n".join(
        f"=== {seat.seat} ===\n{seat.text}" for seat in seats
    )
    chair = provider.complete(
        prompt=f"{CHAIR}\n\n{rule_brief}\n\nTHE THREE REVIEWS:\n\n{transcript}",
        system=prompt.body,
        spec=spec_for(prompt, model),
        prompt_version=prompt.version,
    )
    brief = chair.text.strip()

    models = tuple(dict.fromkeys([*(s.model_version for s in seats), chair.model_version]))
    return PanelResult(
        rule_id=rule.id,
        rule_label=rule.label,
        seats=seats,
        brief=brief,
        review=AiReview(
            reviewed_on=today or date.today(),
            models=models,
            panel_version=PANEL_VERSION,
            concerns=extract_concerns(brief),
            refer_to=extract_referral(brief),
            dossier_path=dossier_path,
        ),
    )


def render(result: PanelResult) -> str:
    """The panel's output as one document, warnings first.

    A reviewer skimming thirty of these must not have to reach the bottom to
    learn that a seat invented a number in the middle.
    """
    lines = [
        f"# {result.rule_id} — {result.rule_label}",
        "",
        "**This rule remains blocked from release.** A panel review is not a "
        "verification: it records that the reading has been done and refers the "
        "rule to a clinician. Only a named, qualified person can clear "
        "`verify_before_ship`, and nothing below does.",
        "",
        f"Referred to: **{result.review.refer_to}**. "
        f"Reviewed {result.review.reviewed_on} by {', '.join(result.review.models)} "
        f"(panel {result.review.panel_version}).",
        "",
    ]

    for seat in result.seats:
        if seat.is_clean:
            continue
        problems = []
        if seat.approving:
            problems.append("used approving language")
        if seat.proposed_thresholds:
            listed = ", ".join(f"`{t}`" for t in seat.proposed_thresholds)
            problems.append(f"proposed unsourced thresholds ({listed})")
        if seat.truncated:
            problems.append(
                "was cut off before finishing, so what survives reads more "
                "one-sided than it was"
            )
        joined = "; ".join(problems)
        lines.extend([f"> **Warning — {seat.seat}** {joined}.", ""])

    lines.extend([result.brief, "", "---", "", "## The reviews behind this brief", ""])
    for seat in result.seats:
        lines.extend([f"### {seat.seat}", "", seat.text, ""])
    return "\n".join(lines)
