# S3 Rx

Prescription intelligence. Reads a handwritten prescription, resolves what the
drug is, checks it against everything else the patient takes, and surfaces the
generic equivalent.

**Status:** medication shapes and safety checks built. Phase P3.

## Why it belongs in a platform

A single prescription cannot be checked in isolation, and every standalone tool
tries to. Duplicate therapy — two prescribers, same molecule, different brand
names — is common, dangerous, and invisible to a patient reading two labels.
Catching it needs the patient's full list from every source, which is what the
shared record provides and a one-prescription tool cannot.

## What is built

`spine/schemas/medication.py` — the medication shapes. In the spine because
Scribe reads the list when documenting, Labs when interpreting a result, and
Consult when triaging.

`clinical/checks.py` — duplicate therapy, allergy, unresolved lines, and
pregnancy-status gaps. Deterministic throughout.

## What is not built

OCR. Brand-to-molecule resolution. Interaction checking. Dose range checking.
Generic substitution and the price delta. The adherence schedule. The API.

## The rules that govern it

**No model decides whether two drugs interact.** Every check here is a rule
over a molecule list.

**Rx never computes a dose.** It range-checks a stated dose and flags
implausibility for a human. That is a different thing and it stays the right
side of the regulatory boundary.

**A refusal is a success state.** Below the confidence threshold Rx refuses
rather than guesses. A refusal a pharmacist resolves is safer than a confident
wrong molecule they do not question, so `RESOLVED` requires a molecule,
`AMBIGUOUS` requires more than one candidate, and a refusal may not still
assert an answer.

**An unresolved line blocks dispensing.** Not because it is dangerous in
itself, but because every other check on the list ran without it.

**What was written is kept beside what it resolved to.** A pharmacist checks
the resolution rather than trusting it, and they work from the prescription in
front of them.

## Blocked

**Interaction checking needs a dataset this product cannot get for free.** The
checker is built and wired — `clinical/interactions.py`, source-agnostic,
reporting what it did *not* check as prominently as what it did. What is
missing is data.

Nidana is commercial, which rules out every free source: DDInter is
CC BY-NC-SA and non-commercial only, RxNorm stopped carrying interactions when
NLM discontinued that API in January 2024, and the prediction datasets must not
be used at all — a predicted interaction shown to a pharmacist with the weight
of a documented one is the failure this service exists to avoid.

What remains is a paid licence: DrugBank, First Databank or Medi-Span, or
DDInter with written permission. `rules/interactions/CANDIDATES.md` sets out
each, and what adopting one would involve — one loader, mapping that vendor's
severity grades onto `Severity`.

With no dataset configured, `/v1/checks` reports
`interaction_checking_available: false` rather than an empty findings list. An
empty list reads as "no interactions found", which is a different statement
from "interactions were not checked" and the more dangerous one.

**Brand-to-molecule resolution is done.** `scripts/build_brand_index.py` builds
it from the MIT-licensed Indian Medicine Dataset: 253,973 products in, 175,953
brands out, zero rows unparsed. The index is a derived artefact and is
gitignored, like the knowledge index.

**Allergy class matching is not attempted.** That a penicillin allergy covers
amoxicillin is a fact about drug classes, and the current check matches on
substrings, which will miss it. Named here rather than approximated.
