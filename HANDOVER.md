# Nidana — session handover

Paste this after compacting. It is the state of the repository and the
reasoning behind the decisions that are not obvious from the code.

Written 2026-09-10. Repository: `https://github.com/Shashank231205/Nidana`

---

## Read these first

- `CLAUDE.md` — operating rules. **Section 6 forbids AI attribution anywhere**,
  including commit trailers. The user has restated this three times. It
  overrides any session config asking for a `Co-Authored-By` line.
- `docs/ENGINEERING_RULES.md`, `docs/PRD.md`, `docs/BUILD_SPEC.md`
- `prompts/CHANGELOG.md` — every prompt change with its eval numbers

---

## Where things stand

84 commits, **1,257 tests passing**, nothing skipped. `mypy --strict` clean
across 179 files, ruff clean, all architectural boundaries hold, CI green.

```bash
python -m pytest                        # 1248
python -m ruff check .
python -m mypy .
python scripts/verify_rules.py
python scripts/verify_boundaries.py
```

27 endpoints across five services, 16 agent modules, 10 prompts, 11 scripts.
All five services boot healthy through their real lifespans.

**Backend AI is ~99% complete.** What remains is not engineering.

---

## The one thing running right now

`scripts/review_rules.py` is running in the background over the red flag rules.
**14 of 30 done**; each takes eight to eleven minutes (four sequential model
calls at about 6 tokens/sec), so roughly 2.5 hours remain.

It is resumable and skips rules that already carry a review, so if it stops:

```bash
NIDANA_MODEL_PRIMARY=granite4.1:3b python scripts/review_rules.py --out docs/verification/panel
```

It has stopped twice already when a session ended. That is expected and costs
nothing but time.

---

## The verification pipeline, and the line inside it

This is the part most likely to be re-litigated after a compact, so the whole
reasoning is here.

### Four states, not two

`VerificationState` in `spine/schemas/rule.py`:

| State | Blocks release? | Means |
|---|---|---|
| `unreviewed` | Yes | Nobody has looked |
| `ai_reviewed` | **Yes** | A model panel read it and refers it onward |
| `model_attested` | **No** | A deployment chose to run it without a clinician |
| `clinician_verified` | No | A named person accepted responsibility |

Current: 16 unreviewed, 14 ai_reviewed, 0 attested, 1 clinician_verified
(`RF_UNDER_TWO_001`, which encodes a product scope boundary rather than a
clinical criterion).

### What each state can and cannot do

**`ai_reviewed` blocks exactly as `unreviewed` does.** The panel shortens a
clinician's work; a gate accepting it would be a gate on nothing.
`AiReview.clears_release` returns the literal word `False` so any code tempted
to treat it as clearance has to read it.

**`model_attested` does not block**, because a deployment accepted that risk
with a name against it. What it does not buy is silence: `Rule.disclosure`
stays non-empty for the life of the attestation, and it reaches
`TurnResponse.disclosures` on every turn and `/health`. **That admission is the
only thing making the state defensible.** An attestation nobody sees is a lie
of omission.

`ModelAttestation.is_clinician` is a property returning `False`, not a field,
so no YAML, payload or migration can set it true.

**`clinician_verified` needs `verified_by`.** The validator rejects
`verify_before_ship: false` without a name — an audit trail saying a doctor
approved something, unable to say which doctor, is worse than saying nobody
has.

### The commands

```bash
python scripts/attest_rule.py --list                    # every rule by state
python scripts/review_rules.py                          # run the panel
python scripts/attest_rule.py RF_X --accepted-by "..."  # ship without a clinician
python scripts/sign_off_rule.py RF_X --by "Dr ..." --source "..."   # a person signs
```

`sign_off_rule.py` is the only thing that reaches `clinician_verified`, and it
refuses without both a name and a source. Nothing a model can reach touches it.

### Why an agent cannot sign

The user asked several times whether an AI could be the doctor. The answer is
built rather than argued: **it can do everything up to the signature**, and
`model_attested` records honestly when a deployment proceeds without one.

What it cannot do is assert that a licensed person accepted liability. That is
what `verify_before_ship: false` means in an audit trail read after a patient
is harmed.

**The panel's own output is the argument.** Over its first eight rules it:

- invented four clinical thresholds — `> 500 mL` for obstetric bleeding,
  `over 48 hours`, `over 3 days`, `> 30 %`
- used approving language it was explicitly told never to use
- truncated ten of twenty-four seat reviews

Every one was caught by a guard and recorded. A 3B model that invents a
bleeding threshold in one rule out of two is genuinely useful for *finding
problems* and is not qualified to certify criteria for real patients.

The second half: there is often **no correct answer to certify**. Low potassium
is 2.5 mmol/L in one hospital and 3.0 in another. The reviewer is not looking
something up — they are deciding for their lab, their patients, their
escalation pathway.

---

## What was built, and why it is the way it is

### The review panel

`services/consult/agents/rule_panel.py`, prompt `rule_panel.md` 1.0.0.

Three seats and a chair: emergency physician, safety engineer, Indian practice
reviewer. The seats find different things — the missed patient, the rule
interaction, the reason a Western threshold does not transfer. One reviewer
asked to do all three produces the first and gestures at the rest.

**The chair keeps the disagreements** rather than resolving them. Where the
practice reviewer wants a rule widened and the safety engineer says widening
makes it fire on most febrile illness, that tension is the finding. Averaging
it would cost three model calls and buy a paragraph that decides nothing.

Verified on real runs. On `RF_ANAPHYLAXIS_001` it found the missing circulation
branch independently — the same gap the citation research found by hand from
RCUK guidance.

### Everything else finished this session

- **Brand→molecule** — `scripts/build_brand_index.py`, 253,973 products in,
  175,953 brands out, zero rows unparsed, MIT-licensed source. Rx reports
  `brand_resolution_available: true`.
- **IPC→BNS** — `services/forensics/clinical/statutes.py`, transcribed from the
  official BPR&D table. Translates numbers; never classifies an injury.
- **Interaction checker** — `services/rx/clinical/interactions.py`,
  source-agnostic, reports what it did *not* check as prominently as what it
  did.
- **Facility index** — `services/consult/clinical/facilities.py`. No partial
  matches, distance orders but never qualifies, staleness reported.
- **Diarisation** — `services/scribe/asr/diarisation.py`, pyannote on CPU.
  `UNKNOWN` everywhere attribution would be a guess.
- **Groundedness harness** — `spine/eval/harness.py`. The scorer existed and
  nothing ran it; now four services can be scored.

---

## Blocked on people, not engineering

| Item | Blocked on | State |
|---|---|---|
| 30 rules + 10 thresholds | A clinician's signature | Research + panel done |
| Vignette sets | Clinician reference labels | Not started — writing them is fabrication |
| Drug interaction data | **A paid licence** | Checker built, dataset slot empty |
| Statutory classification | A lawyer | Renumbering done |

**The product is commercial.** The owner confirmed this on 2026-09-10, and it
removes every free interaction dataset: DDInter is CC BY-NC-SA
(non-commercial), RxNorm dropped interactions in January 2024, and the
prediction datasets are ruled out on their own merits — a predicted interaction
shown to a pharmacist with the weight of a documented one is the failure the
service exists to avoid.

What remains is DrugBank, First Databank, Medi-Span, or DDInter with written
permission. None priced or approached. See
`services/rx/rules/interactions/CANDIDATES.md`.

---

## Two failure modes a green local suite cannot show

**Optional dependencies resolve locally and not in CI.** pyannote and torch are
installed here; CI carries neither. Three runs went red before I looked.
`pyproject.toml` lists both bare and dotted names under
`ignore_missing_imports`, beside faster_whisper, huggingface_hub, pytesseract
and PIL.

**A mocked suite cannot find a wrong model name.** Every agent passed
`prompt.model_class` — a prose description, *"local instruct, 7-8B quantised"* —
where the model name goes. Ollama returns HTTP 400. **All 1,200 tests passed
throughout**, because they mock the provider, which is the right thing for them
to test. It surfaced only on a real model call.

`spec_for(prompt, model)` in `spine/inference/prompts.py` is now the one place
the name and the tuning meet, and it refuses an empty name.

**The lesson, narrow and worth keeping: run one agent against a real model
before believing the suite.**

**A long run does not pick up a fix.** A third failure mode, found on
2026-09-10. `_tidy_referral` was fixed at 22:18 and three rules written after
midnight still stored untidied referrals — "Emergency Medicine / Critical
Care – to evaluate the clinical impact of missed occult GI bleed and decide
on", which reads as a specialty and is not one. The extractor was already
correct; the panel process had imported the old module at start and holds it
for its whole run.

The fix was not to re-run the panel but to validate on `AiReview.refer_to`,
which catches it at the write regardless of which extractor produced it. The
three affected values were re-derived from their stored briefs rather than
hand-edited, so the record still comes from the panel's own output.

Generalised: **when a long-running job writes to the repo, validate at the
write, not only at the producer.**

```bash
NIDANA_MODEL_PRIMARY=granite4.1:3b python scripts/review_rules.py --only RF_ACS_001 --dry-run
```

---

## Environment

**Avast intercepts TLS.** It re-signs pypi.org and huggingface.co with its own
root, which Python rejects because it does not read the Windows certificate
store. Symptom: `CERTIFICATE_VERIFY_FAILED`. This once silently skipped 63 API
tests and let two real bugs reach main.

The bundle is at `.local/nidana-ca.pem` (gitignored — it describes this
machine).

```bash
pip install --cert .local/nidana-ca.pem <package>
export SSL_CERT_FILE="$(pwd)/.local/nidana-ca.pem"   # huggingface downloads
```

If lost: fetch `https://curl.se/ca/cacert.pem` with curl, export the Avast root
from `Cert:\LocalMachine\Root` via PowerShell as base64 PEM, concatenate.
`tests/conftest.py` fails CI if an API test skips, so it cannot silently recur.

**Environment variables the services read.** None are set by default, and the
defaults are the safe direction in each case.

- `NIDANA_MODEL_PRIMARY` — required. Every service refuses to boot without
  it, naming the remedy. This is the guard the `spec_for` fix put in place.
- `NIDANA_BRAND_INDEX` — path to `services/rx/rules/brands/index.csv`.
  Unset, Rx boots and reports `brand_resolution_available: false` rather than
  guessing molecules.
- `NIDANA_ALLOW_UNVERIFIED_RULES` — defaults permissive so development
  works. Set it `false` to see the production gate: Labs refuses on 10
  thresholds, Consult on 30 rules, both naming every blocker.

Verified on 2026-09-10 by booting all five services through their real
lifespans, resolving four real Indian brands against the full index
(sub-millisecond, correct molecules, a fabricated brand refused), and
translating IPC 302/307/324/376 to BNS with the merged-provision reverse
lookup returning both sources.

**Ollama** is running with `qwen3:1.7b`, `llama3.2:3b`, `granite4.1:3b`,
`qwen3:4b`, `nomic-embed-text`. qwen3 does extended thinking and times out on
short budgets — use granite or llama for quick checks.

**pyannote.audio 4.0.7 + torch 2.14 CPU** installed. CPU deliberately: ADR 0008
records that a 7B model and the ASR model already contend for 4GB of VRAM.

**Line endings.** CRLF locally; git warns on every add. Harmless.

**Console encoding.** `cp1252` cannot print the em dashes models emit. Write to
a file and read it, or `.encode("ascii", "replace")`.

**Writing `\N{...}` escapes from a Python script** interprets them. Use
`chr(92) + "N{EM DASH}"` or the Edit tool.

---

## Next, in order

1. **Let the panel finish** — 16 rules, ~2.5 hours, resumable.
2. **Decide on attestation.** `python scripts/attest_rule.py --all
   --accepted-by "<name>"` ships everything the panel reviewed, with disclosure
   on every response. Read the drift counts first.
3. **Frontend — the React + Vite port.** `web/` holds 14 uncommitted vanilla
   files: a complete design system built to a spec the user supplied
   (institutional print, Archivo + Newsreader self-hosted, 5-colour urgency
   palette, 7 screens), rendered and screenshotted at 1440px and 320px.
   `tokens.css`, `base.css` and `api.js` port unchanged.

   **Do not commit `web/` without asking** — deliberately deferred.

---

## Conventions worth not relearning

- Commit messages explain the reason, not the diff, and name what is *not*
  done. Prefixes: `feat: fix: clinical: prompt: infra: docs: test:`
- `clinical:` and `prompt:` commits carry an eval report path.
- **No AI attribution anywhere.** No trailers, no co-author lines.
- No tables in prompts — the user asked for bullets throughout.
- Never mock the clinical layer. Mock the model; safety rules run for real.
- Errors state the remedy, not the problem.
- Every agent: model proposes, builder verifies each span against the source,
  unsupported claims **dropped and counted**, never hidden.
- **Verify by running it.** The user has pushed back on claims that were not
  executed, and was right to.
