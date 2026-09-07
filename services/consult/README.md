# S1 Consult

Conversational triage and routing. The first service, and the one whose
evaluation harness the other four reuse.

**Status:** runs end to end. Phase P1.

Every component below exists and is tested. What blocks release is clinical
governance rather than engineering: thirty of thirty-one red flag criteria
carry `verify_before_ship`, and a release build refuses to start while they do.

## The job

A person is unwell and does not know what to do. Consult takes a structured
history one question at a time, identifies emergencies immediately, assigns an
urgency band, routes to a specialty, and hands the clinician a summary so the
consultation starts from minute three rather than minute zero.

It does not diagnose. No condition name reaches the patient.

## Layout

| Folder | Holds | Never holds |
|---|---|---|
| `clinical/` | red flags, bands, routing, sufficiency | a model call |
| `agents/` | intake, structuring, triage, safety critic | a clinical threshold |
| `prompts/` | the agent prompts, loaded at runtime | anything in a string literal |
| `rules/` | `fields/`, `predicates/`, `red_flags/`, `routing/` | logic |
| `api/` | FastAPI routes | clinical reasoning |
| `asr/` | transcription | anything downstream of it |
| `eval/` | vignettes, harness, dated reports | anything uncommitted |

## The pipeline

```
audio/text
    │
    ▼
  ASR ──► INTAKE ──────► RED FLAG ENGINE      deterministic, every turn,
          conversation   no model              can end the session
              │
              ▼
        STRUCTURING      utterances → typed findings → SNOMED → FHIR
              │
              ▼
          TRIAGE ──────► SAFETY CRITIC        may raise urgency,
          band,                                never lower it
          specialty
              │
              ▼
     ROUTING RESOLVER    specialty + geo + capability, no model
```

Three of the eight boxes are models. The rest are rules.

## Invariants

Red flags run every turn, before the intake agent speaks.

`escalate_only` is the only function that writes a band. It cannot return a
less urgent band than its input, and a test enumerates all 25 ordered pairs.

Every finding carries provenance that verifies as an exact substring of what
the patient said. A paraphrase fails validation rather than being stored.

Every band below U1 carries three to five return criteria.

## Running the checks

```
pytest tests/consult tests/spine
mypy spine services tests
ruff check spine services tests
```
