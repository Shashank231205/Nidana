"""Consult's rule action vocabulary.

The engine is generic over this. Rx, Labs, Scribe, and Forensics declare their
own; these three are Consult's and mean nothing to them.
"""

from __future__ import annotations

from enum import Enum


class RedFlagAction(str, Enum):
    """What a firing red flag does to the session.

    TERMINATE_EMERGENCY ends the conversation immediately: the emergency
    instruction renders, facility lookup restricts to emergency-capable, and the
    session is flagged in the audit log. No further questions are asked.

    ESCALATE_BAND raises urgency and lets the history continue.

    ANNOTATE records the finding for the clinician without changing urgency or
    the conversation.
    """

    TERMINATE_EMERGENCY = "TERMINATE_EMERGENCY"
    ESCALATE_BAND = "ESCALATE_BAND"
    ANNOTATE = "ANNOTATE"
