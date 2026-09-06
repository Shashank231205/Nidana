# ADR 0001 — Shared record envelope with per-module context

Status: accepted
Date: 2026-09-06

## Context

`docs/BUILD_SPEC.md` §2 defines `Record` with `complaint_family`, `is_proxy`, and
`sufficiency` as top-level fields. Those three are Consult concepts. The PRD states
that the record is the product and modules 2–5 are surfaces on it, so the record
type is shared spine.

Scribe produces findings for an encounter, not a complaint family. Labs produces
them for a report. Neither has a sufficiency check against a complaint-family
field registry. If those fields stay top-level, every later module either carries
fields that are meaningless to it or defines its own record type, which is the
outcome the PRD explicitly forbids.

## Options

1. Keep `Record` as specified. Modules 2–5 define their own record types.
2. Keep `Record` as specified but make Consult fields optional.
3. Split into a shared envelope plus a per-module context object.

## Decision

Option 3. `Record` holds what every module has: subject, findings, demographics,
comorbidities, medications, allergies. Module-specific state lives in a named
context object on the record — `consult: ConsultContext` for Module 1, with
`scribe`, `rx`, `labs`, `forensics` slots added by their own PRDs.

`ConsultContext` holds `complaint_family`, `is_proxy`, `pregnancy_status`,
and `sufficiency`.

## Consequences

Module 1 code reads `record.consult.complaint_family` rather than
`record.complaint_family`. That is the whole cost.

Downstream modules add a context class and touch nothing shared. A record
produced by Consult is directly consumable by Rx, which needs the medication
and allergy lists and nothing else from it.

Deviates from `docs/BUILD_SPEC.md` §2 as written.
