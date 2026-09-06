# ADR 0005 — Rules compile against a predicate registry

Status: accepted
Date: 2026-09-06

## Context

`docs/PRD.md` §4.5 shows a red flag rule using atoms `chest_pain`,
`radiation_to_jaw_or_left_arm`, `age_over_40`, `diabetes`, `known_cad`.
`docs/BUILD_SPEC.md` §3 defines the field registry with `radiation` as a
multi-valued enum over `[none, jaw, left_arm, right_arm, back, epigastrium]`.

Nothing connects the two vocabularies. As specified, a rule may reference an atom
that corresponds to no field. Such a rule loads cleanly, evaluates to false
forever, raises nothing, and reports 100% pass on its negative tests.

A red flag rule that silently never fires is the most dangerous defect this
repository can contain. It is invisible to every gate in `docs/BUILD_SPEC.md` §7
except a positive vignette that happens to target it.

Modules 3–5 need the same engine: Rx for interaction and duplicate-therapy
checks, Labs for critical values, Forensics for injury-mechanism consistency.
Only the rule content and the action vocabulary differ.

## Options

1. Rules reference registry fields directly, no predicate layer.
2. Rules reference free-text atoms resolved at evaluation time.
3. Rules reference named predicates declared in `rules/predicates/`, resolved and
   validated at load time.

## Decision

Option 3.

- A predicate is a named, pure, declarative test over registry fields, defined in
  `rules/predicates/*.yaml`.
- Rule loading resolves every atom. An unresolved atom is a hard load failure
  naming the rule, the atom, and the file.
- A test asserts every atom in every shipped rule resolves. This test cannot be
  skipped.
- The engine is generic over a rule-set. A rule-set declares its own action
  vocabulary. Consult's `TERMINATE_EMERGENCY | ESCALATE_BAND | ANNOTATE` is
  Consult's vocabulary, not the engine's.

## Consequences

A typo in a rule fails the build instead of disabling a red flag.

Rule authoring gains one indirection: a new criterion may need a new predicate.
This is the intended cost — it forces each rule atom to have one definition
rather than one per rule.

The engine is reusable by modules 3–5 without modification. Only rule content and
action vocabulary are module-specific.

Extends `docs/PRD.md` §4.5 and `docs/BUILD_SPEC.md` §3, contradicting neither.
