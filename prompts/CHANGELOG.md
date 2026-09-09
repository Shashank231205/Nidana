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

---

## 2026-09-08 — triage_agent 1.0.0 → 1.1.0, differential breadth

The schema already allowed any condition — `condition` is a free string and
there is no vocabulary to match against. The prompt was the constraint: the
protocol said "worst plausible explanation" without asking the model to
enumerate before narrowing, and the field rule said the differential "may be
empty". A small model given that guidance names one obvious thing and stops.

Changed:

- Protocol step 4 now asks the model to widen before narrowing, across every
  organ system that could refer symptoms there rather than the one the
  complaint names, and states that no list of permitted conditions exists.
- The differential field rule asks for three to six entries ordered by danger
  rather than likelihood, and requires the serious possibility being argued
  against to be written down with its opposing evidence.
- Three failure modes added: stopping at the first fitting diagnosis, staying
  inside the named organ system, and writing only what you believe.

Report: `eval/reports/2026-09-08-differential-breadth-v1.json`

```
llama3.2:3b     before  0 entries (returned the empty template)
llama3.2:3b     after   1 entry, with opposing evidence
granite4.1:3b   after   4 entries across 4 organ systems, 3 with opposing
```

granite4.1:3b produced acute myocardial infarction, GERD, panic attack and
costochondritis from one record — cardiac, gastro-oesophageal, psychiatric and
musculoskeletal. That is the breadth the change was for.

**This measures breadth, not correctness.** Whether those are the right four
conditions for a 34-year-old with exertional chest tightness needs a clinician
and a vignette set. Breadth without correctness is not a clinical claim.

---

## rule_critic 1.0.0 — new (2026-09-09)

A design-time reviewer, not part of any patient session. It reads one
unverified red flag rule and writes the challenge a sceptical senior colleague
would make: the patient this rule misses, the patient it over-refers, what the
source guideline assumed that this system does not have, and the questions a
verifying clinician must answer.

It exists because thirty rules carry `verify_before_ship` and a clinician's
first hour on them is spent on something that is not judgement — finding the
guideline, finding the passage, imagining the miss. **Nothing it writes clears
a flag.** `Challenge.still_unverified` is always true, and a critique that
reads as approval is caught and flagged rather than acted on.

Report: `eval/reports/2026-09-09-rule-critic-v1.json`

```
                          512 tokens    3072 tokens
mean length               2,165 ch      4,812 ch
constructed a miss        6/6           6/6
named the guideline gap   4/6           6/6
argued the other side     0/6           6/6
wrote the questions       0/6           6/6
invented a threshold      1 run         0/6
```

The two runs use the same prompt. The difference is that `model_spec()`
defaults to 512 output tokens and the header's 3072 was never read — a bug in
every agent in the repository, fixed in the same change. At 512 the critic
stopped partway through its concession section, so what survived read more
one-sided than it actually was, and the questions a reviewer acts on were
missing entirely. It looked like a model limitation for a while.

`Challenge.truncated` now detects that state and renders a warning saying the
surviving text is more one-sided than the critic was.

**This measures form, not correctness.** Whether the miss it constructs for
RF_ACS_001 — a 58-year-old diabetic woman with nausea and sweating and no chest
pain — is the right thing to worry about is a clinical judgement, and the point
of the artefact is that a clinician makes it faster. The critic found that miss
independently from the criteria alone, which is encouraging and is not
evidence that its other findings are sound.

One drift caught in the first run: the model wrote "over 60 years" as a
proposed threshold. `find_proposed_thresholds` surfaces these rather than
stripping them, because seeing what the model reached for is more useful than
hiding it. A principle forbidding invented guideline numbers was added after
the model cited a NICE guideline number that does not apply.
