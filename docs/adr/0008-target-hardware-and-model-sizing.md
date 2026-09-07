# ADR 0008 — Target hardware fixes model sizing

Status: accepted
Date: 2026-09-07

## Context

`docs/BUILD_SPEC.md` §8 lists target hardware as a blocking question: "Exact
laptop spec — RAM, VRAM if any, CPU. Determines model size and whether the
triage agent can be larger than the intake agent."

The development machine has been measured:

- 16GB system RAM
- NVIDIA RTX 3050 Laptop, **4GB VRAM**
- Intel i7-11800H, 8 physical cores
- 286GB free disk

`docs/PRD.md` §4.7 sets a latency budget of under 1.5 seconds per intake turn
and suggests the triage agent may be larger than the intake agent "where
hardware allows".

## The constraint is VRAM, not RAM

16GB of system RAM is comfortable. 4GB of VRAM is not, and it is the number that
decides model size.

A 7B model at q4_K_M quantisation is roughly 4.7GB of weights. That does not fit
in 4GB, so Ollama splits layers between GPU and CPU. The model runs; each token
costs more. A 9B model at the same quantisation is roughly 5.8GB and runs almost
entirely on CPU, which will not hold a 1.5 second turn.

Running two different models — a larger one for triage, a smaller one for intake
— makes this worse rather than better on this hardware. Both would contend for
the same 4GB, and the swap between them costs a model load on the turn where
triage runs.

## Options

1. Larger model for triage, smaller for intake, as the PRD contemplates.
2. One 7B model for every agent.
3. One 3B model everywhere, to fit fully in VRAM.

## Decision

Option 2. One 7B q4_K_M model serves all four agents on this hardware.

`qwen2.5:7b-instruct-q4_K_M` is the primary. The reason is not general capability
but language coverage: the hardest requirement in this product is code-switched
Hindi, Kannada, Marathi, Bengali and Tamil, and Qwen covers those better than
same-sized alternatives. It also emits reliable JSON, which the structuring
agent depends on and which is otherwise the most common cause of a retry.

The fallback chain is `llama3.1:8b-instruct-q4_K_M`, then
`qwen2.5:3b-instruct-q4_K_M`. The 3B entry exists so a weaker machine still runs
rather than failing to start.

Option 1 is not refused in principle. It is refused on this hardware, and the
adapter already supports per-agent model specs, so a clinic server with a larger
card can adopt it as a config change.

## Consequences

Model choice stays configuration. Nothing in this ADR is compiled into code;
`NIDANA_MODEL_PRIMARY` and `NIDANA_MODEL_FALLBACKS` carry it.

Eval reports must record which model actually answered, because the fallback
chain means it is not always the primary. `Completion.used_fallback` carries
this and the audit log records `model_version`.

The 1.5 second budget is measured, not assumed. If a 7B split across GPU and CPU
does not hold it, the choice is a 3B model or a longer budget, and that is a
decision for the M5 latency numbers rather than a guess now.

Answers question 4 of `docs/BUILD_SPEC.md` §8 for the development machine. A
clinic deployment target is still open, and changes this ADR if its hardware
differs.
