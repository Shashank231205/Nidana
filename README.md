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
| S1 | [Consult](services/consult/) | Patient, then clinician | Triage band, routing, structured history | in build |
| S2 | [Scribe](services/scribe/) | Clinician | SOAP note, examination, assessment, plan | planned |
| S3 | [Rx](services/rx/) | Patient, pharmacist | Resolved medicines, interaction checks | planned |
| S4 | [Labs](services/labs/) | Patient, clinician | Parsed results, trends, critical flags | planned |
| S5 | [Forensics](services/forensics/) | Casualty medical officer | Medico-legal report, tamper-evident | planned |

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

Phase P0, the spine, is in progress.

Built: the record and finding shapes, the five-variant provenance union, band
escalation, the field registry for ten complaint families, the predicate
registry and its load-time resolution.

Not built: red flag rules, routing, terminology, audit chain, persistence,
migrations, the inference adapter, every agent, both frontends, and services
S2 through S5.

## Development

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"

pytest tests/ -q                          # 206 tests
mypy spine services tests                 # strict
ruff check spine services tests
```

## Clinical content

**Every clinical threshold and criterion in this repository is a placeholder
until verified against the current published source, by a qualified clinician.**
Rules carry `verify_before_ship: true` until that happens, and a release build
refuses to start while any active rule still carries it.

Clinical governance — who signs off red flag criteria, interaction rules,
critical value thresholds, and vignette reference labels — is unresolved and
blocking. Without it every evaluation number here is unfounded.
