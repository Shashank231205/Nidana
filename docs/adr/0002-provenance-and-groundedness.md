# ADR 0002 — Provenance as verified offsets, not a free string

Status: accepted
Date: 2026-09-06

## Context

`docs/BUILD_SPEC.md` §2 types `Finding.source_span` as `str`, described as "the
patient's own words, verbatim".

The M2 acceptance gate is "fabrication rate zero on the golden transcript set,
structurally enforced rather than measured". A free-text string cannot be
structurally enforced. A model that paraphrases the patient into that field
produces a Finding that passes every validator in the system. The invariant is
then a convention, and `CLAUDE.md` §2.2 states it is not one.

Separately, Scribe grounds statements in transcript audio, Rx in OCR'd
prescription text, Labs in a parsed report. All four need the same mechanism.

## Options

1. Keep `str`, measure fabrication in eval.
2. Keep `str`, add a similarity check at validation time.
3. Store character offsets into the persisted source text and verify the span is
   an exact substring.

## Decision

Option 3. `Provenance` carries `source_type`, `source_id`, `char_start`,
`char_end`, and `text`. Validation asserts
`source_text[char_start:char_end] == text`.

`source_type` is an open enum: `patient_utterance` for Consult, with
`transcript_segment`, `document_span`, and `ocr_region` reserved for modules 2–5.

## Consequences

A paraphrase fails validation instead of passing unnoticed. The M2 gate becomes
achievable as written rather than aspirational.

Verification requires the source text to be available to the validator. Findings
are therefore validated at the point of extraction, where the utterance is in
hand, not reconstructed later from the database alone.

Offsets are over the stored raw utterance, in Python string indices over the
original script. No normalisation, no transliteration, no case folding — the
stored text is what the patient sent. This holds for code-switched input and for
ASR output in M4 without change.

`findings.source_span` in the database becomes `provenance jsonb NOT NULL`
rather than `source_span text NOT NULL`. The NOT NULL invariant from
`docs/BUILD_SPEC.md` §4 is preserved.

Deviates from `docs/BUILD_SPEC.md` §2 and §4 as written.
