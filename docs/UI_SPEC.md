# Nidana — UI Specification

A brief for building the two frontends. Everything below the API section is
constraint rather than suggestion: the backend enforces most of it, and a UI
that ignores it will fail validation rather than render badly.

Read `docs/PRD.md` §6 and `docs/ENGINEERING_RULES.md` §8 for the source of
these rules. This file is the practical version.

---

## 1. What this product is

Nidana is an on-premise clinical intelligence platform for Indian healthcare.
Five services write to one shared patient record. The record is the product;
the services are surfaces on it.

**Nidana triages, documents, and routes. It does not diagnose.** That is a
product decision before it is a compliance one, and it constrains the UI
directly — see §4.

The five services:

- **S1 Consult** — conversational triage. Patient answers questions, gets an
  urgency band, a specialty, and instructions. *Backend runs end to end.*
- **S2 Scribe** — ambient consultation notes for a clinician.
- **S3 Rx** — prescription reading and safety checks.
- **S4 Labs** — lab report parsing and interpretation.
- **S5 Forensics** — medico-legal documentation, tamper-evident.

**Build the Consult surfaces first.** It is the only service whose API exists.

---

## 2. Two surfaces, two entirely different designs

### Patient surface

A person who is unwell, possibly frightened, possibly on a low-end Android
phone on a poor connection, possibly more comfortable speaking than reading.

- **Single column. One question visible at a time. Nothing else on screen.**
- Large type. Voice button as the primary control, not a secondary one.
- **The design goal: it must not look like a chat product.** It looks like a
  form that talks.
- Works at 320px width. Works without a keyboard.
- Reading level around class 6 for anything the patient reads.

### Clinician surface

A doctor with fifteen seconds before walking into a room.

- Dense, information-first, scannable.
- Red flags and urgency band at the top, unmissable.
- Every clinical line traceable to what the patient actually said — hovering
  or expanding a finding shows the verbatim quote.
- Optimised for scanning, not for beauty.

---

## 3. Do not build the default generated-app look

These are explicit prohibitions, not preferences:

- No gradient hero sections
- No identical rounded cards for dissimilar content
- No all-caps eyebrow labels above every section
- No emoji anywhere in the interface
- No arrow glyphs appended to button text ("Continue →")
- No fade-and-slide-up animation on every section
- No soft grey drop shadow under everything

The product is used by people who are unwell and by clinicians under time
pressure. Decoration costs both of them.

---

## 4. Colour carries clinical meaning only

Urgency bands own a fixed palette. **That palette appears nowhere decorative.**
If a button is red, a patient reads it as an emergency.

| Band | Meaning | Patient sees |
|---|---|---|
| U1 | Immediate threat to life or limb | Go to an emergency facility now |
| U2 | Urgent, hours matter | Same day |
| U3 | Semi-urgent | Within 24–48 hours |
| U4 | Routine | Within a week |
| U5 | Self-care with a safety net | Manage at home |

Pick the five colours yourself, but: they must be distinguishable by someone
with colour vision deficiency, and urgency must also be conveyed by text and
position, never by colour alone.

Nothing else in the product uses those five colours.

---

## 5. The API

FastAPI, default `http://localhost:8000`. Interactive docs at `/docs`.

### Create a session

```
POST /v1/sessions
→ 201
{
  "session_id": "uuid",
  "status": "active",
  "turn_index": 0,
  "complaint_family": null,
  "finding_count": 0
}
```

### Submit what the patient said

```
POST /v1/sessions/{session_id}/turns
{ "utterance": "mujhe do din se chest pain hai" }
```

**The response is one of three shapes. Render on `shape`, never on a status
string you have to parse.**

**Shape 1 — next question.** Show the question. Show nothing else.

```json
{
  "shape": "next_question",
  "session_id": "uuid",
  "turn_index": 3,
  "question": "Does the pain go anywhere else?",
  "emergency": null,
  "triage": null
}
```

**Shape 2 — terminal emergency.** The session is over. A deterministic rule
fired. Show the emergency instruction and stop asking questions — the API will
reject further turns with 409.

```json
{
  "shape": "terminal_emergency",
  "session_id": "uuid",
  "turn_index": 4,
  "question": null,
  "emergency": {
    "rule_ids": ["RF_ACS_001"],
    "terminating_rule_ids": ["RF_ACS_001"],
    "escalating_rule_ids": [],
    "required_capabilities": ["cath_lab", "emergency_24x7"],
    "matched_atoms": ["chest_pain_present", "pain_radiates_to_jaw_or_left_arm"],
    "unverified_rule_ids": ["RF_ACS_001"]
  },
  "triage": null
}
```

**Shape 3 — completed triage.** The history is sufficient. Show the outcome.

```json
{
  "shape": "completed_triage",
  "session_id": "uuid",
  "turn_index": 11,
  "question": null,
  "emergency": null,
  "triage": {
    "band": "U2",
    "specialty": "cardiology",
    "rationale": "Clinician-facing reasoning. Never shown to a patient.",
    "escalating_factors": ["diabetes"],
    "uncertainty": "Not asked whether the pattern changed this week.",
    "required_capabilities": [],
    "return_criteria": [
      "If the tightness comes on while you are sitting still, go to a hospital emergency department immediately.",
      "If it lasts more than fifteen minutes after you rest, go to a hospital emergency department immediately.",
      "If you start sweating heavily with it, go to a hospital the same day."
    ],
    "differential": [
      {
        "condition": "Stable angina",
        "supporting": ["exertional onset", "relieved by rest"],
        "opposing": ["no radiation reported"]
      }
    ],
    "history_gaps": ["prior_similar_episode"],
    "red_flags": { "rule_ids": [] },
    "critic_raised_from": null
  }
}
```

### Other endpoints

```
GET  /health                              instance readiness
GET  /v1/sessions/{id}                    current session state
POST /v1/sessions/{id}/complete           force triage on what exists so far
GET  /v1/sessions/{id}/audit              the full decision trail
```

### Errors

- `404` — unknown session. The `detail` field names the fix; show it.
- `409` — session already ended. Do not retry; render the outcome instead.
- `422` — empty or malformed utterance.
- `503` — the server started but cannot triage. Show a real message, not a
  spinner.

Every error `detail` is written to state the remedy. Show it rather than
replacing it with a generic message.

---

## 6. Rules the UI must not break

**Never show `rationale` or `differential` to a patient.** Both are
clinician-facing and contain condition names. The backend filters patient text;
these two fields are deliberately excluded from that filter because a clinician
needs them.

**Never show a condition name to a patient**, anywhere, in any language.
`return_criteria` are already filtered and safe. Nothing you write yourself
should name a condition.

**`return_criteria` is the most important text this product produces.** Three
to five items, always present below U1. Give them the most visual weight on the
patient outcome screen — more than the band, more than the specialty. They are
what makes a non-diagnostic system safe.

**A terminal emergency ends the conversation.** No "are you sure", no
"continue anyway". Show the instruction and the facility requirement.

**`unverified_rule_ids` is not empty in the current build.** Every clinical
rule is awaiting clinician sign-off. In development the UI may show a discreet
notice; in production the server refuses to start while any rule is unverified,
so this list will be empty there.

---

## 7. Loading states name the operation

Not a spinner. Say what is happening:

- "Checking for anything urgent" — while the red flag engine runs
- "Checking nearby hospitals" — while facilities resolve
- "Listening" — while recording
- "Writing that down" — while structuring

A patient waiting on a slow laptop needs to know the system is doing something
specific.

---

## 8. Voice is the primary path

Voice is faster for elderly and low-literacy users and is how the target user
actually talks. Transcription runs locally.

- The voice button is the largest control on the patient screen.
- Text entry exists and is fully functional, but it is the secondary path.
- Show what was transcribed and let the patient correct it before it is sent.
- Input is code-switched: Hindi, Kannada, Marathi, Bengali, Tamil mixed with
  English, in native script or Roman transliteration. Do not validate against
  an English-only pattern. Do not "correct" spelling.

**The audio endpoint is not built yet.** Build the voice UI against the text
endpoint and leave the recording integration behind an interface.

---

## 9. Accessibility, unannounced

Not a feature to advertise. A floor to meet:

- Visible keyboard focus on every interactive element
- Contrast ratios met
- Screen-reader labels on every control
- `prefers-reduced-motion` respected
- Works at 320px
- Works on a low-end Android browser

---

## 10. Screens to build

### Patient — Consult

1. **Start** — one control to begin. Consent capture (DPDP Act requires it
   logged; the backend endpoint is not built, so put it behind an interface).
2. **Question** — one question, voice button, text fallback. Nothing else.
3. **Emergency** — terminal. What to do, where to go, what capability the
   facility needs. No dismissal, no back button.
4. **Outcome** — band, specialty, when to go, and the return criteria with the
   most weight on the screen.

### Clinician — Consult

1. **Handoff packet** — band and red flags at the top. Structured history where
   each finding expands to show the patient's verbatim words. Differential with
   supporting and opposing evidence. History gaps stated plainly.
2. **Audit trail** — the decision sequence from `GET /audit`. Hash-chained;
   show the sequence and let it be exported.

---

## 11. Stack

Not fixed. Constraints that are:

- Runs offline. No CDN dependency at runtime, no external font fetch, no
  analytics call. The whole product is on-premise and the inference path has no
  network egress.
- Served from the same origin as the API, or CORS configured deliberately.
- Design tokens defined once in one file and used everywhere. No component
  library defaults on display.

React, Svelte, or plain HTML with a small bundle are all acceptable. Prefer the
one that produces the smallest thing that loads on a poor connection.

---

## 12. What to send back

Screenshots of every screen, at 320px and at desktop width. Both surfaces. The
emergency screen and the outcome screen matter most — they are where the
clinical safety of the interface actually lives.

---

## 13. Repository

`https://github.com/Shashank231205/Nidana`

To run the backend:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
cp .env.example .env
docker compose -f infra/compose.yaml up
```

No API keys. Everything runs locally.

Relevant files:

- `services/consult/api/app.py` — the endpoints
- `spine/schemas/triage.py` — `Band`, `Specialty`, `Capability`, `TriageResult`
- `services/consult/session.py` — `TurnShape`
- `services/consult/clinical/output_filter.py` — what may not reach a patient
- `docs/ARCHITECTURE.md` — how the repository is laid out
