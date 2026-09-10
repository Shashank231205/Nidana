/* The five services' endpoints, named.
 *
 * Every call goes through `request`, which carries the backend's error detail
 * verbatim. Turn responses are dispatched on `shape`: there is no status
 * string to parse and no inference about which fields are populated.
 */

import { request } from "./http";
import type {
  CheckResponse,
  ConsentResponse,
  EncounterResponse,
  ExtractResponse,
  InterpretResponse,
  NoteResponse,
  ReadResponse,
  SessionCreated,
  StatuteResponse,
  ThresholdsResponse,
  TurnResponse,
} from "./types";

export { ApiError } from "./http";

/* ── Consult ────────────────────────────────────────────── */

export const createSession = (): Promise<SessionCreated> =>
  request("consult", "POST", "/v1/sessions");

/** Record the patient's decision before any turn is taken.
 *
 * Not optional. `POST /turns` returns 403 on a session with no recorded
 * consent, so a client that collects the checkbox and does not post it cannot
 * complete a single consultation. Purpose is bound under the DPDP Act, so it
 * travels with the decision rather than being implied by the endpoint.
 */
export const recordConsent = (
  sessionId: string,
  granted: boolean,
  purpose = "triage",
): Promise<ConsentResponse> =>
  request("consult", "POST", `/v1/sessions/${sessionId}/consent`, { granted, purpose });

export const submitTurn = (sessionId: string, utterance: string): Promise<TurnResponse> =>
  request("consult", "POST", `/v1/sessions/${sessionId}/turns`, { utterance });

export const completeSession = (sessionId: string): Promise<TurnResponse> =>
  request("consult", "POST", `/v1/sessions/${sessionId}/complete`);

export const readSession = (sessionId: string): Promise<unknown> =>
  request("consult", "GET", `/v1/sessions/${sessionId}`);

export const readAudit = (sessionId: string): Promise<unknown> =>
  request("consult", "GET", `/v1/sessions/${sessionId}/audit`);

/* ── Scribe ─────────────────────────────────────────────── */

export const createEncounter = (): Promise<EncounterResponse> =>
  request("scribe", "POST", "/v1/encounters");

export const draftNote = (
  encounterId: string,
  transcript: unknown,
  record: unknown,
): Promise<NoteResponse> =>
  request("scribe", "POST", `/v1/encounters/${encounterId}/draft`, { transcript, record });

export const signNote = (encounterId: string, signedBy: string): Promise<unknown> =>
  request("scribe", "POST", `/v1/encounters/${encounterId}/sign`, { signed_by: signedBy });

export const readEncounter = (encounterId: string): Promise<EncounterResponse> =>
  request("scribe", "GET", `/v1/encounters/${encounterId}`);

/* ── Rx ─────────────────────────────────────────────────── */

export const checkPrescription = (
  medications: unknown,
  record: unknown,
): Promise<CheckResponse> =>
  request("rx", "POST", "/v1/checks", { medications, record });

export const readPrescription = (
  ocrText: string,
  sourceId: string,
): Promise<ReadResponse> =>
  request("rx", "POST", "/v1/prescriptions/read", {
    ocr_text: ocrText,
    source_id: sourceId,
  });

/* ── Labs ───────────────────────────────────────────────── */

/** The endpoint takes the report itself, not a wrapper around it. */
export const interpretReport = (report: unknown): Promise<InterpretResponse> =>
  request("labs", "POST", "/v1/reports", report);

export const extractReport = (
  reportText: string,
  sourceId: string,
): Promise<ExtractResponse> =>
  request("labs", "POST", "/v1/reports/extract", {
    report_text: reportText,
    source_id: sourceId,
  });

export const readThresholds = (): Promise<ThresholdsResponse> =>
  request("labs", "GET", "/v1/thresholds");

/* ── Forensics ──────────────────────────────────────────── */

export const lookUpStatute = (
  numbering: "ipc" | "bns",
  section: string,
): Promise<StatuteResponse> =>
  request("forensics", "GET", `/v1/statutes/${numbering}/${encodeURIComponent(section)}`);

export const createExamination = (report: unknown, actor: string): Promise<unknown> =>
  request("forensics", "POST", "/v1/examinations", { report, actor });

export const recordAccess = (
  examinationId: string,
  actor: string,
  reason: string,
): Promise<unknown> =>
  request("forensics", "POST", `/v1/examinations/${examinationId}/access`, {
    actor,
    reason,
  });

export const readChain = (examinationId: string, actor: string): Promise<unknown> =>
  request("forensics", "POST", `/v1/examinations/${examinationId}/chain`, { actor });
