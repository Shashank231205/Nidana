import { useState } from "react";
import { readSession } from "../../../lib/client";
import { useAsync, Busy, Failure } from "../../../components/Async";
import { hrefFor } from "../../../shell/useRoute";

/* Open one triage session.
 *
 * There is no list endpoint. Sessions are held per instance and the API
 * exposes them by identifier only, so this screen asks for one rather than
 * pretending to browse. A list that quietly showed only the sessions this
 * process happens to hold would be worse than an honest lookup.
 */

interface SessionSummary {
  readonly session_id: string;
  readonly status: string;
  readonly turn_index: number;
  readonly complaint_family: string | null;
  readonly finding_count: number;
}

export function ConsultSessions(): JSX.Element {
  const [sessionId, setSessionId] = useState("");
  const { state, run } = useAsync<SessionSummary>();

  const load = (): void => {
    const trimmed = sessionId.trim();
    if (trimmed.length > 0) void run(() => readSession(trimmed) as Promise<SessionSummary>);
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Sessions</h1>
      <p className="page-intro">
        Open a triage session by its identifier. Start a new patient triage from
        the <a href="#/triage">triage screen</a>, which runs without this
        header.
      </p>

      <form
        className="lookup-form"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <div className="lookup-row">
          <label className="visually-hidden" htmlFor="lookup-session">
            Session identifier
          </label>
          <input
            className="field field-wide"
            id="lookup-session"
            value={sessionId}
            placeholder="Session identifier"
            onChange={(event) => setSessionId(event.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={state.busy}>
            Open
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Reading the session" />}
      {state.error !== null && <Failure detail={state.error} onRetry={load} />}

      {state.data !== null && (
        <section className="result">
          <dl className="summary">
            <div className="summary-field">
              <dt className="label">Status</dt>
              <dd className="data">{state.data.status}</dd>
            </div>
            <div className="summary-field">
              <dt className="label">Turns taken</dt>
              <dd className="data">{state.data.turn_index}</dd>
            </div>
            <div className="summary-field">
              <dt className="label">Complaint</dt>
              <dd className="data">
                {state.data.complaint_family ?? "not yet established"}
              </dd>
            </div>
            <div className="summary-field">
              <dt className="label">Findings recorded</dt>
              <dd className="data">{state.data.finding_count}</dd>
            </div>
          </dl>

          <p className="form-gap">
            <a className="link" href={hrefFor("consult", "audit")}>
              Open the audit trail
            </a>
          </p>
        </section>
      )}
    </main>
  );
}
