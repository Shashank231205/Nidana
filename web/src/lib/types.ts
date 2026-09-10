/* The wire types, mirroring services/consult/api/app.py.
 *
 * Hand-written rather than generated, and narrow on purpose: `shape` is a
 * union so that a screen switching on it is exhaustive at compile time, and
 * the compiler rejects a fourth shape added to the backend without a matching
 * branch here.
 */

export const SHAPE = {
  NEXT_QUESTION: "next_question",
  TERMINAL_EMERGENCY: "terminal_emergency",
  COMPLETED_TRIAGE: "completed_triage",
} as const;

export type Shape = (typeof SHAPE)[keyof typeof SHAPE];

export type Band = "U1" | "U2" | "U3" | "U4" | "U5";

export interface Emergency {
  readonly capabilities_required?: readonly string[];
  readonly specialty?: string;
}

export interface Triage {
  readonly band?: Band;
  readonly specialty?: string;
  readonly return_criteria?: readonly string[];
}

/** One turn.
 *
 * `disclosures` names every rule in force that runs on a model's reading
 * rather than a clinician's signature. The backend recomputes it per response
 * and its docstring is explicit that a client showing a triage outcome must
 * show these with it: a band produced partly by unreviewed criteria and
 * presented as though it were not is the failure the attestation state exists
 * to prevent. It is non-optional here so a screen cannot forget it.
 */
export interface TurnResponse {
  readonly shape: Shape;
  readonly session_id: string;
  readonly turn_index: number;
  readonly question: string | null;
  readonly emergency: Emergency | null;
  readonly triage: Triage | null;
  readonly disclosures: readonly string[];
}

export interface SessionCreated {
  readonly session_id: string;
  readonly status: string;
  readonly turn_index: number;
}

export interface ConsentResponse {
  readonly session_id: string;
  readonly granted: boolean;
  readonly purpose: string;
  readonly consent_text_version: string;
}

/* ── Scribe ─────────────────────────────────────────────── */

export interface EncounterResponse {
  readonly encounter_id: string;
  readonly status: string;
  readonly statement_count: number;
  readonly omission_count: number;
  readonly blocking_omission_count: number;
  readonly fabrication_count: number;
}

/** The note, plus what the groundedness gate dropped.
 *
 * `fabrication_count` is reported rather than hidden: a non-zero value means
 * the model claimed something the transcript did not support and the gate
 * caught it, which a clinician reviewing the note should know.
 */
export interface NoteResponse {
  readonly encounter_id: string;
  readonly note: unknown;
  readonly fabrication_count: number;
  readonly dropped: readonly string[];
}

/* ── Rx ─────────────────────────────────────────────────── */

export interface FindingResponse {
  readonly kind: string;
  readonly severity: string;
  readonly molecules: readonly string[];
  readonly written_as: readonly string[];
  readonly message: string;
  readonly source: string;
  readonly blocks_dispensing: boolean;
}

/** What every check that could run concluded.
 *
 * The two availability flags and `molecules_not_interaction_checked` carry the
 * distinction the service exists to preserve: an empty findings list reads as
 * "no interactions found", and what may be true is "interactions were not
 * checked". A screen must show them together.
 */
export interface CheckResponse {
  readonly check_id: string;
  readonly findings: readonly FindingResponse[];
  readonly blocks_dispensing: boolean;
  readonly brand_resolution_available: boolean;
  readonly interaction_checking_available: boolean;
  readonly molecules_not_interaction_checked: readonly string[];
}

export interface ReadResponse {
  readonly medications: unknown;
  readonly fabrication_count: number;
  readonly unresolved_count: number;
  readonly dropped: readonly string[];
}

/* ── Labs ───────────────────────────────────────────────── */

export interface CriticalFindingResponse {
  readonly analyte: string;
  readonly value: number;
  readonly unit: string;
  readonly flag: string;
  readonly threshold: number;
  readonly source: string;
  readonly unverified: boolean;
  readonly message: string;
}

/** `unit_mismatches` names analytes whose threshold could not be applied. An
 * empty findings list means something different when this list is not empty. */
export interface InterpretResponse {
  readonly report_id: string;
  readonly critical_findings: readonly CriticalFindingResponse[];
  readonly unit_mismatches: readonly string[];
  readonly has_critical_value: boolean;
}

export interface ExtractResponse {
  readonly report: unknown;
  readonly fabrication_count: number;
  readonly dropped: readonly string[];
  readonly critical_findings: readonly CriticalFindingResponse[];
  readonly unit_mismatches: readonly string[];
  readonly has_critical_value: boolean;
}

export interface ThresholdsResponse {
  readonly count: number;
  readonly unverified: readonly string[];
}

/* ── Forensics ──────────────────────────────────────────── */

export interface StatuteMatch {
  readonly ipc: string;
  readonly bns: string | null;
  readonly title: string;
  readonly changed: boolean;
  readonly repealed: boolean;
  readonly needs_legal_check: boolean;
  readonly note: string | null;
}

/** `legally_reviewed` is false on every response this build produces. The
 * table translates section numbers; it never classifies an injury. */
export interface StatuteResponse {
  readonly query: string;
  readonly numbering: string;
  readonly matches: readonly StatuteMatch[];
  readonly legally_reviewed: boolean;
}
