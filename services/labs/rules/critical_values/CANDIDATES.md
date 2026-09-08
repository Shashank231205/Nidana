# Critical value candidates, for clinician review

**Nothing in this file is in force.** `core.yaml` still holds structural
placeholders and every threshold there still carries `verify_before_ship: true`.
This is research to shorten the reviewing clinician's work, not a substitute for
it.

## What the literature actually says

The first finding is the one that matters most, and it is not a number.

> "There is no internationally or nationally agreed list of laboratory tests
> that warrant assignment of critical limits, and even for those laboratory
> tests that most agree warrant critical limits there is lack of consensus on
> the critical limits that should be applied."
>
> — *Critical values in laboratory medicine*, Acute Care Testing

So there is no authority to copy from. Published values are institutional
policies and survey medians, and they disagree with each other by margins wide
enough to change a clinical decision: reported low-potassium limits span
2.5–3.0 mmol/L, low-sodium 110–130 mmol/L, low-haemoglobin 6–8 g/dL.

This is why `verify_before_ship` cannot be cleared by research. The reviewing
clinician is not looking up a published constant. They are making a local
decision against their own laboratory's assay and their own hospital's
escalation pathway, and that decision is theirs to sign.

## Survey medians

From a 2026 survey of US hospital point-of-care critical limits
(PMC13115040). The hospital count is how many reported that analyte; a low
count means the median rests on few institutions.

| Analyte | Low | High | Unit | Hospitals | Reported spread |
|---|---|---|---|---|---|
| Potassium | 3.0 | 6.0 | mmol/L | 20 | low 2.5–3.0 |
| Sodium | 126 | 155 | mmol/L | 18 | low 110–130 |
| Glucose | 50 | 450 | mg/dL | 73 | low 40–70, high 200–600 |
| Calcium | 6.6 | 12.9 | mg/dL | 11 | ionised low 0.50–1.00 mmol/L |
| Haemoglobin | 6.6 | — | g/dL | 23 | low 6–8 |

CAP participant surveys are quoted elsewhere with tighter bounds — potassium
<2.5 or >6.5, sodium <120 or >160, glucose <2.8 or >30.0 mmol/L — which is
itself an illustration of the disagreement rather than a resolution of it. Note
the unit change: CAP quotes glucose in mmol/L where the survey above uses
mg/dL, and Indian laboratories generally report mg/dL.

## Not researched

`core.yaml` also holds platelet count, INR, creatinine, white cell count and
troponin I. No comparable published survey was found for these, and troponin in
particular is assay-specific: the threshold belongs to the analyser, not to the
literature.

## What a reviewer needs to decide

For each analyte, four things, none of which follow from the table above:

1. The bound, against **this laboratory's assay and reference interval**.
2. The unit the local analyser reports in. A threshold in the wrong unit does
   not fire, and the checker reports the value as though it had been checked.
3. Whether the analyte belongs on the panel at all in this setting.
4. Paediatric and neonatal bounds, which differ from adult and are absent here.

Then set `verify_before_ship: false` with the reviewer's name and the date, and
replace the `source` line with the local protocol or published source relied on.

## Sources

- [Critical values in laboratory medicine](https://acutecaretesting.org/en/articles/critical-values-in-laboratory-medicine) — on the absence of consensus
- [Critical Decision Thresholds for Urgent Physician Notification of Point-of-Care Testing Results](https://pmc.ncbi.nlm.nih.gov/articles/PMC13115040/) — survey medians and spreads

Compiled 2026-09-08.
