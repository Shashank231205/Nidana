# S5 Forensics

Medico-legal documentation. Tamper-evident.

**Status:** examination shapes and custody chain built. Phase P5.

## What makes this one different

**Evidentially isolated.** It reads nothing from the shared record, has its own
access control and its own chain. A medico-legal document must be defensible as
an independent examination; contamination from other sources is an attack
surface in cross-examination. The report shape holds no reference to a Consult
session, a note, or a prescription, and a test asserts that.

**The consumer is a court, not a clinician.** That changes what "good" means.
A precise wound-age estimate is worse than a range the examiner can justify,
because a court will test it.

**The system structures examiner findings and never generates them.** If the
examiner did not observe it, it cannot appear. Every field traces to a signed
examiner entry, enforced by the schema rather than trusted.

## What is built

`spine/schemas/forensic.py` — injuries, photographs, and the report, with the
gaps that block finalisation.

`clinical/custody.py` — the custody chain, reusing the spine's hash chain.

## What is not built

Statutory classification support. The MCCD cause-of-death chain. Age estimation
by radiographic assessment. The sexual assault protocol compliance checklist.
The API and its access control.

## The rules that govern it

**A missing field is listed, never filled.** A missing field is exactly what
gets exploited under cross-examination, so the examiner sees the list before
signing rather than a lawyer finding it years later.

**A measurement names what it was measured from.** A distance from an unstated
landmark cannot be reproduced or challenged.

**A photograph reference must resolve.** A citation to evidence that is not
attached cannot be produced in court.

**A scale reference is required, and a photograph without one is kept anyway.**
It still evidences appearance, and discarding it would lose that. The report
lists which lack a scale.

**Findings are framed as consistent-with, never as a conclusion.** What the
injuries are *not* consistent with is recorded too, and is often the more
useful half.

**The custody chain logs reads as well as writes.** A record read by someone
with no role in the case is a chain-of-custody problem whether or not they
changed anything.

**An amendment states its reason.** A correction with no reason cannot be
distinguished from tampering when the record is read back years later.

## Blocked

**Statutory classification needs a lawyer, not a clinician.** Simple versus
grievous hurt is a legal test with medical inputs, and section numbering moved
from IPC to BNS in 2024. Nothing statutory is implemented rather than
implemented against numbers that may have changed.

**Admissibility is unresolved.** Whether output from this service is admissible
in any jurisdiction, and what that requires, is a legal question that has not
been asked.

**The sexual assault module is protocol compliance only.** Consent documented,
statutory steps followed, kit sealed and logged, POCSO obligations met where
the patient is a minor. Nothing generative touches the content of that
examination, because protocol deviation is what gets these cases dismissed and
content generation is not the useful feature.
