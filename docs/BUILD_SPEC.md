# Nidana Consult — Build Spec

Companion to `docs/PRD.md`. This file pins down the shapes so they do not get invented twice.

---

## 1. Domain vocabulary

Fixed terms. Use these names in code, database, and prompts. Do not introduce synonyms.

| Term | Meaning |
|---|---|
| **Session** | One patient encounter from first message to final output |
| **Turn** | One patient utterance plus the agent response to it |
| **Finding** | A single clinical fact elicited from the patient, with its source span |
| **Record** | The accumulated set of findings for a session |
| **Complaint family** | The classification that determines which fields are required |
| **Red flag** | A deterministic rule that can terminate a session |
| **Band** | Urgency level, U1 to U5 |
| **Handoff packet** | The clinician-facing output |
| **Return criteria** | Patient-facing instructions for when to seek care regardless of band |

---

## 2. Core schemas

All in `packages/schemas/`. Pydantic v2. These are the contract between every component.

### Finding

The atomic unit. Nothing enters the record except as a Finding.

```
Finding
  field            str          from the field registry for this complaint family
  value            str|num|bool|enum
  unit             str|None     required when value is numeric and unitful
  source_span      str          the patient's own words, verbatim
  turn_index       int
  confidence       high|medium|low
  negated          bool         patient explicitly denied this
  asked            bool         False means never asked, distinct from denied
```

Two rules that matter more than the rest:

`source_span` is non-optional. A Finding without one fails validation. There is no code path that constructs a Finding from inference.

`asked=False` is not the same as `negated=True`. "Not asked" and "asked and denied" carry different clinical weight and the triage agent must be able to tell them apart. The validator rejects `negated=True` where `asked=False`.

### Record

```
Record
  session_id           UUID
  complaint_family     ComplaintFamily|None
  findings             list[Finding]
  demographics         Demographics
  comorbidities        list[Comorbidity]
  medications          list[Medication]
  allergies            list[Allergy]
  pregnancy_status     unknown|possible|confirmed|not_applicable
  is_proxy             bool          patient describing someone else
  sufficiency          Sufficiency
```

### Sufficiency

```
Sufficiency
  complete           bool
  required_fields    list[str]      from the family registry
  missing            list[str]
  low_confidence     list[str]      fields needing re-ask
```

### TriageResult

```
TriageResult
  band                  Band
  rationale             str
  escalating_factors    list[str]
  uncertainty           str|None
  destination           Destination
  return_criteria       list[str]      min 3 when band != U1
  differential          list[DifferentialEntry]
  history_gaps          list[str]
  patient_summary_input PatientSummaryInput
```

### Band

Ordered enum. This ordering is what makes the safety critic's asymmetry type-enforceable.

```
Band  U1 < U2 < U3 < U4 < U5    (U1 most urgent)
```

The critic's signature is `escalate_only(current: Band, proposed: Band) -> Band` returning `min(current, proposed)` by urgency. There is no function that can return a less urgent band than its input.

### RedFlagResult

```
RedFlagResult
  fired            bool
  rule_ids         list[str]
  action           TERMINATE_EMERGENCY | ESCALATE_BAND | ANNOTATE
  required_capabilities list[str]
  patient_message_key   str
```

---

## 3. Field registry

`rules/fields/<complaint_family>.yaml`. Defines required and optional fields per family, with types and units. The intake agent reads this to know what is still missing; the validator reads it to check Finding fields are legal.

```yaml
family: chest_pain
required:
  - field: onset_duration_hours
    type: number
    unit: hours
  - field: onset_speed
    type: enum
    values: [sudden, gradual, unknown]
  - field: radiation
    type: enum
    values: [none, jaw, left_arm, right_arm, back, epigastrium]
    multi: true
  - field: exertional_relation
    type: enum
    values: [worse_on_exertion, unrelated, worse_at_rest, unknown]
  - field: diaphoresis
    type: boolean
optional:
  - field: relation_to_food
    type: enum
    values: [worse_after, better_after, unrelated, unknown]
```

Adding a field is a schema change and a migration. It is not an ad-hoc addition inside a prompt.

---

## 4. Database

Postgres. Alembic, forward-only.

```
sessions
  id                UUID PK
  created_at        timestamptz  DEFAULT now()
  status            enum(active, completed, terminated_emergency, handed_off)
  complaint_family  text
  band              text          nullable until triage runs
  specialty         text          nullable
  locale            text
  rule_set_version  text
  prompt_versions   jsonb

session_turns
  id                UUID PK
  session_id        UUID FK
  turn_index        int
  patient_utterance text
  agent_utterance   text
  language          text
  created_at        timestamptz  DEFAULT now()
  UNIQUE(session_id, turn_index)

findings
  id                UUID PK
  session_id        UUID FK
  turn_index        int
  field             text
  value             jsonb
  source_span       text          NOT NULL
  confidence        text
  negated           bool
  asked             bool
  created_at        timestamptz  DEFAULT now()

triage_results
  id                UUID PK
  session_id        UUID FK
  band              text
  specialty         text
  payload           jsonb
  critic_adjusted   bool
  critic_from_band  text          nullable
  created_at        timestamptz  DEFAULT now()

audit_events
  id                UUID PK
  session_id        UUID FK
  event_type        text
  actor             text          agent name, rule id, or 'system'
  prompt_version    text          nullable
  model_version     text          nullable
  payload           jsonb
  created_at        timestamptz  DEFAULT now()

patients
  id                UUID PK
  identifiers       jsonb         restricted access
  created_at        timestamptz  DEFAULT now()

facilities
  id                UUID PK
  name              text
  location          geography(Point, 4326)
  capabilities      text[]
  hours             jsonb
  last_verified_at  timestamptz
```

Rules on this schema:

**No UPDATE or DELETE on `findings`, `triage_results`, `audit_events`, `session_turns`.** Enforced by a database role that lacks the grant, not by convention. Corrections are new rows.

**`patients` is joined to `sessions` by a nullable FK only.** A dump of the clinical tables is not a breach.

**`source_span` is `NOT NULL`.** The invariant is enforced at the storage layer, not only in Pydantic.

**Indexed:** `sessions(band)`, `sessions(created_at)`, `findings(session_id)`, `audit_events(session_id, created_at)`, GiST on `facilities(location)`.

---

## 5. API surface

FastAPI. The HTTP layer does no clinical reasoning; it delegates.

```
POST   /v1/sessions                     create; returns session_id and opening turn
POST   /v1/sessions/{id}/turns          submit patient utterance; returns next turn
                                        or terminal state
POST   /v1/sessions/{id}/audio          multipart; ASR then as above
GET    /v1/sessions/{id}                current record and status
POST   /v1/sessions/{id}/complete       force triage on current record
GET    /v1/sessions/{id}/patient-view   filtered patient output
GET    /v1/sessions/{id}/handoff        clinician packet
POST   /v1/sessions/{id}/handoff-human  escalate to human
GET    /v1/facilities                   capability + geo query
GET    /health
```

Every response from `/turns` is one of three shapes: a next question, a terminal emergency instruction, or a completed triage. The client renders on shape, never on a status string it has to parse.

---

## 6. Components and their boundaries

| Package | Contains | Never contains |
|---|---|---|
| `services/clinical/` | red flags, band logic, routing, sufficiency | any model call, any I/O |
| `services/agents/` | intake, structuring, triage, critic; one adapter | clinical thresholds |
| `services/terminology/` | SNOMED and ICD-10 lookup | a model |
| `services/asr/` | transcription | anything downstream |
| `services/persistence/` | repositories | business logic |
| `packages/schemas/` | every clinical shape | logic |
| `packages/fhir/` | R4 mapping | anything that isn't mapping |

All inference goes through `services/agents/adapter.py`. Model identity, quantisation, and sampling are configuration. A model swap is a config change plus an eval re-run.

---

## 7. Milestones and acceptance gates

Do not begin a milestone until the previous one's gate is met and its eval report is committed.

### M1 — Spine
Schemas, field registry, migrations, red flag engine, routing rules, vignette set v1. No models.

**Gate:** 100% coverage on `services/clinical/`. Every red flag rule has positive, negative, and boundary tests. Every rule carries a cited source. `docker compose up` starts the database and runs migrations clean.

### M2 — Text consultation
Intake agent, structuring agent, English only, text only. Handoff packet generation.

**Gate:** Fabrication rate zero on the golden transcript set, structurally enforced rather than measured. History completeness above 90% on required fields across all complaint families. First eval report committed.

### M3 — Triage and routing
Triage agent, safety critic, facility index with capability matching, both frontends.

**Gate:** Red flag sensitivity 100% on the emergency vignette set — a single miss blocks release. Under-triage under 2% against clinician reference. Specialty routing accuracy reported. Over-triage reported and not optimised downward.

### M4 — Voice and language
ASR integration, one Indian language end to end, code-switch handling.

**Gate:** WER reported overall and separately on drug names and anatomical terms, per language. M3 clinical metrics re-run on voice input and unchanged within tolerance.

### M5 — Hardening
Full eval suite, latency and load testing, audit completeness, deployment packaging.

**Gate:** p95 turn latency inside budget on target hardware. Every decision in a sample session reconstructable from the audit log alone. One-command deploy from clean machine.

**M4 does not start before M3's numbers are published.** Language support on an unevaluated triage layer produces an impressive demo and an unsafe product.

---

## 8. Open questions requiring a decision before build

These are blocking and cannot be resolved by the coding agent.

1. **Clinician reviewer.** Who signs off red flag criteria and vignette reference labels? Without this the eval numbers are unfounded. Ideally two reviewers with a disagreement protocol.

2. **Target hardware.** Exact laptop spec — RAM, VRAM if any, CPU. Determines model size and whether the triage agent can be larger than the intake agent.

3. **First language after English.** Determines the ASR fine-tuning set.

4. **SNOMED CT licensing.** Confirm the licensing position for India before building a dependency on it. ICD-10 is the fallback.

5. **Facility data source.** Where does the capability-tagged facility index come from, and how is it kept current? Distance-only fallback is specified but should not be the permanent state.

6. **Deployment target.** Single laptop for demo, or clinic server? Changes the concurrency and persistence assumptions.
