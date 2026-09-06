# Nidana — Product Requirements Document

Version 0.1 · Draft · Owner: Shashank Kasamshetty

---

## 1. What this is

Nidana is a clinical intelligence platform for Indian healthcare. It runs on-premise, including on a single laptop, and produces one structured clinical record per patient encounter. Five modules consume that record.

The record is the product. The modules are surfaces on it.

| Module | Name | Primary user | Status |
|---|---|---|---|
| 1 | Consult — conversational triage and routing | Patient, then physician | **In scope now** |
| 2 | Scribe — ambient consultation documentation | Physician | Planned |
| 3 | Rx — prescription intelligence | Patient, pharmacist | Planned |
| 4 | Labs — diagnostic report interpretation | Patient, physician | Planned |
| 5 | Forensics — medico-legal documentation | Casualty medical officer | Planned |

Modules ship one at a time, each to production quality. Module 1 is fully specified in this document. Modules 2–5 have scope stubs in Appendix A and get their own PRDs when they start.

---

## 2. Why this exists

Three facts drive the design.

**Indian patients arrive undirected.** There is no gatekeeping GP layer. People self-refer to specialists, walk into diagnostic chains and order their own tests, and consult three doctors for one problem without any of them seeing the other two's notes. The result is delay in the cases that need speed and over-consumption in the cases that do not.

**Consultations are multilingual and code-switched.** A patient describes symptoms in Kannada, the doctor asks in English, the answer comes back mixed. Every commercial product in this category is English-monolingual. This is the largest single technical gap in the market and the hardest part of the build.

**Health data does not leave the premises willingly.** Clinics distrust cloud vendors, and the regulatory position under the DPDP Act 2023 is still settling. On-premise operation is a requirement, not an optimisation.

---

## 3. Scope boundary — read this before designing anything

**Nidana performs triage, documentation, and routing. Nidana does not diagnose.**

This is a product decision, not timidity.

A diagnosis is unfalsifiable at demo time and untestable in evaluation. A triage decision is neither — urgency banding and specialist routing can be scored against a labelled dataset, reported as a confusion matrix, and defended in a README. The evaluable product is also the better product.

The regulatory consequence matters too. Software that outputs a diagnosis or a treatment decision is a medical device under most frameworks, including CDSCO's medical device rules. Software that structures documentation and routes patients is not. Abridge and Nabla are both large businesses and neither diagnoses.

Three concrete rules follow.

1. **Patient-facing output contains urgency, specialist, red flags, and what to watch for.** Never a condition name.
2. **Clinician-facing output may contain a ranked differential**, clearly labelled as decision support for a qualified professional, with the evidence for each entry.
3. **Nothing generative can create a clinical finding.** The model elicits and structures. It never invents a symptom, a measurement, or a history item the patient did not state.

---

## 4. Module 1 — Nidana Consult

### 4.1 The job

A person is unwell and does not know what to do about it. Consult conducts a structured clinical history, identifies emergencies immediately, assigns an urgency band, routes to the right specialist, finds appropriate nearby facilities, and hands the physician a structured summary so the actual consultation starts from minute three instead of minute zero.

### 4.2 It must not sound like AI

This is a functional requirement, not polish. If it reads as a chatbot, users disclose less, and disclosure is the entire input to the system.

**One question per turn.** Not two. Not a comma-joined list.

**No emotional preamble.** No "I understand that must be difficult." A clinician says "Since when?"

**Next question determined by last answer.** This is the actual mechanism behind the feeling of talking to a doctor. The question path is a state machine derived from clinical history-taking frameworks; the model selects the next node and phrases it naturally. It does not free-associate questions.

**No summarising back unless confirming something clinically critical.** "So you're saying you've had chest pain for two days" is chatbot behaviour. Confirm only allergies, current medications, and pregnancy status.

Compare:

> **Wrong:** I'm sorry to hear you're experiencing chest discomfort. To help me better understand your situation, could you tell me about the duration, severity, and any associated symptoms you may be experiencing?

> **Right:** Since when?

### 4.3 Sub-features

**4.3.1 Multimodal intake**
Text and voice. Voice is the primary path — it is faster for the elderly and for low-literacy users, and it is how the target user actually talks. Transcription runs locally.

**4.3.2 Code-switched language handling**
Hindi, Kannada, Marathi, Bengali, Tamil mixed with English, in Devanagari, native script, or Roman transliteration ("pet mein dard"). Output language matches the user's dominant language, not the script they typed in.

**4.3.3 Adaptive history taking**
Question paths follow established frameworks — OPQRST and SOCRATES for pain, structured screens for the common presenting complaint families. Each answer narrows the next question. Target: sufficient history in 8–14 turns.

**4.3.4 Red flag engine**
Deterministic rules, evaluated on every turn, with authority to terminate the conversation. Not a prompt instruction — code. Described in 4.5.

**4.3.5 Structured symptom record**
Every elicited fact lands in a typed structure, coded to SNOMED CT where a mapping exists, emitted as FHIR R4 resources.

**4.3.6 Urgency banding**
Five levels, modelled on the Emergency Severity Index and the Manchester Triage System, adapted to an Indian outpatient context where "emergency department" is not always the right destination.

**4.3.7 Specialist routing**
Maps the structured presentation to a specialty. Handles the common Indian misrouting patterns explicitly — chest pain going to a general physician when it should go to cardiology, and its inverse, dyspepsia going to cardiology out of fear.

**4.3.8 Facility recommendation with capability matching**
Not nearest-by-distance. A STEMI needs a facility with a catheterisation lab; a suspected stroke needs CT plus thrombolysis capability within the window. The facility index stores capabilities, not just coordinates. Falls back to distance-only when capability data is unavailable, and says so.

**4.3.9 Clinician handoff packet**
Structured history, timeline, red flags fired, ranked differential with supporting and opposing evidence, and suggested examination and investigations. Every line traceable to a patient utterance.

**4.3.10 Patient summary**
Same encounter in the patient's language at roughly a class-6 reading level. What to do, when, what would make it urgent.

**4.3.11 Session audit log**
Append-only. Every model call, prompt version, rule fired, and decision, with timestamps. Required for defending any decision after the fact.

**4.3.12 Escalation to human**
Any moment, any turn, by request or by rule.

### 4.4 Agent architecture

Five components. Only three are models.

```
audio/text
    │
    ▼
┌─────────────────┐
│  ASR            │  local, streaming, code-switch aware
└────────┬────────┘
         ▼
┌─────────────────┐        ┌──────────────────────┐
│  INTAKE AGENT   │◄──────►│  RED FLAG ENGINE     │  deterministic
│  conversation   │        │  runs every turn     │  can halt session
│  only           │        │  no model            │
└────────┬────────┘        └──────────────────────┘
         ▼
┌─────────────────┐
│  STRUCTURING    │  utterances → typed record → SNOMED → FHIR
│  AGENT          │  constrained decoding, schema-validated
└────────┬────────┘
         ▼
┌─────────────────┐        ┌──────────────────────┐
│  TRIAGE AGENT   │───────►│  SAFETY CRITIC       │  second pass
│  urgency,       │        │  can only escalate   │
│  specialty,     │◄───────│  urgency, never      │
│  differential   │        │  reduce it           │
└────────┬────────┘        └──────────────────────┘
         ▼
┌─────────────────┐
│  ROUTING        │  deterministic; specialty + geo + capability
│  RESOLVER       │  no model
└─────────────────┘
```

Design rules for this graph:

- **The intake agent never reasons about diagnosis.** It elicits. Giving it both jobs is what makes chatbots leak premature conclusions to patients.
- **Every downstream component consumes the structured record, not the transcript.** This is what makes the record portable to modules 2–5.
- **The safety critic is asymmetric.** It may raise urgency. It may never lower it. A disagreement between triage and critic resolves upward, always.
- **Red flags and routing contain no model.** Anything where being wrong causes physical harm is deterministic and unit-tested.

### 4.5 Red flag engine

Runs after every patient turn against the accumulated record. On fire: conversation terminates, emergency instruction renders, facility lookup switches to emergency-capable only, session is flagged in the audit log.

Rules are declarative YAML, versioned in the repo, each carrying a citation to its clinical source.

```yaml
- id: RF_ACS_001
  label: Possible acute coronary syndrome
  any_of:
    - all_of: [chest_pain, radiation_to_jaw_or_left_arm]
    - all_of: [chest_pain, diaphoresis]
    - all_of: [chest_pain, dyspnoea, age_over_40]
  modifiers:
    escalate_if: [diabetes, known_cad, age_over_60]
  action: TERMINATE_EMERGENCY
  facility_capability: [cath_lab, emergency_24x7]
  patient_message_key: acs_emergency
  source: NICE CG95 / AHA-ACC ACS guidance
  verify_before_ship: true
```

Minimum rule set for v1 — each of these needs its threshold and criteria verified against a current published guideline before it ships:

Acute coronary syndrome · stroke (FAST, with time-of-onset capture for the thrombolysis window) · anaphylaxis · sepsis screen · acute abdomen with peritonism · testicular torsion · ectopic pregnancy · obstetric bleeding · meningism · suicidal ideation with plan · paediatric danger signs from WHO IMCI · significant haemoptysis or haematemesis · sudden severe headache · acute vision loss · diabetic ketoacidosis features.

Paediatric and pregnancy modifiers apply across all rules and are separately tested.

### 4.6 Urgency bands

| Band | Meaning | Action |
|---|---|---|
| U1 | Immediate threat to life | Emergency facility now. Session ends. |
| U2 | Urgent, hours matter | Same day, emergency or urgent care |
| U3 | Semi-urgent | Within 24–48 hours, named specialty |
| U4 | Routine | Within a week, named specialty |
| U5 | Self-care with safety net | Home care, explicit return criteria |

Every band below U1 carries **return criteria**: the specific developments that mean the person should reassess immediately. This is the most important patient-facing text the product produces, and it is what makes a non-diagnostic system clinically safe.

### 4.7 Models

All local. Nothing leaves the machine.

| Component | Model | Notes |
|---|---|---|
| ASR | Whisper family, fine-tuned on Indian-accented medical speech | Evaluate AI4Bharat IndicWhisper as a base. Drug names and anatomical terms are the failure surface; they need a targeted fine-tune set. |
| Intake dialogue | 7–8B instruct, quantised | Latency budget under 1.5s per turn on target laptop |
| Structuring | Same base, constrained decoding to schema | Grammar-constrained generation, not prompt-and-hope |
| Triage reasoning | Same base, or a larger model where hardware allows | Config-switchable |
| Embeddings | Multilingual sentence embeddings | For symptom normalisation and terminology mapping |
| Terminology | SNOMED CT + ICD-10 lookup | Deterministic index, no model |

Model choice is configuration, never hard-coded. Every inference call goes through one adapter interface so a model swap is a config change and a re-run of the eval suite.

### 4.8 Evaluation

The product is defined by these numbers, not by the demo.

**Safety — the numbers that gate release**
- Red flag sensitivity on a curated emergency vignette set. **Target: 100%. A miss is a release blocker.**
- Under-triage rate: proportion of cases assigned a band lower than clinician reference. **Target: under 2%.**
- Over-triage rate. Target under 25%, because over-triage is the correct direction to err and a low number here usually means the system is unsafe.

**Quality**
- Specialist routing accuracy against clinician reference.
- History completeness: proportion of clinically required fields elicited per complaint family.
- Fabrication rate: findings in the handoff packet not traceable to a patient utterance. **Target: zero, enforced structurally rather than measured.**

**Experience**
- Turns to sufficient history. Target median 8–14.
- Turn latency p95 on target hardware.
- ASR word error rate overall, and separately on drug names and anatomical terms, per language.

**Reference data.** Build a vignette set of 300+ cases with clinician-assigned reference bands. Public conversational medical datasets exist — MTS-Dialog, PriMock57, ACI-Bench — and should be assessed for fit; none are Indian or code-switched, so the vignette set has to be constructed. Reference labels need at least one qualified clinician, ideally two with disagreement resolution.

### 4.9 Out of scope for v1

Prescribing. Dose calculation. Anything a pharmacist would sign. Image interpretation. Mental health crisis counselling beyond risk detection and immediate escalation to a helpline. Paediatric under-2 as a primary path — detect and route to human, because the danger-sign profile is different enough to warrant its own build.

---

## 5. Non-functional requirements

**Privacy.** No network egress from the inference path. De-identification before anything is persisted beyond the session. Patient identifiers separated from clinical content at the storage layer. DPDP Act 2023 obligations apply; consent capture is explicit and logged.

**Auditability.** Append-only session log. Prompt version, model version, and rule-set version recorded on every decision. Any output reproducible from the log.

**Interoperability.** FHIR R4 output. ABDM/ABHA alignment where the record is exportable — this is the difference between a project and something that could plug into national infrastructure.

**Availability.** Fully functional offline. Degrades to distance-only facility lookup when the facility index is stale, and states that it has.

**Accessibility.** Voice-first. Works on a low-end Android browser. Large tap targets, high contrast, screen-reader labelled.

---

## 6. Frontend

Two surfaces.

**Patient consultation.** Single-column, one question visible at a time, large type, voice button as the primary control. Nothing else on screen. The design goal is that it does not look like a chat product — it looks like a form that talks.

**Clinician review.** Dense, information-first. Handoff packet, structured history, red flags, differential with evidence, audit trail. Optimised for a doctor scanning in fifteen seconds before walking into the room.

Design direction comes from your screenshots. Until those arrive, no visual decisions get made. Constraints that hold regardless:

Do not build the default generated-app look — no purple-to-blue gradient headers, no identical rounded cards for dissimilar content, no all-caps eyebrow labels above every section, no emoji in the interface, no arrow glyphs appended to button text. Colour carries clinical meaning here and nothing else: urgency bands map to a fixed palette and that palette is not used decoratively anywhere else in the product.

---

## 7. Delivery plan for Module 1

**M1 — Spine.** Schema, FHIR mapping, red flag engine with full unit tests, vignette set v1. No models yet. The safety layer exists and is tested before anything generative is written.

**M2 — Text consultation.** Intake and structuring agents, English only, text only. Handoff packet generation. First eval run.

**M3 — Triage and routing.** Triage agent, safety critic, facility index with capability matching, both frontends.

**M4 — Voice and language.** ASR integration, one Indian language end to end, code-switch handling, ASR eval.

**M5 — Hardening.** Full eval suite, load and latency testing, audit log completeness, deployment packaging, documentation.

Do not start M4 before M3's numbers are published. Language support on top of an unevaluated triage layer produces an impressive demo and an unsafe product.

---

## Appendix A — Module stubs

**Scribe.** Ambient consultation capture; SOAP note; FHIR extraction; span-level groundedness so every clinical statement traces to transcript audio; physician edit loop.

**Rx.** Handwritten prescription OCR; Indian brand-to-molecule resolution across the many-brands-one-molecule problem; interaction and duplicate-therapy checking against the patient's structured record; Jan Aushadhi generic substitution with price delta.

**Labs.** Multi-format Indian diagnostic report parsing; reference range interpretation with clinical context; trend analysis across prior reports; routing to appropriate specialty.

**Forensics.** Structured MLC and wound documentation; injury-mechanism consistency; statutory hurt classification support under BNS; MCCD cause-of-death chain guidance; append-only hash-chained evidence record with verifiable custody chain. The system structures examiner findings and never generates them.

---

## Appendix B — Sources

These are the standards and frameworks the design leans on. **Every clinical threshold, criterion, and statutory section number must be verified against the current published source before it ships.** My knowledge has a cutoff and clinical guidance changes; treat the list below as pointers to check, not as citations to trust.

**Terminology and interoperability**
- HL7 FHIR R4 — https://hl7.org/fhir/R4/
- SNOMED CT — https://www.snomed.org/
- WHO ICD — https://www.who.int/standards/classifications/classification-of-diseases
- ABDM (Ayushman Bharat Digital Mission) — https://abdm.gov.in/

**Triage frameworks**
- Emergency Severity Index — AHRQ has published an ESI implementation handbook; find the current edition
- Manchester Triage System
- WHO IMCI for paediatric danger signs — https://www.who.int/

**Clinical guidance to verify red flag criteria against**
- NICE guidelines — https://www.nice.org.uk/guidance
- WHO clinical guidance
- Indian national programme guidance from MoHFW — https://mohfw.gov.in/

**Regulatory**
- Digital Personal Data Protection Act 2023
- CDSCO medical device classification — confirm current position on clinical decision support software
- BNS 2023 for the forensics module; section numbering changed from IPC in 2024 and must be checked directly

**Evaluation datasets to assess**
- MTS-Dialog, PriMock57, ACI-Bench for clinical dialogue. Confirm licences and current availability.

**Models to evaluate**
- Whisper — OpenAI
- AI4Bharat IndicWhisper and IndicTrans2 — IIT Madras
