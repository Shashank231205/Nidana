# S2 Scribe

Ambient consultation documentation. The clinician consults, audio is captured,
a structured note comes out, and the clinician edits rather than writes.

**Status:** groundedness gate and completeness checking built. Phase P2.

## Why it matters

Consult produces a history. Scribe produces examination, assessment and plan.
Without Scribe the record is patient-reported only, which limits what every
service after it can do.

## What is built

`spine/schemas/note.py` — the note, its statements, its omissions, and the
signing gate. In the spine because Consult's handoff packet and Labs' routing
both read from it.

`agents/note_builder.py` — the groundedness gate. Every generated statement
carries the transcript span it came from with an audio offset, so a clinician
can click a line and hear the moment it was said. A claim whose span is not an
exact substring of the transcript is dropped.

`clinical/completeness.py` — flags clinically expected elements the
consultation did not cover, using the spine's rule engine with Scribe's
vocabulary.

`prompts/note_agent.md` — the note agent.

## What is not built

ASR and diarisation. Consult continuity, where a preceding Consult session
pre-populates the note. The edit loop. Discharge and referral letters. The
API surface. The eval harness bindings.

## The rules that govern it

**A model may only write what it heard.** A clinician may record what they
observed, and their statements carry examiner provenance. A generated
statement carrying anything but a transcript span is rejected by the schema.

**Nothing is filled by the system.** An omission is surfaced where the
clinician would fill it. They fill it or dismiss it with a reason; the
dismissal is recorded and the field stays empty.

**Advisory by default.** A documentation tool that blocks a clinician
mid-clinic gets switched off. Two rules hold a note out of the signed state
and even those can be dismissed with a reason.

**Signing is where a draft becomes clinical record.** A signed note names its
signer, and the schema refuses one that does not.

## Blocked

Which elements are clinically expected in which consultation is a clinical
judgement. All six completeness rules carry `verify_before_ship` and name
plausible checks rather than verified ones.

The edit loop is the highest-value training signal this product will generate,
and the mechanism must exist from the first real consultation or months of it
are lost. It is not built yet, and that is the most time-sensitive gap here.
