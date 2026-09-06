# S5 Forensics

Medico-legal documentation. Tamper-evident.

**Status:** not started. Phase P5.

## What makes this one different

Forensics is **evidentially isolated**. It reads nothing from the shared record,
has its own access control, its own retention rules, and its own hash chain.
A medico-legal document must be defensible as an independent examination;
contamination from other sources is an attack surface in court.

It is also the only service whose primary consumer is a court rather than a
clinician, and the only one that can be built in parallel with another.

**The system structures examiner findings. It never generates them.** If the
examiner did not observe it, it cannot appear. No autocompleted wound
description, no inferred injury. Enforced structurally: every field traces to an
examiner input or it does not render.

## Layout

| Folder | Will hold |
|---|---|
| `clinical/` | protocol compliance and statutory mapping checks |
| `agents/` | phrasing only, never content |
| `prompts/` | prompts as files, loaded at runtime |
| `rules/` | protocol checklists and statutory criteria |
| `api/` | its HTTP routes, under its own access control |
| `eval/` | completeness against a reference MLC checklist |

## Blocking before build

Statutory mapping needs a lawyer, not only a clinician. Section numbering moved
from IPC to BNS in 2024 and must be verified directly against the current
statute. See `NIDANA.md` Part X.
