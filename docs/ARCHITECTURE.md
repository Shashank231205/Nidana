# Nidana — Repository Map

Where each thing lives and why.

## The one-sentence version

One shared spine, five self-contained services that use it and never import each
other, and deterministic clinical logic kept in separate packages from anything
generative.

## Top level

```
nidana/
├── spine/                shared by all five services — built once
│   ├── schemas/          every clinical shape: record, finding, provenance, band
│   ├── rules/            the rule engine, predicate evaluation, loaders
│   ├── terminology/      SNOMED CT and ICD-10 lookup
│   ├── audit/            append-only, hash-chained
│   ├── inference/        the one adapter every model call goes through
│   ├── identity/         patient resolution across services
│   ├── persistence/      repositories
│   └── fhir/             FHIR R4 mapping
│
├── services/             one folder per service, each self-contained
│   ├── consult/          S1 · triage and routing        · in build
│   ├── scribe/           S2 · consultation documentation · planned
│   ├── rx/               S3 · prescription intelligence  · planned
│   ├── labs/             S4 · report interpretation      · planned
│   └── forensics/        S5 · medico-legal, isolated     · planned
│
├── web/
│   ├── patient/          voice-first, one question at a time
│   └── clinician/        dense, scannable in fifteen seconds
│
├── infra/                docker, compose, migrations
├── tests/                mirrors spine/ and services/
├── scripts/              operational entry points
└── docs/                 PRD, build spec, engineering rules, ADRs
```

## Inside a service

Every service has the same seven folders, so knowing one means knowing all five.

```
services/<name>/
├── clinical/     deterministic checks     · never a model call
├── agents/       its agents               · never a clinical threshold
├── prompts/      *.md, loaded at runtime  · never a string literal
├── rules/        declarative, cited YAML  · never logic
├── api/          HTTP routes              · never clinical reasoning
├── eval/         vignettes, harness, reports
└── README.md     what it is, what is built, what is not
```

Consult additionally has `asr/`, because voice is its input path.

## The boundaries

**Nothing in `spine/` imports from a service.** The spine is the foundation; it
does not know who stands on it.

**No service imports another service.** Shared behaviour goes in the spine or it
is duplicated deliberately.

**`services/*/clinical/` imports no inference client.** Anything where being
wrong causes physical harm is a rule, not a generation.

**`services/*/agents/` holds no clinical threshold.** Agents handle language.
They elicit, transcribe, extract, and phrase; they never decide.

**Every clinical shape is defined in `spine/schemas/`.** No parallel definitions.

**The spine holds the engine, the service holds the rules.** Rule content lives
at `services/<name>/rules/` because Consult's red flags are not Rx's interaction
checks.

**Forensics reads nothing.** It uses the spine's shapes and writes its own chain.
It does not read the shared record, by design.

## Reading order for someone new

1. `docs/PRD.md` — the product and the scope boundary.
2. `docs/BUILD_SPEC.md` — the data model and the milestone gates.
3. `docs/adr/` — seven decisions where the spec, taken literally, could not be
   implemented safely. Read 0002 and 0004 first.
4. `spine/README.md` — the three things that matter most.
5. `spine/schemas/` — the shapes themselves.
6. `services/consult/README.md` — the first service, end to end.

## Where to add something

| Adding | Goes in |
|---|---|
| A clinical data shape | `spine/schemas/` |
| A rule-engine capability | `spine/rules/` |
| A red flag rule | `services/consult/rules/red_flags/`, with a citation |
| An interaction check | `services/rx/rules/` |
| A new complaint family | `services/consult/rules/fields/<family>.yaml` + an enum member |
| A rule atom | `services/<name>/rules/predicates/`, then reference it |
| An agent | `services/<name>/prompts/<agent>.md` + `services/<name>/agents/<agent>.py` |
| An endpoint | `services/<name>/api/`, delegating to that service |
| A migration | `infra/migrations/`, forward-only |
