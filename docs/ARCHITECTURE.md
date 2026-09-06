# Nidana — Repository Map

Where each thing lives and why. The layout is fixed by
`docs/ENGINEERING_RULES.md` §1; this file explains how to navigate it.

## The one-sentence version

Deterministic clinical logic and generative agents are separate packages that
never import each other, and every clinical shape they exchange is defined once
in `packages/schemas/`.

## Directories

```
nidana/
├── packages/          shapes and mappings — no behaviour
│   ├── schemas/       every clinical data shape, single source of truth
│   └── fhir/          FHIR R4 mapping, nothing but mapping
│
├── services/          behaviour, one job per package
│   ├── clinical/      red flags, bands, routing, sufficiency — NO MODELS
│   ├── agents/        intake, structuring, triage, critic + one adapter
│   ├── terminology/   SNOMED / ICD-10 lookup, deterministic index
│   ├── asr/           transcription, local only
│   ├── persistence/   repositories — no business logic
│   └── api/           FastAPI, HTTP boundary only, delegates everything
│
├── rules/             clinical content, declarative, cited, versioned
│   ├── fields/        required + optional fields per complaint family
│   ├── predicates/    named tests over registry fields
│   ├── red_flags/     rules that can terminate a session
│   └── routing/       specialty and capability mapping
│
├── prompts/           agent prompts as files, loaded at runtime
├── eval/              vignettes, harness, dated reports
├── web/               patient and clinician surfaces
├── infra/             docker, compose, migrations
├── tests/             mirrors the services/ and packages/ tree
├── scripts/           operational entry points
└── docs/              PRD, build spec, engineering rules, ADRs
```

## The boundaries that matter

**`services/clinical/` imports no inference client.** Red flags, urgency
thresholds, routing, and interaction checks are deterministic code. Anything
where being wrong causes physical harm is a rule, not a generation.

**`services/agents/` holds no clinical threshold.** Agents handle language.
They elicit and structure; they never decide.

**Every clinical shape is defined in `packages/schemas/`.** Agents, API,
persistence, and FHIR mapping import from it. There are no parallel
definitions inside a service.

**Rules are data, not code.** A clinical constant lives in `rules/`, carries
its source citation, and is loaded and validated at startup. It is never
hard-coded in application logic.

**Prompts are files.** `prompts/*.md`, versioned in git, loaded at runtime,
never a string literal.

## Reading order for someone new

1. `docs/PRD.md` §3 — the scope boundary. Nidana triages; it does not diagnose.
2. `docs/BUILD_SPEC.md` §2 — the core schemas.
3. `docs/adr/` — seven decisions where the spec, taken literally, could not be
   implemented safely. Read 0002 and 0004 first; they carry the two strongest
   safety invariants.
4. `packages/schemas/` — the shapes themselves.
5. `services/clinical/` — what the system decides without a model.

## Where to add something

| Adding | Goes in |
|---|---|
| A clinical data shape | `packages/schemas/` |
| A red flag rule | `rules/red_flags/`, with a citation |
| A new complaint family | `rules/fields/<family>.yaml` + a registry enum member |
| A rule atom | `rules/predicates/`, then reference it |
| An agent | `prompts/<name>.md` + `services/agents/<name>.py` |
| An endpoint | `services/api/`, delegating to a service |
| A migration | `infra/migrations/`, forward-only |
