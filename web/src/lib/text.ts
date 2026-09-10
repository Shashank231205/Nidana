/* Patient- and clinician-facing wording.
 *
 * Ported verbatim from the vanilla build. These tables are the substance of
 * the patient surface: a specialty a patient cannot name is a referral they
 * cannot act on, and a capability list is what stops someone being sent to a
 * hospital that cannot treat them.
 */

import type { Band } from "./types";

/* Bands as the patient reads them. No condition names, no probabilities. */
export const BAND_TEXT: Record<Band, string> = {
  U1: "Emergency — go now",
  U2: "Urgent — see a doctor today",
  U3: "See a doctor within 24 to 48 hours",
  U4: "See a doctor within a week",
  U5: "You can manage this at home",
};

/* Bands as a clinician reads them. */
export const BAND_TEXT_CLINICAL: Record<Band, string> = {
  U1: "U1 — Immediate",
  U2: "U2 — Urgent, same day",
  U3: "U3 — Semi-urgent, 24 to 48 hours",
  U4: "U4 — Routine, within a week",
  U5: "U5 — Self-care with a safety net",
};

/* Specialty as a patient reads it: the plain name first, the clinical term in
 * brackets. A patient looking for a doctor needs the word on the door. */
export const SPECIALTY_TEXT: Record<string, string> = {
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
export const CAPABILITY_TEXT: Record<string, string> = {
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

export const capabilityText = (key: string): string =>
  CAPABILITY_TEXT[key] ?? key.replace(/_/g, " ");

export const specialtyText = (key: string): string =>
  SPECIALTY_TEXT[key] ?? key.replace(/_/g, " ");
