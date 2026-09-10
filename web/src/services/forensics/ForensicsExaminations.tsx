import { useState } from "react";
import { createExamination, readChain, recordAccess } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";

/* Open an examination, and read its chain of custody.
 *
 * Reading is itself an event. `POST /access` requires who is reading and why,
 * because an unattributed access in a custody log is the same as no log — so
 * this screen asks for a reason before it will show anything.
 *
 * `verified` comes from the server, which recomputes the chain rather than
 * trusting it. A false there means the log was altered, and it is shown at the
 * top rather than as a footnote.
 */

interface ChainEntry {
  readonly sequence: number;
  readonly event_type: string;
  readonly actor: string;
  readonly occurred_at: string;
  readonly payload: Record<string, unknown>;
}

interface ChainResponse {
  readonly examination_id: string;
  readonly verified: boolean;
  readonly entries: readonly ChainEntry[];
}

const newId = (): string =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : "00000000-0000-4000-8000-000000000000";

export function ForensicsExaminations({
  actor,
}: {
  readonly actor: string;
}): JSX.Element {
  const [examinationId, setExaminationId] = useState("");
  const [reason, setReason] = useState("");
  const { state, run } = useAsync<ChainResponse>();

  const start = (): void => {
    void run(async () => {
      const id = newId();
      await createExamination(
        {
          examination_id: id,
          examiner_id: actor,
          examined_at: new Date().toISOString(),
        },
        actor,
      );
      setExaminationId(id);
      return (await readChain(id, actor)) as ChainResponse;
    });
  };

  const open = (): void => {
    const id = examinationId.trim();
    const why = reason.trim();
    if (id.length === 0 || why.length === 0) return;
    void run(async () => {
      await recordAccess(id, actor, why);
      return (await readChain(id, actor)) as ChainResponse;
    });
  };

  return (
    <main className="page">
      <h1 className="page-title">Examinations</h1>
      <p className="page-intro">
        Open a medico-legal examination, or read the chain of custody on an
        existing one. Every read is recorded against your name and your reason.
      </p>

      <div className="lookup-row">
        <button className="btn btn-primary" onClick={start} disabled={state.busy}>
          Open an examination
        </button>
      </div>

      <form
        className="lookup-form form-gap"
        onSubmit={(event) => {
          event.preventDefault();
          open();
        }}
      >
        <label className="label" htmlFor="exam-id">
          Examination identifier
        </label>
        <input
          className="field field-wide"
          id="exam-id"
          value={examinationId}
          onChange={(event) => setExaminationId(event.target.value)}
        />

        <label className="label form-gap" htmlFor="exam-reason">
          Why you are reading it
        </label>
        <input
          className="field field-wide"
          id="exam-reason"
          value={reason}
          placeholder="Preparing court submission"
          onChange={(event) => setReason(event.target.value)}
        />

        <div className="form-gap">
          <button
            className="btn btn-secondary"
            type="submit"
            disabled={
              state.busy ||
              examinationId.trim().length === 0 ||
              reason.trim().length === 0
            }
          >
            Record access and read
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Recording your access and reading the chain" />}
      {state.error !== null && <Failure detail={state.error} onRetry={open} />}

      {state.data !== null && (
        <section className="result">
          <p className="label">Examination</p>
          <p className="data">{state.data.examination_id}</p>

          {state.data.verified ? (
            <p className="body form-gap">
              The chain verifies. Every entry links to the one before it and
              nothing has been altered since it was written.
            </p>
          ) : (
            <p className="body audit-broken form-gap" role="alert">
              The chain does not verify. An entry has been altered or removed,
              and this record cannot be relied on as evidence until that is
              explained.
            </p>
          )}

          <ol className="plain audit-list">
            {state.data.entries.map((entry) => (
              <li className="audit-entry" key={entry.sequence}>
                <p className="audit-head">
                  <span className="audit-seq">{entry.sequence}</span>
                  <span className="audit-event">
                    {entry.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="meta audit-when">{entry.occurred_at}</span>
                </p>
                <p className="meta">by {entry.actor}</p>
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
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
