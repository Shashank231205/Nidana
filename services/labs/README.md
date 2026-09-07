# S4 Labs

Diagnostic report interpretation. Indian patients order their own tests and
receive a PDF they cannot read. Labs parses it, explains it in context, tracks
it over time, and says who to take it to.

**Status:** result shapes and critical value detection built. Phase P4.

## What is built

`spine/schemas/lab.py` — results, reference ranges, reports, and trends. In the
spine because Consult reads a result when triaging, Rx reads renal and hepatic
status before checking a prescription, and Scribe records results discussed in
a consultation.

`clinical/critical_values.py` — deterministic critical value detection with the
same release gate as Consult red flags: 100% sensitivity.

## What is not built

Multi-format parsing. Contextual interpretation. The patient explanation.
Specialty routing, which reuses Consult's resolver. The API.

## The rules that govern it

**The printed reference range is authoritative.** Ranges are age, sex and
method dependent, and a laboratory's own range for its own assay beats any
internal table. A range from a table is marked as a fallback.

**A result with no range is UNKNOWN, not NORMAL.** Nobody judged it, and
reporting it as normal would be a claim no one made. Unassessed results are
listed separately rather than hidden.

**Critical is not the same as abnormal.** A potassium can be outside its range
without being critical, and a value can be critical while sitting inside a
range printed for a different population. The two answer different questions,
so critical thresholds are their own table and override range classification.

**A unit mismatch never fires a threshold, and is reported loudly.** Comparing
mg/dL against mmol/L produces a nonsense verdict, but silently skipping the
check is a missed critical value — which is the one failure this module exists
to prevent.

**No threshold lives in code.** Every number is in `rules/critical_values/`,
cited and versioned, and a release build refuses to start while any is
unverified.

## Blocked

**Every threshold in the shipped file is a placeholder.** The numbers are
structural and exist to fix the shape. A wrong threshold here is more dangerous
than a missing one: set too wide, it reports 100% sensitivity against a
vignette set that never tests the gap. A clinician must set each one from the
laboratory's own assay and the current published source.

**Assay dependence is unresolved.** Troponin in particular varies enough
between assays that a generic threshold may be meaningless, and whether the
threshold belongs here or per-laboratory is a clinical decision.
