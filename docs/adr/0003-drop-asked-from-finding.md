# ADR 0003 — "Not asked" is derived, not stored

Status: accepted
Date: 2026-09-06

## Context

`docs/BUILD_SPEC.md` §2 gives `Finding` an `asked: bool` field where
`asked=False` means "never asked", and states this must remain distinct from
`negated=True` ("asked and denied") because they carry different clinical
weight. That distinction is correct and must survive.

The same section requires every Finding to carry a source span, and states there
is no code path constructing a Finding from inference.

These cannot both hold. A field that was never asked has no patient utterance
behind it, so it has no span, so no valid Finding can represent it. Yet the
specified validator rule — reject `negated=True` where `asked=False` — implies
such rows exist.

Any resolution that keeps `asked=False` as a stored Finding requires making
`source_span` optional for some rows. That reopens the exact hole ADR 0002
closes.

## Options

1. Make `source_span` optional when `asked=False`.
2. Keep `asked`, store un-asked fields as a separate row type.
3. Remove `asked` from `Finding` and derive "not asked" from absence.

## Decision

Option 3.

- **Asked and denied** is a Finding with a real span (`"no, it doesn't go
  anywhere"`) and `negated=True`.
- **Asked, answered** is a Finding with a span and `negated=False`.
- **Never asked** is the absence of any Finding for that field. Computed by
  `Sufficiency` as registry-required-fields minus fields present in the record.

## Consequences

The clinical distinction is preserved exactly, and it is now impossible to
represent it wrongly. The span invariant has no exceptions.

Consumers asking "was this asked?" query the record, not a flag. `Sufficiency`
already carries `missing`, which is that answer.

One case needs care: a question asked and not answered — the patient changed the
subject. That is not a Finding and not "denied"; it is still missing, and the
intake agent re-asks it. The prompt already specifies this behaviour.

Deviates from `docs/BUILD_SPEC.md` §2 as written.
