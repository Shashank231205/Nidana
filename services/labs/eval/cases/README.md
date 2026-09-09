# Groundedness case sets

`groundedness.json` in this directory is read by
`scripts/run_groundedness_eval.py`. It is not committed and does not exist yet.

## Why there is no case set here

A case is a source document — a prescription, a lab report, a dictation, a
consultation transcript. Writing one means writing clinical content, and
CLAUDE.md §1 forbids that: a plausible-looking fabricated prescription is
exactly the kind of thing that ends up in a demo, then in a screenshot, then in
someone's understanding of what this system does.

Real cases come from de-identified documents a deployment already holds.

## Format

```json
[
  {
    "case_id": "rx-001",
    "source": "the full text the agent reads",
    "expected_spans": ["a phrase a reference says is in the source"],
    "note": "optional, for a human reading the set"
  }
]
```

`expected_spans` is optional. Without it a case still scores **fabrication** —
which is the number a gate turns on — and is counted as unscored for recall, so
a reader can see how much of the set is measuring only half the property.

## What the eval measures

Every claim these agents produce carries a span, and that span either occurs in
the source or it does not. That question needs no clinician, which is why this
can run before the vignette sets exist.

It does **not** measure whether the agent found the right things. A perfect
score shows the agent invented nothing; it does not show the output is useful.
