import { useState } from "react";
import { readAudit } from "../../../lib/client";
import { useAsync, Busy, Failure } from "../../../components/Async";

/* The decision trail for one session.
 *
 * Every decision in a session must be reconstructable from this log alone, so
 * the chain is shown in full rather than summarised. Entries are append-only
 * and hash-linked: a correction is a new entry naming the one it corrects, so
 * a gap in the sequence or a broken link is visible rather than silent.
 */

interface AuditEntry {
  readonly sequence: number;
  readonly event_type: string;
  readonly actor: string;
  readonly occurred_at: string;
  readonly payload: Record<string, unknown>;
  readonly corrects_sequence: number | null;
  readonly previous_hash: string;
  readonly entry_hash: string;
}

interface AuditResponse {
  readonly session_id: string;
  readonly entries: readonly AuditEntry[];
}

const ZERO_HASH = "0".repeat(64);

export function ConsultAudit(): JSX.Element {
  const [sessionId, setSessionId] = useState("");
  const { state, run } = useAsync<AuditResponse>();

  const load = (): void => {
    const trimmed = sessionId.trim();
    if (trimmed.length > 0) void run(() => readAudit(trimmed) as Promise<AuditResponse>);
  };

  return (
    <main className="page">
      <h1 className="page-title">Audit trail</h1>
      <p className="page-intro">
        Every decision in a session, in the order it happened. Append-only and
        hash-linked, so a missing or altered entry shows.
      </p>

      <form
        className="lookup-form"
        onSubmit={(event) => {
          event.preventDefault();
          load();
        }}
      >
        <div className="lookup-row">
          <label className="visually-hidden" htmlFor="session-id">
            Session identifier
          </label>
          <input
            className="field field-wide"
            id="session-id"
            value={sessionId}
            placeholder="Session identifier"
            onChange={(event) => setSessionId(event.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={state.busy}>
            Open
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Reading the decision trail" />}
      {state.error !== null && <Failure detail={state.error} onRetry={load} />}

      {state.data !== null && (
        <section className="result">
          <p className="body secondary">
            {state.data.entries.length} entr
            {state.data.entries.length === 1 ? "y" : "ies"}
          </p>

          <ol className="plain audit-list">
            {state.data.entries.map((entry, index) => (
              <AuditRow
                key={entry.sequence}
                entry={entry}
                previous={state.data?.entries[index - 1] ?? null}
              />
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}

function AuditRow({
  entry,
  previous,
}: {
  readonly entry: AuditEntry;
  readonly previous: AuditEntry | null;
}): JSX.Element {
  /* The link is checked here rather than trusted. The first entry links to
   * zero; every other must name the hash of the one before it. A mismatch
   * means the log was altered or an entry is missing, and that must be visible
   * to whoever is reading the trail, not only to a verifier. */
  const expected = previous === null ? ZERO_HASH : previous.entry_hash;
  const linked = entry.previous_hash === expected;

  return (
    <li className="audit-entry">
      <p className="audit-head">
        <span className="audit-seq">{entry.sequence}</span>
        <span className="audit-event">{entry.event_type.replace(/_/g, " ")}</span>
        <span className="meta audit-when">{entry.occurred_at}</span>
      </p>
      <p className="meta">by {entry.actor}</p>

      {entry.corrects_sequence !== null && (
        <p className="body">Corrects entry {entry.corrects_sequence}.</p>
      )}

      {!linked && (
        <p className="body audit-broken" role="alert">
          This entry does not link to the one before it. The trail has been
          altered or an entry is missing.
        </p>
      )}

      {Object.keys(entry.payload).length > 0 && (
        <dl className="audit-payload">
          {Object.entries(entry.payload).map(([key, value]) => (
            <div className="audit-field" key={key}>
              <dt className="meta">{key.replace(/_/g, " ")}</dt>
              <dd className="data">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}
