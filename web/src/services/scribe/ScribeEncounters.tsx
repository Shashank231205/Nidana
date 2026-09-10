import { useState } from "react";
import { createEncounter, readEncounter } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { hrefFor } from "../../shell/useRoute";
import type { EncounterResponse } from "../../lib/types";

/* Start an encounter, or open one.
 *
 * The four counts are shown together because they answer different questions
 * and a clinician needs all four before signing: how much was recorded, what
 * the note left out, which of those omissions block signing, and what the
 * groundedness gate caught the model inventing.
 */

export function ScribeEncounters(): JSX.Element {
  const [encounterId, setEncounterId] = useState("");
  const { state, run } = useAsync<EncounterResponse>();

  const open = (): void => {
    const trimmed = encounterId.trim();
    if (trimmed.length > 0) void run(() => readEncounter(trimmed));
  };

  const start = (): void => {
    void run(async () => {
      const created = await createEncounter();
      setEncounterId(created.encounter_id);
      return created;
    });
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Encounters</h1>
      <p className="page-intro">
        Start a new encounter, or open an existing one to see what its draft
        note recorded and what it left out.
      </p>

      <div className="lookup-row">
        <button className="btn btn-primary" onClick={start} disabled={state.busy}>
          Start an encounter
        </button>
      </div>

      <form
        className="lookup-form form-gap"
        onSubmit={(event) => {
          event.preventDefault();
          open();
        }}
      >
        <div className="lookup-row">
          <label className="visually-hidden" htmlFor="encounter-id">
            Encounter identifier
          </label>
          <input
            className="field field-wide"
            id="encounter-id"
            value={encounterId}
            placeholder="Encounter identifier"
            onChange={(event) => setEncounterId(event.target.value)}
          />
          <button className="btn btn-secondary" type="submit" disabled={state.busy}>
            Open
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Reading the encounter" />}
      {state.error !== null && <Failure detail={state.error} onRetry={open} />}

      {state.data !== null && (
        <section className="result">
          <p className="label">Encounter</p>
          <p className="data">{state.data.encounter_id}</p>

          <dl className="summary form-gap">
            <div className="summary-field">
              <dt className="label">Status</dt>
              <dd className="data">{state.data.status}</dd>
            </div>
            <div className="summary-field">
              <dt className="label">Statements recorded</dt>
              <dd className="data">{state.data.statement_count}</dd>
            </div>
            <div className="summary-field">
              <dt className="label">Left out of the note</dt>
              <dd className="data">{state.data.omission_count}</dd>
            </div>
            <div className="summary-field">
              <dt className="label">Blocking signature</dt>
              <dd className="data">{state.data.blocking_omission_count}</dd>
            </div>
          </dl>

          {state.data.fabrication_count > 0 && (
            <section className="coverage">
              <p className="label">
                {state.data.fabrication_count} claim
                {state.data.fabrication_count === 1 ? "" : "s"} dropped
              </p>
              <p className="body">
                The model claimed something the transcript did not support and
                the gate caught it. Nothing was recorded for those claims, so
                read the note knowing they are absent.
              </p>
            </section>
          )}

          <p className="form-gap">
            <a className="link" href={hrefFor("scribe", "draft")}>
              Draft the note
            </a>
          </p>
        </section>
      )}
    </main>
  );
}
