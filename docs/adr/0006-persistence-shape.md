# ADR 0006 — Patient linkage, audit subjects, and consent

Status: accepted
Date: 2026-09-06

## Context

Three problems in `docs/BUILD_SPEC.md` §4.

**Patient linkage.** The spec states `patients` joins to `sessions` by a nullable
FK, and concludes "a dump of the clinical tables is not a breach". If the FK
column lives on `sessions`, the clinical tables do contain a patient reference.
It is pseudonymous, which is the useful property, but the stated conclusion is
stronger than the design delivers.

**Audit subject.** `audit_events.session_id` is an FK to `sessions`. Rx and Labs
events are not sessions. The append-only audit log is shared spine per the PRD.

**Consent.** `docs/PRD.md` §5 requires explicit logged consent capture under the
DPDP Act. No table or column in `docs/BUILD_SPEC.md` §4 records it.

## Decision

**Linkage** moves to `patient_session_links` in a separate `restricted` Postgres
schema, holding `(patient_id, session_id)`. The `clinical` schema contains no
patient reference of any kind. A dump of `clinical` is then genuinely unlinkable,
and the claim in `docs/BUILD_SPEC.md` §4 becomes true.

**Audit** becomes polymorphic: `subject_type` and `subject_id` replace
`session_id`. Consult writes `subject_type='session'`. No shared `encounters`
parent table is introduced — modules 2–5 have not specified their subjects and an
abstraction invented now would be guesswork.

**Consent** gets `session_consents`, append-only, recording purpose, granted
state, the version of the consent text shown, and the timestamp. Withdrawal is a
new row, never an update, consistent with `CLAUDE.md` §2.6.

**Red flag firings** get a dedicated `red_flag_events` table rather than living
only in `audit_events.payload`. The M3 gate measures red flag sensitivity and the
M5 gate requires decision reconstruction from the log; both need these rows
queryable, not buried in JSON.

## Consequences

Four tables in the M1 migration that `docs/BUILD_SPEC.md` §4 does not list, and
one relocated. Two schemas instead of one, with grants differing between them.

Joining a patient to their clinical record now requires the `restricted` schema.
That is the point.

Deviates from `docs/BUILD_SPEC.md` §4 as written.
