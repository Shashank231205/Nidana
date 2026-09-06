# Nidana — Engineering Rules

These are binding. A pull request that violates them does not merge.

---

## 1. Repository layout

```
nidana/
├── docs/
│   ├── PRD.md
│   ├── ENGINEERING_RULES.md
│   └── adr/                      architecture decision records
├── prompts/
│   ├── intake_agent.md
│   ├── triage_agent.md
│   ├── structuring_agent.md
│   ├── safety_critic.md
│   └── CHANGELOG.md              every prompt edit, with eval delta
├── rules/
│   ├── red_flags/*.yaml          declarative, cited, versioned
│   └── routing/*.yaml
├── services/
│   ├── api/                      FastAPI, HTTP boundary only
│   ├── agents/                   one module per agent
│   ├── clinical/                 red flags, urgency, routing — no models
│   ├── terminology/              SNOMED, ICD-10 lookup
│   ├── asr/
│   └── persistence/
├── packages/
│   ├── schemas/                  Pydantic models, single source of truth
│   └── fhir/                     FHIR R4 mapping
├── eval/
│   ├── vignettes/                reference cases with clinician labels
│   ├── harness/
│   └── reports/                  committed, dated, never overwritten
├── web/
│   ├── patient/
│   └── clinician/
├── infra/
│   ├── docker/
│   ├── compose.yaml
│   └── migrations/
└── tests/
```

Rules that follow from this layout:

`services/clinical/` contains **no model calls**. If you find yourself importing an inference client there, the design is wrong.

`packages/schemas/` is the only place a clinical data shape is defined. Agents, API, persistence, and FHIR mapping all import from it. No parallel definitions.

`prompts/` holds prompts as files, versioned in git, loaded at runtime. Prompts are never string literals in application code.

---

## 2. Code

**No comments that restate the code.** If a line needs explaining, the names are wrong. Fix the names.

```python
# banned
# increment the counter
counter += 1

# banned
# This function checks red flags
def check(record): ...
```

Comments are permitted for exactly three things: a clinical citation next to a threshold, a workaround with a linked issue, and a non-obvious performance decision with the measurement that justified it.

```python
# ESI level 2 threshold; source: AHRQ ESI handbook v4, verified 2026-03-11
TACHYCARDIA_THRESHOLD_BPM = 100
```

**Type everything.** Python is fully annotated. `mypy --strict` passes. TypeScript is `strict: true` with no `any`.

**No bare exceptions.** Catch the specific error, or let it propagate.

**Functions do one thing.** If you need "and" to describe it, split it.

**No magic values.** Every clinical constant is named, and carries its source.

**Pure clinical logic.** Functions in `services/clinical/` take a record and return a decision. No I/O, no clock reads, no randomness. This is what makes them testable, and they must be exhaustively tested.

**Errors say what to do.** `"Facility index stale (last updated 2026-08-02); run scripts/refresh_facilities.py"` — not `"Error loading facilities"`.

---

## 3. Agents and prompts

**One agent, one job.** The intake agent conducts conversation. It does not triage. Merging responsibilities is how clinical conclusions leak into patient-facing text.

**Prompts live in `prompts/*.md`, versioned, loaded at runtime.** Every prompt file carries a version header. Every model call logs the prompt version it used.

**Every prompt edit runs the eval suite.** The result goes in `prompts/CHANGELOG.md` with the before/after numbers. A prompt change with no eval run does not merge.

**Structured output is enforced, not requested.** Use grammar-constrained decoding or a schema-validating parser with retry. "Please respond in JSON" is not a contract. Parse failures are logged and retried once, then fail loudly.

**One inference adapter.** Every model call goes through `services/agents/adapter.py`. Model identity, quantisation, and sampling parameters are configuration. Swapping models is a config change and an eval re-run.

**Model temperature for clinical reasoning is 0.** Conversational phrasing may use a low non-zero temperature. Triage may not.

**Never let a model decide something a rule can decide.** Red flags, urgency thresholds, routing, and interaction checks are deterministic code. The model handles language.

---

## 4. Safety invariants

These are enforced in code and covered by tests that cannot be skipped.

1. The red flag engine runs on every turn, before the intake agent produces its next question.
2. The safety critic may raise urgency. It may never lower it. Enforced by type, not by prompt.
3. No clinical finding appears in any output without a traceable source utterance. Findings carry a source span; a finding without one fails schema validation and never renders.
4. No condition name appears in patient-facing output. Enforced by an output filter with tests.
5. Every non-U1 outcome carries return criteria. A response without them fails validation.
6. Session audit entries are append-only. There is no update path in the persistence layer.

---

## 5. Data and database

**Postgres.** Migrations via Alembic, forward-only, reviewed like code. No schema changes outside migrations.

**Separation.** Patient identifiers live in one table with restricted access. Clinical content references a pseudonymous session id. A dump of the clinical tables is not a breach.

**Append-only where it matters.** Session events, decisions, and audit entries have no UPDATE or DELETE path. Corrections are new rows referencing the prior one.

**JSONB for the clinical record, columns for anything queried.** Urgency band, specialty, timestamps, and red flag ids are columns and indexed.

**Every table has `created_at`, and it is set by the database, not the application.**

**Seed data is code.** Facility index, terminology subsets, and rule sets load through versioned scripts. No manual inserts.

---

## 6. Docker

Everything runs with `docker compose up`. There is no "first install these seventeen things" step.

- Multi-stage builds. Runtime images carry no build toolchain.
- Non-root user in every container.
- Pinned base images by digest, not by tag.
- Model weights mount as a volume, never bake into an image.
- Healthchecks on every service.
- `.env.example` committed with every variable documented. `.env` never committed.
- One compose file for development with hot reload, one for production.
- GPU is optional. CPU-only must work, with a documented latency penalty.

---

## 7. Testing

**Clinical logic: exhaustive.** Every red flag rule has positive cases, negative cases, and boundary cases. Every paediatric and pregnancy modifier is separately tested. Coverage on `services/clinical/` is 100% and the build enforces it.

**Agents: eval suite, not unit tests.** Vignettes with reference labels, scored on the metrics in the PRD. Runs in CI on every prompt or model change.

**Golden transcripts.** A set of conversations with expected structured output, run on every change to the structuring agent.

**Adversarial set.** Patients who minimise ("it's probably nothing, but"), who bury the red flag mid-sentence, who answer a different question than the one asked, who switch language mid-conversation, who are describing someone else's symptoms. These break naive implementations and belong in CI.

**No mocking the clinical layer in integration tests.** Mock the model. Never mock the safety rules.

---

## 8. Frontend

**No component library defaults on display.** Design tokens defined once, in one file, and used everywhere.

**Colour carries clinical meaning only.** Urgency bands own a fixed palette. That palette appears nowhere decorative.

**Voice-first on the patient surface.** Everything reachable without a keyboard.

**Accessible floor, unannounced.** Keyboard focus visible, contrast ratios met, screen-reader labels present, reduced motion respected, works at 320px.

**No generated-app tells.** No gradient hero, no identical rounded cards for dissimilar content, no all-caps eyebrow labels, no emoji, no arrows appended to buttons, no fade-and-slide-up on every section.

**Loading states show what is happening.** "Checking nearby hospitals" — not a spinner.

**Design decisions wait for the reference screenshots.** Until those exist, build with unstyled semantic markup and correct structure.

---

## 9. Git

**Commit messages describe the change and its reason.**

```
Add ectopic pregnancy red flag rule

Fires on abdominal pain with amenorrhoea or positive pregnancy
test. Terminates the session and requires an obstetric-capable
facility. Criteria pending clinician review before release.
```

**No AI attribution anywhere.** Not in commit messages, not in trailers, not in co-author lines, not in code comments, not in the README, not in PR descriptions. The work is authored by you.

**Conventional prefixes:** `feat:` `fix:` `clinical:` `prompt:` `infra:` `docs:` `test:`

`clinical:` and `prompt:` commits must include the eval report path in the body.

**Small commits.** One logical change.

**Branch per change, PR to main, CI green before merge.**

**Tag releases. Record the model versions and rule-set version in the release notes.** A clinical decision must be reproducible from a tag.

---

## 10. Decision records

Any decision that is expensive to reverse gets a short ADR in `docs/adr/`: context, options considered, decision, consequences. Half a page. Numbered sequentially.

Candidates: model selection, whether to run the safety critic on every case or only on high-stakes bands, the terminology mapping approach, the persistence schema for the clinical record.

---

## 11. What is never acceptable

Model output rendered to a patient without passing the output filter.

A red flag threshold committed without its source cited.

A prompt change merged without an eval run.

Fabricated clinical content — including in fixtures, demos, and seed data. If a vignette needs a case, it comes from a published source or a clinician wrote it.

Committed model weights, patient data, or `.env`.

A clinical constant hard-coded in application logic instead of in `rules/`.
