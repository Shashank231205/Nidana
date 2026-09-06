# ADR 0004 — What "the critic can never lower urgency" actually enforces

Status: accepted
Date: 2026-09-06

## Context

`CLAUDE.md` §2.3 and `docs/ENGINEERING_RULES.md` §4.2 require the safety critic's
asymmetry to be enforced "in the type system, not in a prompt".

Python's type system cannot do this. A function annotated `-> Band` may return
any `Band`. The claim as written is not implementable, and leaving it in place
means the strongest safety invariant in the product is believed to be enforced
when it is not.

Separately, `docs/BUILD_SPEC.md` §2 writes the ordering as
`U1 < U2 < U3 < U4 < U5 (U1 most urgent)` and defines the critic as
`min(current, proposed)` by urgency. This is self-consistent but inverts twice:
`<` reads as ordinal while `min` reads as most-urgent. It invites a
de-escalation bug during any future refactor.

## Options

1. Leave as specified and rely on review.
2. Order the enum by urgency so `max()` is the escalating operation.
3. Remove ordering comparison entirely and expose one named operation.

## Decision

Option 3, with option 2's naming.

- `Band` carries an explicit `urgency` rank where U1 is highest. Raw `<` and `>`
  between bands are not defined; attempting them raises.
- The critic returns `NoChange | RaiseTo(band)`. `RaiseTo` validates on
  construction that the target is strictly more urgent than the current band.
- `escalate_only(current, proposed) -> Band` is the only function in the codebase
  that writes a band onto a record.
- A property test enumerates all 25 ordered band pairs and asserts the result is
  never less urgent than `current`.

## Consequences

The guarantee is real and exhaustively tested rather than type-asserted and
unenforced. Exhaustive here means literally exhaustive: the input domain is 25
pairs.

`CLAUDE.md` §2.3 and `docs/ENGINEERING_RULES.md` §4.2 are inaccurate as written
and should be amended to "enforced by a single constructor and an exhaustive
test" once the owner confirms.

Deviates from `docs/BUILD_SPEC.md` §2 and `CLAUDE.md` §2.3 as written.
