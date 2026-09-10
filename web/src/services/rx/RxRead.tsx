import { useState } from "react";
import { readPrescription } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { Coverage } from "../../components/Coverage";
import type { ReadResponse } from "../../lib/types";

/* Read medication lines out of prescription text.
 *
 * `unresolved_count` and `fabrication_count` are separate numbers and are
 * shown separately. A line the resolver could not match is the resolver
 * working as designed and needs a pharmacist to confirm it; a line the model
 * invented is a different failure entirely. Collapsing them into one "issues"
 * count would hide which of the two happened.
 */

export function RxRead(): JSX.Element {
  const [text, setText] = useState("");
  const [sourceId, setSourceId] = useState("");
  const { state, run } = useAsync<ReadResponse>();

  const ready = text.trim().length > 0 && sourceId.trim().length > 0;
  const submit = (): void => {
    if (ready) void run(() => readPrescription(text.trim(), sourceId.trim()));
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Read from text</h1>
      <p className="page-intro">
        Paste the text of a prescription. Every line read is checked against the
        source, and anything unsupported is dropped rather than guessed.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="label" htmlFor="rx-source">
          Where this came from
        </label>
        <input
          className="field"
          id="rx-source"
          value={sourceId}
          placeholder="Prescription reference or file name"
          onChange={(event) => setSourceId(event.target.value)}
        />

        <label className="label form-gap" htmlFor="rx-text">
          Prescription text
        </label>
        <textarea
          className="field field-tall"
          id="rx-text"
          rows={10}
          value={text}
          placeholder="Tab Crocin 500mg 1-0-1 x 5 days&#10;Cap Augmentin 625 BD x 7 days"
          onChange={(event) => setText(event.target.value)}
        />

        <button className="btn btn-primary form-gap" type="submit" disabled={!ready || state.busy}>
          Read the lines
        </button>
      </form>

      {state.busy && <Busy doing="Reading each line and checking it against the text" />}
      {state.error !== null && <Failure detail={state.error} onRetry={submit} />}

      {state.data !== null && (
        <section className="result">
          {state.data.unresolved_count > 0 && (
            <Coverage
              title={`${state.data.unresolved_count} line${state.data.unresolved_count === 1 ? "" : "s"} need confirming`}
              explanation="The brand could not be matched to a molecule with confidence. This is the resolver refusing to guess: a wrong molecule invalidates every other check, so a pharmacist must confirm these by hand."
            />
          )}

          {state.data.dropped.length > 0 && (
            <Coverage
              title="Dropped as unsupported"
              explanation="The gate refused these because the prescription text did not support them. Nothing was recorded for them, so they must be entered by hand if they are real."
              items={state.data.dropped}
            />
          )}

          {state.data.unresolved_count === 0 && state.data.dropped.length === 0 && (
            <p className="body">Every line was read and resolved.</p>
          )}
        </section>
      )}
    </main>
  );
}
