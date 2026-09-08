/* The Consult API client.
 *
 * Two things this module is responsible for and the screens are not:
 *
 * 1. Turn responses are dispatched on `shape`. There is no status string to
 *    parse and no inference about which fields are populated.
 * 2. Error `detail` from the backend is written to state the remedy, so it is
 *    carried through verbatim rather than replaced with a generic message.
 */

const BASE = window.NIDANA_API_BASE || "";

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    throw new ApiError(
      0,
      "Cannot reach the Nidana server on this machine. Check that it is running.",
    );
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail) && payload.detail.length) {
        // 422 from FastAPI validation: a list of per-field errors.
        detail = payload.detail.map((item) => item.msg).join("; ");
      }
    } catch (cause) {
      // A non-JSON error body leaves the status line as the detail.
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export const createSession = () => request("POST", "/v1/sessions");

export const submitTurn = (sessionId, utterance) =>
  request("POST", `/v1/sessions/${sessionId}/turns`, { utterance });

export const readSession = (sessionId) =>
  request("GET", `/v1/sessions/${sessionId}`);

export const completeSession = (sessionId) =>
  request("POST", `/v1/sessions/${sessionId}/complete`);

export const readAudit = (sessionId) =>
  request("GET", `/v1/sessions/${sessionId}/audit`);

/* The three shapes, named. A screen switches on this and nothing else. */
export const SHAPE = {
  NEXT_QUESTION: "next_question",
  TERMINAL_EMERGENCY: "terminal_emergency",
  COMPLETED_TRIAGE: "completed_triage",
};

/* Bands as the patient reads them. No condition names, no probabilities. */
export const BAND_TEXT = {
  U1: "Emergency — go now",
  U2: "Urgent — see a doctor today",
  U3: "See a doctor within 24 to 48 hours",
  U4: "See a doctor within a week",
  U5: "You can manage this at home",
};

/* Bands as a clinician reads them. */
export const BAND_TEXT_CLINICAL = {
  U1: "U1 — Immediate",
  U2: "U2 — Urgent, same day",
  U3: "U3 — Semi-urgent, 24 to 48 hours",
  U4: "U4 — Routine, within a week",
  U5: "U5 — Self-care with a safety net",
};

/* Specialty as a patient reads it: the plain name first, the clinical term in
 * brackets. A patient looking for a doctor needs the word on the door. */
export const SPECIALTY_TEXT = {
  emergency: "an emergency department",
  general_medicine: "a general physician",
  cardiology: "a heart doctor (cardiologist)",
  neurology: "a nerve and brain doctor (neurologist)",
  gastroenterology: "a stomach and digestion doctor (gastroenterologist)",
  pulmonology: "a lung doctor (pulmonologist)",
  nephrology: "a kidney doctor (nephrologist)",
  endocrinology: "a hormone and diabetes doctor (endocrinologist)",
  rheumatology: "a joint and autoimmune doctor (rheumatologist)",
  haematology: "a blood doctor (haematologist)",
  oncology: "a cancer doctor (oncologist)",
  infectious_disease: "an infection specialist",
  obstetrics_gynaecology: "a women's health doctor (gynaecologist)",
  paediatrics: "a children's doctor (paediatrician)",
  neonatology: "a newborn specialist (neonatologist)",
  geriatrics: "a doctor for older people (geriatrician)",
  surgery: "a surgeon",
  urology: "a urinary system doctor (urologist)",
  orthopaedics: "a bone and joint doctor (orthopaedic surgeon)",
  ophthalmology: "an eye doctor (ophthalmologist)",
  ent: "an ear, nose and throat doctor",
  dentistry: "a dentist",
  dermatology: "a skin doctor (dermatologist)",
  psychiatry: "a mental health doctor (psychiatrist)",
  human_review: "a general physician",
};

/* What a facility must be able to do, in words a patient can act on.
 * Sending someone to the nearest hospital is wrong if it cannot treat them. */
export const CAPABILITY_TEXT = {
  emergency_24x7: "An emergency department open 24 hours",
  cath_lab: "A heart procedure room (cath lab)",
  ct_scanner: "A CT scanner",
  thrombolysis: "Clot-dissolving treatment",
  obstetric_theatre: "An operating theatre for childbirth",
  neonatal_care: "A newborn care unit",
  surgical_theatre: "An operating theatre",
  blood_bank: "A blood bank",
  intensive_care: "An intensive care unit",
  psychiatric_assessment: "A doctor who can assess mental health",
  ophthalmology_on_call: "An eye doctor available now",
  dialysis: "A dialysis unit",
  burn_unit: "A burns unit",
  antivenom: "Snake antivenom in stock",
  rabies_immunoglobulin: "Rabies immunoglobulin in stock",
  ventilator: "A ventilator",
  endoscopy: "An endoscopy unit",
};

export const capabilityText = (key) =>
  CAPABILITY_TEXT[key] || key.replace(/_/g, " ");
