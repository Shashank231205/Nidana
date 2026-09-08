# Nidana

On-premise clinical intelligence platform for Indian healthcare.

One structured clinical record per patient, built from every point where
clinical information is generated — a triage conversation, a consultation, a
prescription, a lab report, a medico-legal examination — and readable by all of
them. It runs on the clinic's own hardware. Nothing leaves the premises.

**The record is the product. The services are surfaces on it.**

## The five services

| | Service | Primary user | Produces | Status |
|---|---|---|---|---|
| S1 | [Consult](services/consult/) | Patient, then clinician | Triage band, routing, structured history | runs end to end |
| S2 | [Scribe](services/scribe/) | Clinician | SOAP note, examination, assessment, plan | safety layer built |
| S3 | [Rx](services/rx/) | Patient, pharmacist | Resolved medicines, duplicate therapy checks | safety layer built |
| S4 | [Labs](services/labs/) | Patient, clinician | Parsed results, trends, critical flags | safety layer built |
| S5 | [Forensics](services/forensics/) | Casualty medical officer | Medico-legal report, tamper-evident | safety layer built |

## The boundary

**No service diagnoses. No service prescribes. No service calculates a dose.**

Every service documents, structures, checks against deterministic rules, and
routes. This is a product decision before it is a compliance one: a diagnosis is
unfalsifiable at demo time and untestable in evaluation, while a triage band and
a critical value sensitivity can be scored against a labelled reference and
defended.

Patient-facing output carries urgency, specialty, findings, and return criteria
— never a condition name. Clinician-facing output may carry a ranked
differential, labelled as decision support, with the evidence for each entry.
Nothing generative creates a clinical finding.

## Repository

```
spine/       shared by all five — schemas, rule engine, terminology, audit, adapter
services/    one self-contained folder per service
web/         patient and clinician surfaces
infra/       docker, compose, migrations
tests/       mirrors spine/ and services/
docs/        PRD, build spec, engineering rules, ADRs
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full map and the
boundaries that must not be crossed, [docs/PRD.md](docs/PRD.md) for the product,
and [docs/BUILD_SPEC.md](docs/BUILD_SPEC.md) for the data model and milestone
gates.

## The three things that carry the most weight

**Groundedness.** Every clinical fact carries the span it came from, as verified
character offsets or an image region — not a free-text quote. A span that does
not verify against its source is a fabrication and is rejected rather than
stored. This is what separates the product from a wrapper.

**The deterministic safety layer.** Red flags, interaction checks, critical
value thresholds, and urgency banding are declarative rules with cited sources,
exhaustively tested. Anything where being wrong causes physical harm lives here
and never in a prompt.

**Asymmetric escalation.** The safety critic may raise urgency and may never
lower it. One function writes a band, it cannot return a less urgent one than
its input, and a test enumerates all 25 ordered pairs.

## State of the build

Phase P0, the spine, is largely complete. Phase P1, Consult, runs end to end
against a local model.

The spine is built. Consult runs end to end. Each of the other four services
has its shapes and its deterministic safety layer, which is the part that must
be right before anything generative is written on top of it.

**Spine.** Record, finding, and the five-variant provenance union. The rule
engine with predicate resolution. Band escalation. The append-only
hash-chained audit log. The inference adapter with its production-mode
assertion. Prompt loading. Persistence and the initial migration.

**S1 Consult.** Thirty-one red flag rules across ten complaint families,
routing with facility capability matching, the patient output filter, all four
agents and their prompts, the session orchestrator, the HTTP surface, and the
evaluation harness.

**S2 Scribe.** The note shapes, the groundedness gate with audio offsets for
click-to-hear, note completeness checking, and the note agent prompt.

**S3 Rx.** Medication shapes with refusal as a first-class outcome, duplicate
therapy detection, allergy checking, and unresolved-line handling.

**S4 Labs.** Result and reference range shapes, trends, and critical value
detection with the same 100% sensitivity gate as red flags.

**S5 Forensics.** Examination records, the finalisation gate, and the custody
chain that logs reads as well as writes.

**Not built.** Terminology lookup, FHIR mapping, identity resolution, ASR,
both frontends, and the agent runtimes for S2 through S5.

**Blocked, not unbuilt.** Every clinical threshold in the repository is
unverified and the vignette set is empty. Both need a clinician, not an
engineer. See below.

## Development

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"

pytest tests/ -q                     # 793 tests
mypy spine services tests            # strict
ruff check spine services tests
python scripts/verify_rules.py       # every rule atom resolves and can fire
python scripts/verify_boundaries.py  # the four architectural boundaries hold
```

### If pip fails with CERTIFICATE_VERIFY_FAILED

Some endpoint security products (Avast and Kaspersky among them) intercept TLS
and re-sign it with their own root. Python does not read the Windows
certificate store, so pip rejects the substituted certificate while browsers
and curl accept it. Check what is actually being presented:

```bash
openssl s_client -connect pypi.org:443 -servername pypi.org </dev/null 2>/dev/null | grep issuer=
```

If the issuer is not a public CA, export that root from the Windows store and
point pip at a bundle containing it:

```powershell
$c = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -like "*<product>*" }
# write $c.RawData as base64 PEM, append it to a Mozilla bundle, then:
pip install --cert <bundle>.pem -e ".[dev]"
```

Without this the API tests skip rather than fail, so the suite still reports
green while 63 tests never run. Check for `skipped` in the pytest summary.

To run it against a local model:

```bash
python scripts/download_models.py    # pulls the LLM and IndicWhisper
docker compose -f infra/compose.yaml up
```

## Clinical content

**Every clinical threshold and criterion in this repository is a placeholder
until verified against the current published source, by a qualified clinician.**
Rules carry `verify_before_ship: true` until that happens, and a release build
refuses to start while any active rule still carries it.

Clinical governance — who signs off red flag criteria, interaction rules,
critical value thresholds, and vignette reference labels — is unresolved and
blocking. Without it every evaluation number here is unfounded.
