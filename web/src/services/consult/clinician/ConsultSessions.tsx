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
 *
 * Identifiers a clinician has opened this shift are kept for the tab, because
 * a screen that demands a UUID and offers no way to have one is a dead end.
 */

interface SessionSummary {
  readonly session_id: string;
  readonly status: string;
  readonly turn_index: number;
  readonly complaint_family: string | null;
  readonly finding_count: number;
}

const RECENT_KEY = "nidana.recentSessions";

const readRecent = (): readonly string[] => {
  try {
    const raw = window.sessionStorage.getItem(RECENT_KEY);
    return raw === null ? [] : (JSON.parse(raw) as string[]);
  } catch {
    return [];
  }
};

const remember = (id: string): readonly string[] => {
  const next = [id, ...readRecent().filter((seen) => seen !== id)].slice(0, 8);
  try {
    window.sessionStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // Held for this render only.
  }
  return next;
};

export function ConsultSessions(): JSX.Element {
  const [sessionId, setSessionId] = useState("");
  const [recent, setRecent] = useState<readonly string[]>(readRecent);
  const { state, run } = useAsync<SessionSummary>();

  const load = (id: string): void => {
    const trimmed = id.trim();
    if (trimmed.length === 0) return;
    setSessionId(trimmed);
    void run(async () => {
      const summary = (await readSession(trimmed)) as SessionSummary;
      setRecent(remember(trimmed));
      return summary;
    });
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Sessions</h1>
      <p className="page-intro">
        Open a triage session by its identifier. A patient starts a new one on
        the <a href="#/triage">triage screen</a>, which runs without this
        header.
      </p>

      <form
        className="lookup-form"
        onSubmit={(event) => {
          event.preventDefault();
          load(sessionId);
        }}
      >
        <label className="label" htmlFor="lookup-session">
          Session identifier
        </label>
        <div className="lookup-row">
          <input
            className="field field-wide"
            id="lookup-session"
            value={sessionId}
            placeholder="0b467023-8c0c-4ed4-b91e-b20c7cfb84dd"
            onChange={(event) => setSessionId(event.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={state.busy}>
            Open
          </button>
        </div>
      </form>

      {recent.length > 0 && state.data === null && (
        <section className="recent">
          <p className="label">Opened this shift</p>
          <ul className="plain recent-list">
            {recent.map((id) => (
              <li key={id}>
                <button className="link recent-item" onClick={() => load(id)}>
                  {id}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {state.busy && <Busy doing="Reading the session" />}
      {state.error !== null && (
        <Failure detail={state.error} onRetry={() => load(sessionId)} />
      )}

      {state.data !== null && (
        <section className="result">
          <p className="label">Session</p>
          <p className="data mono-id">{state.data.session_id}</p>

          <dl className="summary form-gap">
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
            <a href={hrefFor("consult", "audit")}>
              Open the audit trail for this session
            </a>
          </p>
        </section>
      )}
    </main>
  );
}
