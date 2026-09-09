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

**Interaction checking needs a dataset, and the dataset is a licence
decision.** The checker itself is built and wired — `clinical/interactions.py`,
source-agnostic, reporting what it did *not* check as prominently as what it
did. What is missing is data. DDInter has the best of it and is CC BY-NC-SA
4.0: usable in a non-commercial deployment, not in a commercial one without
permission. `rules/interactions/CANDIDATES.md` records what each option
implies, including why the prediction datasets must not be used here.

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
