"""Note completeness checking.

Flags clinically expected elements a consultation did not cover. Advisory: the
system surfaces the gap and the clinician decides. It never fills the field.

Reuses the spine's rule engine unchanged. What differs from Consult is the
vocabulary — these predicates test the note's own shape rather than a patient's
symptoms — and the action set, where nothing terminates anything.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from services.scribe.clinical.actions import NoteCheckAction
from spine.rules.engine import Firing, evaluate_rule_set
from spine.schemas.finding import Finding
from spine.schemas.note import ClinicalNote, NoteSection, Omission
from spine.schemas.predicate import Predicate
from spine.schemas.primitives import Confidence, Sex
from spine.schemas.provenance import ExaminerEntry
from spine.schemas.record import Demographics, Record, SubjectType
from spine.schemas.rule import RuleSet

RULE_SECTIONS: dict[str, NoteSection] = {
    "NC_ALLERGY_001": NoteSection.PLAN,
    "NC_FOLLOWUP_002": NoteSection.FOLLOW_UP,
    "NC_EXAMINATION_003": NoteSection.EXAMINATION,
    "NC_PREGNANCY_004": NoteSection.PLAN,
    "NC_ASSESSMENT_005": NoteSection.ASSESSMENT,
    "NC_SUBJECTIVE_006": NoteSection.SUBJECTIVE,
}
"""Which section a flagged omission belongs to.

So the clinician sees the gap where they would fill it, rather than in a list
away from the note.
"""

REPRODUCTIVE_AGE_FLOOR = 12
REPRODUCTIVE_AGE_CEILING = 55
"""Bounds for pregnancy-gated checks.

A cohort boundary, not a clinical threshold. It decides whether a question is
asked, never what the answer means.
"""


def _fact(field: str, value: bool, encounter_id: UUID) -> Finding:
    """A note-shape fact, as a Finding the engine can evaluate.

    Provenance is an ExaminerEntry rather than a transcript span because the
    fact is about the note rather than about anything anyone said. The note's
    own structure is the source.
    """
    return Finding(
        field=field,
        value=value,
        provenance=ExaminerEntry(
            source_id=str(encounter_id),
            examiner_id="note_completeness",
            text=f"{field}={value}",
            field_path=field,
        ),
        confidence=Confidence.HIGH,
        negated=not value,
    )


def _is_reproductive_age(demographics: Demographics) -> bool:
    """Whether pregnancy-gated checks apply.

    Unknown age or sex returns False, so the check is not asked rather than
    asked wrongly. That is the opposite of Consult's paediatric handling, and
    deliberately so: a missed question here is a documentation gap, while a
    missed paediatric modifier there is a clinical one.
    """
    if demographics.sex is not Sex.FEMALE or demographics.age_years is None:
        return False
    return REPRODUCTIVE_AGE_FLOOR <= demographics.age_years <= REPRODUCTIVE_AGE_CEILING


def as_record(
    note: ClinicalNote,
    demographics: Demographics,
    *,
    prescription_issued: bool,
    allergy_documented: bool,
    pregnancy_documented: bool,
) -> Record:
    """Describe a note as a record the rule engine can evaluate.

    The three flags are passed in rather than derived, because whether a
    prescription was issued is a fact about the consultation that the note
    alone cannot always establish.
    """
    encounter_id = note.encounter_id
    shape = {
        "has_subjective": bool(note.in_section(NoteSection.SUBJECTIVE)),
        "has_examination": bool(note.in_section(NoteSection.EXAMINATION)),
        "has_assessment": bool(note.in_section(NoteSection.ASSESSMENT)),
        "has_plan": bool(note.in_section(NoteSection.PLAN)),
        "has_follow_up": bool(note.in_section(NoteSection.FOLLOW_UP)),
        "has_investigations": bool(note.in_section(NoteSection.INVESTIGATIONS)),
        "prescription_issued": prescription_issued,
        "allergy_documented": allergy_documented,
        "pregnancy_documented": pregnancy_documented,
        "female_reproductive_age": _is_reproductive_age(demographics),
    }
    return Record(
        subject_type=SubjectType.ENCOUNTER,
        subject_id=encounter_id if isinstance(encounter_id, UUID) else uuid4(),
        demographics=demographics,
    ).with_findings(*(_fact(field, value, encounter_id) for field, value in shape.items()))


def _to_omission(firing: Firing[NoteCheckAction]) -> Omission:
    return Omission(
        rule_id=firing.rule_id,
        label=firing.label,
        section=RULE_SECTIONS.get(firing.rule_id, NoteSection.PLAN),
        blocking=firing.action == NoteCheckAction.REQUIRE_BEFORE_SIGN.value,
    )


def check(
    record: Record,
    rule_sets: tuple[RuleSet[NoteCheckAction], ...],
    predicates: dict[str, Predicate],
) -> tuple[Omission, ...]:
    """Every completeness rule that fired, as omissions.

    Pure. Record and rules in, omissions out.
    """
    return tuple(
        _to_omission(firing)
        for rule_set in rule_sets
        for firing in evaluate_rule_set(rule_set, record, predicates)
    )
