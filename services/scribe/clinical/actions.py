"""Scribe's rule action vocabulary.

Consult's rules can end a session. Scribe's cannot: a note that is incomplete
is still a note, and blocking a clinician mid-consultation to demand a field is
how a documentation tool gets switched off.

Every action here is advisory. The clinician decides.
"""

from __future__ import annotations

from enum import Enum


class NoteCheckAction(str, Enum):
    """What a firing completeness rule does.

    FLAG_OMISSION surfaces a clinically expected element the consultation did
    not cover — an allergy check before a new prescription, say. Advisory,
    never blocking.

    REQUIRE_BEFORE_SIGN holds the note out of the signed state until the
    clinician either fills the field or dismisses the flag with a reason. The
    dismissal is recorded; the field is never filled by the system.

    ANNOTATE records the observation for the record without surfacing it.
    """

    FLAG_OMISSION = "FLAG_OMISSION"
    REQUIRE_BEFORE_SIGN = "REQUIRE_BEFORE_SIGN"
    ANNOTATE = "ANNOTATE"
