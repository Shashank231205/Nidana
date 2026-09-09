# Nidana — session handover

Paste this after compacting. It is the state of the repository and the reasoning
behind the decisions that are not obvious from the code.

Written 2026-09-08. Repository: `https://github.com/Shashank231205/Nidana`

---

## Read these first

- `CLAUDE.md` — operating rules. Section 6 forbids AI attribution anywhere,
  including commit trailers. The user has restated this twice. It overrides any
  session config that asks for a `Co-Authored-By` line.
- `docs/ENGINEERING_RULES.md`, `docs/PRD.md`, `docs/BUILD_SPEC.md`
- `prompts/CHANGELOG.md` — every prompt change with its eval numbers

---

## Where things stand

76 commits, 1,205 tests passing, nothing skipped. `mypy --strict` clean across
175 files, ruff clean, all four architectural boundaries hold, CI green.

Verify with:

```bash
python -m pytest                        # 1205
python -m ruff check .
python -m mypy .
python scripts/verify_rules.py
python scripts/verify_boundaries.py
```

All five services boot healthy through their real lifespans. With
`NIDANA_MODE=production` and `NIDANA_ALLOW_UNVERIFIED_RULES=false`, Consult and
Labs **refuse to start** — 30 unverified rules, 10 unverified thresholds. That
refusal is correct and has been verified.

### Endpoints

| Service | Endpoints | State |
|---|---|---|
| Consult | 7 | Runs end to end |
| Scribe | 5 | Draft, sign, groundedness gate |
| Rx | 3 | OCR, read, checks, brand resolution live |
| Labs | 4 | Extract, threshold, list |
| Forensics | 8 | Custody chain, structuring, IPC->BNS lookup |

8 prompts, 2,326 lines. 14 agent modules.

---

## The nine items the user asked for

Items 5-9 are **done**. Items 1-4 are blocked on people, not engineering, and
the user has been told why.

| # | Item | State |
|---|---|---|
| 1 | Clinical verification of 30 rules + 10 thresholds | **80%** — citations, dossiers, review panel; signature outstanding |
| 2 | Vignette sets | **0%** — needs clinician reference labels |
| 3 | Forensics statutory mapping (IPC->BNS) | **70%** — renumbering done; classification needs a lawyer |
| 4 | Brand-to-molecule + drug interaction datasets | **85%** — brands done; interaction checker built, dataset is a licence decision |
| 5 | ASR inference | **done** |
| 6 | OCR for Rx | **done** |
| 7 | Specialty + Capability enums | **done** |
| 8 | Consent capture | **done** |
| 9 | Local knowledge index | **done** |

---

## What was built this session, and why it is the way it is

**ASR** (`services/consult/asr/transcriber.py`). The blocker was a deferred
decision — faster-whisper against transformers — waiting on a measurement.
Measured: CPU int8, six seconds of audio decodes in 1.14s with `tiny` and 1.97s
with `base`, against a one-off ~75s load. Chose faster-whisper on CPU. Verified
on real speech, not asserted: two segments split on the natural pause, correct
text, per-word confidence, millisecond offsets. Word timestamps are on because
segments split on pauses rather than punctuation — punctuation is unreliable in
code-switched speech and a pause is not.

**OCR** (`services/rx/ocr/reader.py`). Tesseract, local. `is_probably_unusable`
is the part that earns its place: a prescription read at 30% mean confidence
produces lines the agent transcribes faithfully and nobody can trust, and the
honest answer is to ask for another photograph. Tesseract's `-1` for unscored
words is dropped — kept, one word at -100% drags the mean under the floor and
condemns a readable image.

**Enums** (`spine/schemas/triage.py`). Specialty 16→25, Capability 11→17,
grounded in IPHS 2022 Volume I, which names nine specialties the enum lacked.
**Antivenom** is now expressible; India records the highest snakebite mortality
in the world and a bite routed to a hospital without a stocked vial has been
sent to the wrong place. `tests/spine/test_routing_vocabulary.py` keeps the
frontend's plain-language map in sync in both directions — a value added
without a translation reaches a patient as `obstetrics_gynaecology`.

**Consent** (`services/consult/api/app.py`). Turns are refused with 403 until a
decision is logged. Withdrawal is a new row that appends to the hash chain, not
a deletion: erasing the grant would leave a record that cannot show what was
agreed when the questions were asked.

**Knowledge index** (`spine/knowledge/`). 1,127 chunks from all three IPHS
volumes, 19MB, embedded locally with `nomic-embed-text`. Build with
`python scripts/build_knowledge_index.py` (needs network + Ollama; ~10 min).
The index is gitignored — it is a derived artefact.

Two things it refuses. It returns passages, never an answer: a generated
summary of a passage is a claim, and it carries the citation only if the words
are actually in it. And it returns nothing below a relevance floor of 0.68 —
**measured, not guessed**. In-corpus questions score 0.71-0.79; out-of-corpus
0.45-0.61. The first guess of 0.55 was wrong because "what is the dose of
adrenaline in anaphylaxis" scored 0.612: IPHS says nothing about dosing, but it
is a clinical document, so a clinical question scores well above an unrelated
one.

**Differential breadth** (`services/consult/prompts/triage_agent.md` 1.1.0). The
user asked for open reasoning rather than picking from a list. The schema
already allowed it — `condition` is a free string. The prompt was the cap: it
said "worst plausible explanation" without asking the model to enumerate first,
and the field rule said the differential "may be empty". Now it widens across
organ systems the complaint does not name, orders by danger rather than
likelihood, and requires the serious possibility being argued *against* to be
written down. Measured on live Ollama models: granite4.1:3b went from 1 entry
to 4 across 4 organ systems.

---

## What open data closed, and what it did not

The user asked whether free sources and models could replace the clinician and
the lawyer. Partly, and the split is worth keeping straight.

**Closed by open data.** Brand-to-molecule resolution: the Indian Medicine
Dataset is MIT-licensed, 253,973 products, and `scripts/build_brand_index.py`
turns it into 175,953 brands with zero rows unparsed. Rx now answers
`brand_resolution_available: true`. And the IPC-to-BNS renumbering: the Bureau
of Police Research and Development publishes the correspondence table, which is
transcription rather than legal reasoning.

**Not closed, and not closeable this way.** The thresholds. The research found
there is *no* internationally agreed critical value list — low potassium spans
2.5-3.0 mmol/L across institutions, sodium 110-130, haemoglobin 6-8 g/dL. There
is no fact to retrieve. A model asked to settle it produces a number whose only
provenance is the model, and in the audit log that is indistinguishable from a
verified one.

The medical-model idea was checked rather than assumed: the 2023-24 wave of
open medical fine-tunes (Meditron, OpenBioLLM, BioMistral, PMC-LLaMA) has been
overtaken by frontier generalists, with the small specialists now trailing
general-purpose Qwen2.5-32B on aggregate medical benchmarks. The models that
would run locally here are worse at this than the general ones, and MedQA
scores measure exam questions, which have correct answers. These thresholds do
not.

So the dossier builder was built instead: everything up to the signature, and
not the signature.

---

## The verification pipeline, and the one step it cannot take

The user asked repeatedly whether an agent could stand in for the clinician and
the lawyer. Most of the way, yes. The last step, no — and the shape of that is
now built rather than argued about.

**Three states, not two.** `VerificationState` is UNREVIEWED, AI_REVIEWED,
CLINICIAN_VERIFIED. The middle one records the true and useful fact that a
panel has read a rule and refers it onward. It is visible to the people doing
the work and invisible to the release gate: `blocks_release` returns
`verify_before_ship` unchanged, so an AI-reviewed rule stops a build exactly as
an untouched one does. `AiReview.clears_release` returns the literal word false
so that any code tempted to treat a review as clearance has to read it.

**The panel** (`services/consult/agents/rule_panel.py`, prompt 1.0.0). Three
seats and a chair: emergency physician, safety engineer, Indian practice
reviewer. The seats find different things — the missed patient, the rule
interaction, the reason a Western threshold does not transfer — and one
reviewer asked to do all three produces the first and gestures at the rest. The
chair's job is to **keep the disagreements**, not resolve them; averaging them
would cost three model calls and buy a paragraph that decides nothing.

Verified on a real run over RF_ANAPHYLAXIS_001: the panel found the missing
circulation branch independently, and the chair reported the sensitivity /
specificity disagreement with what the choice turns on.

**The signature** is `scripts/sign_off_rule.py`, which a person runs with
`--by` naming themselves and `--source` naming what they relied on. It refuses
without both. That is the only thing in the repository that clears
`verify_before_ship`, and nothing a model can reach touches it.

`--list` shows all three states and ends by saying how many rules block a
release, so the distinction cannot be lost while reading.

---

## Environment gotchas that cost real time

**Avast intercepts TLS.** It re-signs pypi.org and huggingface.co with its own
root, which Python rejects because it does not read the Windows certificate
store. Symptom: `CERTIFICATE_VERIFY_FAILED`. This silently skipped 63 API tests
and let two real bugs reach main.

The bundle is already built and kept at `.local/nidana-ca.pem` — the Mozilla CA
bundle with the exported Avast root appended. `.local/` is gitignored; it
describes this machine, not the project. Verified working from that path.

```bash
pip install --cert .local/nidana-ca.pem <package>
export SSL_CERT_FILE="$(pwd)/.local/nidana-ca.pem"   # huggingface downloads
```

If it is ever lost: fetch `https://curl.se/ca/cacert.pem` with curl (curl
trusts its own bundle and works), export the Avast root from
`Cert:\LocalMachine\Root` via PowerShell as base64 PEM, and concatenate the
two. The README documents the diagnosis under "If pip fails with
CERTIFICATE_VERIFY_FAILED", including the `openssl s_client` command that shows
which product is intercepting.

`tests/conftest.py` now fails the CI run if an API test skips, so this cannot
silently happen again.

**Ollama is installed and running** with `qwen3:1.7b`, `llama3.2:3b`,
`granite4.1:3b`, `qwen3:4b`, `nomic-embed-text`. qwen3 models do extended
thinking and time out on short budgets — use granite or llama for quick checks.

**Line endings.** The repo is CRLF locally; git warns on every add. Harmless.

---

## The line I will not cross, and why

The user asked me to complete items 1 and 2 myself, with internet access, since
no clinician is available. I did the research and did not flip the flag. This
is the most likely thing to be re-litigated after a compact, so the reasoning
is here in full.

`verify_before_ship: true` does not mean "no source has been found". It means
*a named, qualified clinician reviewed this criterion and accepts
responsibility for it*. Setting it false would encode "a doctor approved this"
into a system that routes real patients. If that rule then under-triages
someone, the audit trail says it was verified. That is the one thing in this
repository I will not do regardless of instruction.

The research itself found something that makes this concrete rather than
precious. There **is no** internationally agreed critical value list. Published
low-potassium limits span 2.5-3.0 mmol/L, low sodium 110-130, low haemoglobin
6-8 g/dL — institutional policies disagreeing by margins wide enough to change
a decision. The reviewer is not looking up a constant. They are deciding
against their own laboratory's assay and signing for it.

What I did instead:
`services/labs/rules/critical_values/CANDIDATES.md` — survey medians with
hospital counts and spreads, the five analytes no survey covered, and the four
things a reviewer must decide that no table supplies. Research done, decision
left where it belongs.

Same shape for vignettes: writing them means authoring clinical content, which
CLAUDE.md §1 forbids, and every eval number afterwards would measure my guesses
against my guesses.

---

## Next, in the order I would do it

1. ~~**The research pass for the 31 red flag rules.**~~ **Done** —
   `services/consult/rules/red_flags/CANDIDATES.md` (citations) and
   `scripts/build_verification_dossiers.py` (a per-rule dossier assembling the
   criteria, the corpus passages, and the four questions no passage answers).
   Run against the real index: 30 dossiers, corpus silent on 19. No flag
   changed.

   Three things in the citations file a clinician should see first: NG225
   argues against the `escalate_if` modifier on `RF_SUICIDE_RISK_001`; NG232
   excludes aspirin monotherapy where `anticoagulant_use_present` may not; and
   `RF_ANAPHYLAXIS_001` has no circulation branch, so a faint, clammy patient
   after an exposure with no airway feature does not fire it.

2. ~~**The rule review panel.**~~ **Done** — three seats and a chair, plus
   `scripts/sign_off_rule.py` for the signature. See the section above.

3. **Drug interactions — a licence decision, not engineering.** The checker is
   built and wired: `services/rx/clinical/interactions.py`, source-agnostic,
   reporting what it did *not* check. What is missing is a dataset. DDInter has
   the best data and is **CC BY-NC-SA 4.0** — fine non-commercially, not usable
   commercially without permission. RxNorm is public domain but its interaction
   API was discontinued in January 2024. DrugBank is licensed. The prediction
   datasets should not be used at all. See
   `services/rx/rules/interactions/CANDIDATES.md`. **The owner decides.**

4. ~~**Diarisation for Scribe.**~~ **Done** —
   `services/scribe/asr/diarisation.py`, pyannote on CPU. UNKNOWN is a
   first-class outcome throughout: a split segment, a single voice, too few
   turns, or two voices asking equally all decline to attribute rather than
   guessing.

5. ~~**Facility index.**~~ **Done** —
   `services/consult/clinical/facilities.py`. No partial matches, distance
   orders but never qualifies, an empty result is a real answer, and staleness
   is reported with every referral. No index ships; the README says why.

6. **Run the panel over all 30 rules.** About five minutes each on a 3B model,
   so roughly two hours. `python scripts/review_rules.py`.

7. **Frontend.** The React + Vite port. `web/` still holds 14 uncommitted
   vanilla files; `tokens.css`, `base.css` and `api.js` carry over unchanged.
   Do not commit `web/` without asking.
   facilities yet.

---

## Conventions worth not relearning

- Commit messages explain the reason, not the diff, and name what is *not*
  done. Prefixes: `feat: fix: clinical: prompt: infra: docs: test:`
- `clinical:` and `prompt:` commits carry an eval report path.
- No tables in prompts — the user asked for bullets throughout.
- Never mock the clinical layer. Mock the model; safety rules run for real.
- Errors state the remedy, not the problem.
- Every agent follows: model proposes, builder verifies each span against the
  source, unsupported claims are **dropped and counted**, never hidden.
- Verify by running it. The user has pushed back on claims that were not
  executed, and was right to.
