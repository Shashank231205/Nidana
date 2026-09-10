/* The Consult API client.
 *
 * Two things this module is responsible for and the screens are not:
 *
 * 1. Turn responses are dispatched on `shape`. There is no status string to
 *    parse and no inference about which fields are populated.
 * 2. Error `detail` from the backend is written to state the remedy, so it is
 *    carried through verbatim rather than replaced with a generic message.
 */

import type {
  ConsentResponse,
  SessionCreated,
  TurnResponse,
} from "./types";

declare global {
  interface Window {
    NIDANA_API_BASE?: string;
  }
}

const base = (): string => window.NIDANA_API_BASE ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface ValidationItem {
  readonly msg?: unknown;
}

function detailFrom(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null) return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // 422 from FastAPI validation: a list of per-field errors.
    const messages = (detail as ValidationItem[])
      .map((item) => (typeof item.msg === "string" ? item.msg : null))
      .filter((msg): msg is string => msg !== null);
    if (messages.length > 0) return messages.join("; ");
  }
  return fallback;
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit =
    body === undefined
      ? { method }
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        };

  let response: Response;
  try {
    response = await fetch(base() + path, init);
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the Nidana server on this machine. Check that it is running.",
    );
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // A non-JSON error body leaves the status line as the detail.
    }
    throw new ApiError(
      response.status,
      detailFrom(payload, `${response.status} ${response.statusText}`),
    );
  }

  return (await response.json()) as T;
}

export const createSession = (): Promise<SessionCreated> =>
  request<SessionCreated>("POST", "/v1/sessions");

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
  request<ConsentResponse>("POST", `/v1/sessions/${sessionId}/consent`, {
    granted,
    purpose,
  });

export const submitTurn = (
  sessionId: string,
  utterance: string,
): Promise<TurnResponse> =>
  request<TurnResponse>("POST", `/v1/sessions/${sessionId}/turns`, { utterance });

export const completeSession = (sessionId: string): Promise<TurnResponse> =>
  request<TurnResponse>("POST", `/v1/sessions/${sessionId}/complete`);
