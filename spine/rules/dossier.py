"""Assembling what a clinician needs in order to sign a rule off.

Thirty red flag rules and ten critical thresholds carry
`verify_before_ship: true`, and a release build refuses to start while any of
them does. Clearing that flag means a named, qualified clinician has read the
criterion and accepted responsibility for it. No amount of retrieval is that
signature, and nothing in this module sets the flag.

What it does is remove the part of their work that is not judgement. A
reviewer facing thirty rules currently starts by finding the guideline,
finding the passage inside it, and working out what the guideline assumed that
this system cannot supply. That is hours of reading before the first decision.
This assembles it: the rule, its criteria in the predicate vocabulary, the
passages the local corpus actually contains, and the questions that remain.

Two design consequences follow from the flag not being ours to clear.

The dossier carries passages, never a recommendation. A generated sentence
saying a criterion "aligns with NICE guidance" is a claim wearing a citation,
and a reviewer skimming thirty of them would reasonably read it as a finding.
Every passage here is a verbatim span from the corpus with its citation
attached, exactly as `spine.knowledge.retrieval` returns it.

And silence is reported as silence. A rule the corpus cannot speak to gets an
empty dossier saying so, rather than the least-irrelevant paragraph in the
index. The corpus is IPHS facility standards; most red flag criteria are not
in it, and a dossier implying otherwise would be worse than no dossier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic

from spine.knowledge.index import KnowledgeIndex, Passage
from spine.knowledge.retrieval import Answer, RetrievalUnavailableError, ask
from spine.schemas.rule import ActionT, Rule


@dataclass(frozen=True)
class Evidence:
    """One retrieved passage, kept with the question that found it.

    The question is carried because a reviewer needs to judge whether the
    passage answers it. A passage detached from its query reads as though the
    corpus endorsed the rule.
    """

    question: str
    passage: Passage

    @property
    def citation(self) -> str:
        return self.passage.citation


@dataclass(frozen=True)
class Dossier(Generic[ActionT]):
    """Everything assembled for one rule, and nothing decided about it."""

    rule: Rule[ActionT]
    evidence: tuple[Evidence, ...]
    questions_asked: tuple[str, ...]
    corpus_silent: bool
    retrieval_failed: bool = False

    @property
    def rule_id(self) -> str:
        return self.rule.id

    @property
    def still_needs_verification(self) -> bool:
        """Always true for an unverified rule. Retrieval does not change it.

        Stated as a property rather than left implicit so that a caller
        rendering a dossier cannot present one as a completed review.
        """
        return self.rule.verify_before_ship

    @property
    def open_questions(self) -> tuple[str, ...]:
        """What a reviewer must decide, which no passage supplies.

        These are the four recurring gaps between a published guideline and
        this system, recorded per rule because each has a different answer:
        the guidelines assume an examiner, they assume tests this service does
        not have, they were mostly written for other populations, and none of
        them knows what this system does when a rule fires.
        """
        questions = [
            f"Do the criteria translate? {self.rule.label} is decided here from "
            f"reported history alone: {', '.join(sorted(self.rule.atoms))}.",
            "How much wider must this be than the source guideline, given that "
            "the guideline assumed examination findings or tests this service "
            "does not have?",
            "Does the source apply to this population, or does local "
            "epidemiology change the threshold?",
            f"Is {self.rule.action} the right action, which no guideline states "
            f"because none knows what this system does next?",
        ]
        if self.corpus_silent:
            questions.append(
                "The local corpus holds nothing on this rule. Which guideline "
                "should be relied on, and should it be added to the corpus?"
            )
        return tuple(questions)


def questions_for(rule: Rule[ActionT]) -> tuple[str, ...]:
    """The queries to put to the corpus for one rule.

    Built from the rule's own label and criteria rather than from a hand-written
    list, so a rule added later is covered without anyone remembering to add
    its questions. The label carries the clinical concept; the atoms carry the
    findings the criteria turn on.
    """
    label = rule.label.lower()
    queries = [label, f"{label} referral criteria", f"{label} emergency management"]
    readable = sorted(atom.replace("_", " ") for atom in rule.atoms)
    if readable:
        queries.append(f"{label}: {', '.join(readable[:6])}")
    return tuple(queries)


def build_dossier(
    rule: Rule[ActionT],
    index: KnowledgeIndex,
    *,
    per_question: int = 2,
) -> Dossier[ActionT]:
    """Assemble the dossier for one rule.

    A retrieval outage is recorded rather than raised. A reviewer working
    through thirty rules should get twenty-nine dossiers and one that says the
    embedding model was unreachable, not an exception on the ninth.
    """
    questions = questions_for(rule)
    evidence: list[Evidence] = []
    seen: set[str] = set()
    failed = False

    for question in questions:
        try:
            answer: Answer = ask(index, question, limit=per_question)
        except RetrievalUnavailableError:
            failed = True
            break
        for passage in answer.passages:
            # The same passage answers several of a rule's questions, and
            # repeating it inflates a dossier without adding evidence.
            fingerprint = f"{passage.citation}::{passage.text[:120]}"
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            evidence.append(Evidence(question=question, passage=passage))

    return Dossier(
        rule=rule,
        evidence=tuple(evidence),
        questions_asked=questions,
        corpus_silent=not evidence and not failed,
        retrieval_failed=failed,
    )


def render(dossier: Dossier[ActionT]) -> str:
    """One dossier as Markdown, for a reviewer to read away from a terminal.

    The verification status leads, because the single most likely misreading
    of this document is that it constitutes a review.
    """
    rule = dossier.rule
    lines = [
        f"## {rule.id} — {rule.label}",
        "",
        f"**Status: unverified.** {rule.action}. "
        f"This dossier is retrieved evidence, not a review, and does not clear "
        f"`verify_before_ship`."
        if dossier.still_needs_verification
        else f"**Status: verified on {rule.verified_on}.** {rule.action}.",
        "",
        "### Criteria as encoded",
        "",
    ]
    for clause in rule.any_of:
        lines.append(f"- {' AND '.join(clause.all_of)}")
    if rule.modifiers.escalate_if:
        lines.append(f"- escalates on: {', '.join(rule.modifiers.escalate_if)}")
    lines.extend(["", f"Current source line: {rule.source}", ""])
    if rule.notes:
        lines.extend([f"Existing note: {rule.notes}", ""])

    lines.extend(["### What the local corpus holds", ""])
    if dossier.retrieval_failed:
        lines.append(
            "Retrieval was unavailable when this was built. Start Ollama and "
            "rebuild before relying on the absence of evidence below."
        )
    elif dossier.corpus_silent:
        lines.append(
            "Nothing. The corpus does not cover this rule, which is expected "
            "for most clinical criteria: it holds facility standards. The "
            "guideline this rule needs is not in it."
        )
    else:
        for item in dossier.evidence:
            lines.extend(
                [
                    f"> {item.passage.text.strip()}",
                    "",
                    f"— {item.citation} (retrieved for: {item.question})",
                    "",
                ]
            )

    lines.extend(["### What a reviewer must decide", ""])
    lines.extend(f"{n}. {q}" for n, q in enumerate(dossier.open_questions, start=1))
    lines.extend(
        [
            "",
            "To sign off: set `verify_before_ship: false`, record `verified_on` "
            "and the reviewer, and replace the `source:` line with what was "
            "actually relied on.",
            "",
        ]
    )
    return "\n".join(lines)
