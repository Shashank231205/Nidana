# Vignette cases

**This directory is empty, deliberately.**

A vignette carries a clinician-assigned reference band. That label is what
makes every number in the eval report mean something. An engineer writing one
produces a number that measures agreement with an engineer's guess.

`docs/BUILD_SPEC.md` section 8 lists the clinical reviewer as blocking and
unresolved:

> Who signs off red flag criteria and vignette reference labels? Without this
> the eval numbers are unfounded. Ideally two reviewers with a disagreement
> protocol.

Until that is answered, the harness runs against zero cases and reports zero
cases. That is the honest state.

## What goes here when a clinician is available

One YAML file per complaint family, each holding a `vignettes` list. The shape
is enforced by `services/consult/eval/vignettes.py`, which rejects a reference
band that names no reviewer.

```yaml
vignettes:
  - id: CP_001
    description: One line on what this case tests
    complaint_family: chest_pain
    age_years: 58
    sex: male
    turns:
      - patient: "Chest mein dard ho raha hai"
        language: hi-en
      - patient: "Kal raat se"
        language: hi-en
    reference_band: U2
    reference_specialty: cardiology
    expected_red_flags: [RF_ACS_001]
    reviewed_by: "Dr <name>, <registration number>"
    reviewed_on: "2026-01-01"
    source: "Written for this vignette set" 
    adversarial: [minimising]
```

## What the set needs

The PRD calls for 300 or more cases. Beyond volume, it needs coverage of the
patterns that break naive implementations, which belong in CI:

- Patients who minimise: "it's probably nothing, but"
- The red flag buried mid-sentence, after two irrelevant ones
- Answering a different question than the one asked
- Switching language mid-conversation
- Describing someone else's symptoms
- Colloquialisms used in their non-clinical sense: gas, acidity, BP, weakness
- The resolved deficit, where the patient now feels fine

MTS-Dialog, PriMock57 and ACI-Bench exist and should be assessed for fit, but
none is Indian or code-switched, so most of this set has to be constructed.
