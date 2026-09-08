# Prompt changelog

Every prompt change is recorded here with the eval numbers before and after.
A prompt change with no eval run does not merge.

Prompts live beside the service that owns them, in `services/<service>/prompts/`.
This file is the shared record across all five.

---

## What the numbers mean

**Groundedness eval** (`spine/eval/groundedness.py`) scores the one property
these agents share: every claim carries a span, and that span either occurs in
the source or it does not. No clinician is needed to judge that, which is why
it can run before the vignette sets exist.

- **Fabrication rate** — claims whose span was not in the source, over all
  claims. The gates drop these, so a non-zero rate is not a safety failure. It
  measures how hard the gate is working, and a rising number across releases
  means a prompt is drifting toward invention.
- **Recall** — of the claims a reference says the source contains, how many the
  agent found. Read together with fabrication rate, always: a gate that drops
  everything scores perfectly on the first and uselessly on the second.

**Triage eval** (`services/consult/eval/harness.py`) scores Consult against
clinician reference labels: under-triage rate, over-triage rate, missed red
flags. It needs a vignette set, which does not exist.

---

## 2026-09-08 — Rx, Labs and Forensics agents, v1.0.0

New prompts:

- `services/rx/prompts/reading_agent.md` — reads medication lines from OCR text
- `services/labs/prompts/extraction_agent.md` — reads results from a report
- `services/forensics/prompts/structuring_agent.md` — structures an examiner's
  dictation into injuries

All three at temperature 0. No prior version, so there is no before number.

Report: `eval/reports/2026-09-08-groundedness-v1.json`

```
extraction_agent    claims 4   dropped 2   fabrication 0.500   recall 1.000
structuring_agent   claims 2   dropped 1   fabrication 0.500   recall 1.000
reading_agent       claims 3   dropped 1   fabrication 0.333   recall 1.000
```

**These are smoke cases with a scripted model, not a clinician-authored
vignette set.** The inputs were deliberately poisoned with claims the source
does not support, so the fabrication rates say the gates caught everything
planted and nothing more. Recall of 1.000 says no legitimate claim was lost on
the way through.

What these numbers do not say: whether the prompts are clinically correct,
whether they read a real Indian lab report or a real handwritten prescription,
or whether an examiner would recognise the structured injuries as their
dictation. That needs real documents and a clinician, and until then no
clinical claim follows from anything above.

**Blocked.** The vignette sets for all five services are empty. Writing them
means authoring clinical content, which is a clinician's job — see
`CLAUDE.md` §1.
