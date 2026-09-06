# CLAUDE.md

Operating rules for this repository. Read fully before the first edit of any session.

Project: **Nidana** — on-premise clinical intelligence platform for Indian healthcare.
Current scope: **Module 1, nidana-consult**. Nothing else is being built.

Read `docs/PRD.md` for what the product is. Read `docs/BUILD_SPEC.md` for the data model, API surface, and milestone gates. This file governs how you work.

---

## 1. Before you write anything

**Check the milestone.** `docs/BUILD_SPEC.md` defines M1 through M5 with acceptance gates. Work only on the current milestone. If asked to build something from a later milestone, say so and ask whether to proceed out of order rather than silently doing it.

**Check the schema.** `packages/schemas/` is the single source of truth for every clinical data shape. If a shape you need is not there, add it there first, then use it. Never define a parallel shape inside a service.

**Do not invent clinical content.** Not thresholds, not criteria, not drug names, not vignettes, not seed data. If a clinical value is needed and not supplied in `rules/`, stop and ask. A plausible-looking fabricated threshold is the most dangerous thing you can produce in this repo.

**Ask rather than assume on anything clinical.** Guessing at architecture is recoverable. Guessing at a red flag criterion is not.

---

## 2. Hard constraints

These are not preferences. Violating any of them means the change is wrong regardless of how well it works.

1. **`services/clinical/` contains no model calls.** Red flags, urgency thresholds, routing, and interaction checks are deterministic code. If you are importing an inference client into that package, the design is wrong — stop and reconsider.

2. **Every clinical finding carries a source span.** A finding without a span fails schema validation and is dropped. There is no path by which a model-inferred fact enters the record.

3. **The safety critic may raise urgency and may never lower it.** Enforce this in the type system, not in a prompt. A function that returns a band must be incapable of returning a lower one.

4. **No condition name reaches patient-facing output.** There is an output filter. It has tests. Do not route around it.

5. **Every non-U1 outcome carries return criteria.** A response without them fails validation.

6. **Audit entries are append-only.** No UPDATE, no DELETE, no soft-delete flag. Corrections are new rows referencing the prior one.

7. **No network egress from the inference path.** Everything runs locally. If you add a dependency that phones home, remove it.

---

## 3. Code standards

**No comments that restate code.** If a line needs explaining, rename things. Comments are permitted for three things only: a clinical citation beside a constant, a workaround with a linked issue, a performance decision with the measurement behind it.

```python
# ESI level 2 threshold; AHRQ ESI handbook v4, verified 2026-03-11
TACHYCARDIA_THRESHOLD_BPM = 100
```

**Full typing.** `mypy --strict` passes. TypeScript is `strict: true`, no `any`, no `as` casts to escape a type error.

**No bare `except`.** Catch the specific error or let it propagate.

**Pure functions in `services/clinical/`.** Record in, decision out. No I/O, no clock reads, no randomness. This is what makes them exhaustively testable.

**No magic values.** Every clinical constant is named and lives in `rules/`, not in application code.

**Errors state the remedy.** `"Facility index stale (last updated 2026-08-02); run scripts/refresh_facilities.py"` — not `"Error loading facilities"`.

**Small functions.** If describing it needs "and", split it.

---

## 4. Writing agent prompts

You will author the agent prompts. They are the highest-leverage artefacts in the repo and they follow a fixed standard.

**Location and form.** `prompts/<agent_name>.md`. Markdown, versioned in git, loaded at runtime. Never a string literal in application code.

**Header block.** Every prompt opens with version, module, model class, temperature, max output tokens, owner.

**Required sections, in this order:**

```
ROLE          who the model is being, in professional terms
TASK          the single job, stated once, plus what is explicitly not the job
CONTEXT       who the user is, what the agent receives, what runs alongside it,
              what it must never do
PRINCIPLES    the operating rules that govern every turn
PROTOCOL      the actual procedure, in the order it happens
DO / DO NOT   paired examples, wrong version first, right version second
OUTPUT        exact schema, with rules on each field
FAILURE MODES the specific ways this agent drifts, named so it can self-check
```

**Depth expectation.** These run long — 250 to 400 lines is normal for a clinical agent. Length comes from concrete paired examples and from enumerating the actual clinical fields, never from restating the same instruction in different words. If a section is padding, cut it.

**Reference exemplars.** `prompts/intake_agent.md` and `prompts/triage_agent.md` are the standard. Match their specificity, their example density, and their tone. Do not match their length as a target.

**Examples must be real.** Paired do/do-not examples use realistic patient utterances, including code-switched ones. The wrong version must be the plausible failure, not a strawman.

**One agent, one job.** If a prompt needs two ROLE paragraphs, it is two agents.

**Temperature 0 for anything clinical.** Conversational phrasing may use low non-zero. Reasoning may not.

**Structured output is enforced, not requested.** Grammar-constrained decoding or schema-validating parse with one retry, then loud failure. "Please respond in JSON" is not a contract.

**Every prompt edit runs the eval suite.** Result goes in `prompts/CHANGELOG.md` with before and after numbers. A prompt change with no eval run does not merge.

---

## 5. Testing

**`services/clinical/` is at 100% coverage and the build enforces it.** Every red flag rule gets positive, negative, and boundary cases. Paediatric and pregnancy modifiers are tested separately.

**Agents are evaluated, not unit tested.** Vignettes with clinician reference labels, scored on the PRD metrics.

**Never mock the clinical layer.** Mock the model. The safety rules run for real in every integration test.

**Adversarial cases belong in CI:** patients who minimise, who bury the red flag mid-sentence, who answer a different question, who switch language mid-conversation, who are describing someone else's symptoms.

**Golden transcripts** for the structuring agent — fixed conversations with expected structured output.

---

## 6. Git

**No AI attribution anywhere.** Not in commit messages, not in trailers, not in co-author lines, not in comments, not in the README, not in PR bodies. The work is authored by the repository owner.

**Prefixes:** `feat:` `fix:` `clinical:` `prompt:` `infra:` `docs:` `test:`

`clinical:` and `prompt:` commits include the eval report path in the body.

**Messages explain the reason, not the diff.**

```
clinical: add ectopic pregnancy red flag

Fires on abdominal pain with amenorrhoea or positive pregnancy test.
Terminates session, requires obstetric-capable facility. Criteria
pending clinician sign-off before release.

eval: eval/reports/2026-09-06-redflag-v3.json
```

**One logical change per commit. Branch per change. CI green before merge.**

**Release tags record model versions and rule-set version.** A clinical decision must be reproducible from a tag.

---

## 7. Frontend

**Wait for the reference screenshots before making visual decisions.** Until they exist, build semantic unstyled markup with correct structure and accessibility.

**Colour carries clinical meaning only.** Urgency bands own a fixed palette; that palette appears nowhere decorative.

**Do not produce the default generated-app look.** No gradient hero, no identical rounded cards for dissimilar content, no all-caps eyebrow labels, no emoji in the UI, no arrows appended to button text, no fade-and-slide-up on every section, no soft grey shadow under everything.

**Accessible floor, unannounced.** Visible keyboard focus, contrast ratios met, screen-reader labels, reduced motion respected, works at 320px.

**Loading states name the operation.** "Checking nearby hospitals" — not a spinner.

**Patient surface is voice-first.** Everything reachable without a keyboard.

---

## 8. When you finish a task

State plainly:

- What changed, at file level
- What you did not do that the task implied, and why
- Any clinical value you needed and did not have
- Whether the eval suite ran, and the delta if it did

Do not summarise the code back. Do not claim something works without having run it.

---

## 9. Never

Render model output to a patient without the output filter.

Commit a clinical threshold without its source cited.

Merge a prompt change without an eval run.

Fabricate clinical content, including in fixtures, demos, and seed data.

Commit model weights, patient data, or `.env`.

Hard-code a clinical constant in application logic instead of `rules/`.

Let a model decide something a rule can decide.
