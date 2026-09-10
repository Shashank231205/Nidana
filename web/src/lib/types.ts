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
