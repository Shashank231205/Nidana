"""The patient output filter.

No condition name reaches patient-facing output. Not in any language, not at any
confidence, not hedged.

This is enforced here rather than requested in a prompt, because a prompt
instruction is a tendency and this is an invariant. The filter runs on every
patient-facing string the system produces, including ones a model wrote.

Two mechanisms, deliberately:

`redact` removes what it finds, for text assembled from templates where a stray
term is a bug worth fixing quietly.

`assert_clean` refuses, for model output. A model that names a condition has
misunderstood its job, and silently redacting it would hide that.
"""

from __future__ import annotations

import re
from typing import Final

BLOCKED_TERMS: Final[frozenset[str]] = frozenset(
    {
        "acute coronary syndrome",
        "myocardial infarction",
        "heart attack",
        "angina",
        "stemi",
        "nstemi",
        "aortic dissection",
        "pulmonary embolism",
        "deep vein thrombosis",
        "heart failure",
        "arrhythmia",
        "atrial fibrillation",
        "stroke",
        "cerebrovascular accident",
        "transient ischaemic attack",
        "transient ischemic attack",
        "subarachnoid haemorrhage",
        "subarachnoid hemorrhage",
        "intracranial haemorrhage",
        "intracranial hemorrhage",
        "meningitis",
        "encephalitis",
        "brain tumour",
        "brain tumor",
        "temporal arteritis",
        "glaucoma",
        "retinal detachment",
        "appendicitis",
        "cholecystitis",
        "pancreatitis",
        "peritonitis",
        "bowel obstruction",
        "perforation",
        "ectopic pregnancy",
        "miscarriage",
        "placental abruption",
        "pre-eclampsia",
        "preeclampsia",
        "eclampsia",
        "testicular torsion",
        "sepsis",
        "septicaemia",
        "septicemia",
        "meningococcaemia",
        "diabetic ketoacidosis",
        "ketoacidosis",
        "hypoglycaemia",
        "hypoglycemia",
        "diabetes",
        "tuberculosis",
        "dengue",
        "malaria",
        "typhoid",
        "pneumonia",
        "asthma",
        "copd",
        "cancer",
        "carcinoma",
        "tumour",
        "tumor",
        "malignancy",
        "ulcer",
        "gastritis",
        "hepatitis",
        "cirrhosis",
        "kidney failure",
        "renal failure",
        "anaemia",
        "anemia",
        "depression",
        "psychosis",
        "schizophrenia",
        "bipolar",
    }
)
"""Condition names that must never reach a patient.

Not exhaustive and cannot be. It covers what the red flag rules detect plus the
conditions a model is most likely to volunteer, which is where the risk
concentrates. The refusal in `assert_clean` is the real guarantee; this list
catches the common cases loudly rather than pretending to be complete.
"""

_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, BLOCKED_TERMS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

REDACTION: Final[str] = "[removed]"


class ConditionNameLeakError(ValueError):
    """Raised when patient-facing text names a condition."""


def find_blocked_terms(text: str) -> tuple[str, ...]:
    """Every blocked term in `text`, lowercased, in order of appearance."""
    return tuple(match.group(0).lower() for match in _PATTERN.finditer(text))


def is_clean(text: str) -> bool:
    return not _PATTERN.search(text)


def redact(text: str) -> str:
    """Replace every blocked term with a marker.

    For text the system assembled itself. A stray term here is a template bug,
    not a model misbehaving.
    """
    return _PATTERN.sub(REDACTION, text)


def assert_clean(text: str, origin: str) -> str:
    """Return `text` unchanged, or refuse if it names a condition.

    For model output. Redacting silently would leave a model that thinks
    naming conditions is acceptable, and the next thing it names may not be on
    the list.
    """
    found = find_blocked_terms(text)
    if found:
        unique = sorted(set(found))
        raise ConditionNameLeakError(
            f"patient-facing text from {origin} names {len(unique)} condition(s): "
            f"{', '.join(unique)}. Patient output carries urgency, specialty, findings "
            f"and return criteria, never a condition name. Fix the prompt or the "
            f"template that produced this; do not route around the filter"
        )
    return text
