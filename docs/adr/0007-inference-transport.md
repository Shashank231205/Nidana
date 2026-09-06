# ADR 0007 — Local inference, with hosted providers gated to development

Status: accepted
Date: 2026-09-06

## Context

`docs/PRD.md` §4.7 states all models are local and nothing leaves the machine.
`CLAUDE.md` §2.7 forbids network egress from the inference path. `docs/PRD.md` §2
gives the reason: clinics distrust cloud vendors and the DPDP position is
unsettled. On-premise operation is stated as a requirement, not an optimisation.

The owner has asked for OpenRouter (Grok), Gemini, and Whisper from Hugging Face.

Whisper is not in conflict — it is downloaded once and runs locally, which is what
§4.7 specifies. OpenRouter and Gemini are hosted inference: patient utterances
leave the machine on every turn.

There is a real development need behind the request. Local model iteration is slow
on a laptop, and the eval suite is easier to bring up against a capable hosted
model before a local one is tuned.

## Options

1. Use hosted providers. Abandon the on-premise claim.
2. Local only. Accept slower development iteration.
3. One adapter interface, two transports, hosted refused in production mode.

## Decision

Option 3.

- `services/agents/adapter.py` exposes one interface. `LocalProvider` targets
  Ollama; `HostedProvider` targets OpenRouter and Gemini.
- Both support a primary model plus an ordered fallback chain.
- `NIDANA_MODE=production` refuses to start when
  `NIDANA_INFERENCE_TRANSPORT=hosted`. The check is a startup assertion with a
  test, not a configuration convention.
- Every inference call logs its transport, provider, model version, and prompt
  version to the audit log. A session run against a hosted provider is
  identifiable as such after the fact.
- ASR is local in all modes. There is no hosted ASR transport.

## Consequences

Development and eval can run against Grok or Gemini today at no cost. A clinic
deployment cannot leak, because it cannot boot in a leaking configuration.

Eval numbers produced under the hosted transport are not valid evidence for a
local deployment — different model, different behaviour. Eval reports record the
transport, and the M2 and M3 gates are met under the local transport or not at
all.

This is M2 and M4 work. M1 contains no inference and no adapter.

Reconciles the owner's instruction with `docs/PRD.md` §4.7 and `CLAUDE.md` §2.7
rather than overriding either.
