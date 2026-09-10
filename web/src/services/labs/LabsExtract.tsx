import { useState } from "react";
import { extractReport } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { CriticalFindings } from "./CriticalFindings";
import { Coverage } from "../../components/Coverage";
import type { ExtractResponse } from "../../lib/types";

/* Read a report, then check it. One call, because a report read but not
 * checked is the failure this service exists to prevent.
 *
 * `dropped` is shown rather than logged. A result the groundedness gate
 * refused is one a human must enter by hand, and someone who cannot see the
 * refusals does not know the report is incomplete.
 */

export function LabsExtract(): JSX.Element {
  const [text, setText] = useState("");
  const [sourceId, setSourceId] = useState("");
  const { state, run } = useAsync<ExtractResponse>();

  const ready = text.trim().length > 0 && sourceId.trim().length > 0;
  const submit = (): void => {
    if (ready) void run(() => extractReport(text.trim(), sourceId.trim()));
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Extract from report text</h1>
      <p className="page-intro">
        Paste the text of a laboratory report. Every value read is checked
        against the critical value thresholds in the same step.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="label" htmlFor="source-id">
          Where this came from
        </label>
        <input
          className="field"
          id="source-id"
          value={sourceId}
          placeholder="Report reference or file name"
          onChange={(event) => setSourceId(event.target.value)}
        />

        <label className="label form-gap" htmlFor="report-text">
          Report text
        </label>
        <textarea
          className="field field-tall"
          id="report-text"
          rows={12}
          value={text}
          placeholder="Haemoglobin 6.2 g/dL&#10;Potassium 6.9 mmol/L"
          onChange={(event) => setText(event.target.value)}
        />

        <button className="btn btn-primary form-gap" type="submit" disabled={!ready || state.busy}>
          Read and check
        </button>
      </form>

      {state.busy && <Busy doing="Reading the report and checking every value" />}
      {state.error !== null && <Failure detail={state.error} onRetry={submit} />}

      {state.data !== null && (
        <>
          {state.data.dropped.length > 0 && (
            <Coverage
              title="Refused, enter by hand"
              explanation="The gate dropped these because the report text did not support them. A dropped result is one nobody has recorded, so this report is incomplete until someone enters them."
              items={state.data.dropped}
            />
          )}

          <CriticalFindings
            findings={state.data.critical_findings}
            unitMismatches={state.data.unit_mismatches}
            hasCritical={state.data.has_critical_value}
          />
        </>
      )}
    </main>
  );
}
