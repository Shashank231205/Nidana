import { useEffect, useState } from "react";
import { interpretReport, readThresholds } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { CriticalFindings } from "./CriticalFindings";
import type { InterpretResponse, ThresholdsResponse } from "../../lib/types";

/* Enter results by hand and check them.
 *
 * Every result carries provenance, so a hand-entered one records who entered
 * it and what they typed. The examiner's name and the verbatim text are the
 * provenance; there is no path by which a value enters the record unattributed.
 *
 * The unverified-threshold notice sits above the result and not below it. With
 * placeholder thresholds a genuinely dangerous potassium of 6.9 mmol/L returns
 * "no critical value", and a clinician reading that as reassurance is the
 * exact failure this service exists to prevent.
 */

interface Row {
  readonly analyte: string;
  readonly value: string;
  readonly unit: string;
}

const EMPTY: Row = { analyte: "", value: "", unit: "" };

export function LabsReport({ actor }: { readonly actor: string }): JSX.Element {
  const [rows, setRows] = useState<readonly Row[]>([EMPTY]);
  const [sourceId, setSourceId] = useState("");
  const { state, run } = useAsync<InterpretResponse>();
  const thresholds = useAsync<ThresholdsResponse>();

  useEffect(() => {
    void thresholds.run(readThresholds);
  }, [thresholds.run]);

  const filled = rows.filter(
    (row) => row.analyte.trim().length > 0 && row.value.trim().length > 0,
  );
  const ready = filled.length > 0 && sourceId.trim().length > 0;

  const submit = (): void => {
    if (!ready) return;
    const report = {
      results: filled.map((row, index) => ({
        analyte: row.analyte.trim(),
        value: Number(row.value),
        unit: row.unit.trim(),
        provenance: {
          source_type: "examiner_entry",
          source_id: sourceId.trim(),
          examiner_id: actor,
          text: `${row.analyte.trim()} ${row.value.trim()} ${row.unit.trim()}`.trim(),
          field_path: `results.${index}.value`,
        },
      })),
    };
    void run(() => interpretReport(report));
  };

  const update = (index: number, field: keyof Row, value: string): void => {
    setRows((prior) =>
      prior.map((row, at) => (at === index ? { ...row, [field]: value } : row)),
    );
  };

  const unverified = thresholds.state.data?.unverified ?? [];

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Interpret a report</h1>
      <p className="page-intro">
        Enter the results. Each is recorded against your name, with what you
        typed kept verbatim.
      </p>

      {unverified.length > 0 && (
        <section className="coverage" aria-label="Thresholds are unverified">
          <p className="label">Thresholds are unverified</p>
          <p className="body">
            {unverified.length} of {thresholds.state.data?.count} thresholds
            carry placeholder numbers that cannot fire. A result checked against
            them can come back clear while being dangerous, so do not read
            &ldquo;no critical value&rdquo; as reassurance until a clinician has
            set these.
          </p>
        </section>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="label" htmlFor="lab-source">
          Report reference
        </label>
        <input
          className="field"
          id="lab-source"
          value={sourceId}
          placeholder="Laboratory report number"
          onChange={(event) => setSourceId(event.target.value)}
        />

        <p className="label form-gap">Results</p>
        {rows.map((row, index) => (
          <div className="result-row" key={index}>
            <input
              className="field"
              value={row.analyte}
              placeholder="Analyte"
              aria-label={`Analyte ${index + 1}`}
              onChange={(event) => update(index, "analyte", event.target.value)}
            />
            <input
              className="field field-short"
              value={row.value}
              inputMode="decimal"
              placeholder="Value"
              aria-label={`Value ${index + 1}`}
              onChange={(event) => update(index, "value", event.target.value)}
            />
            <input
              className="field field-short"
              value={row.unit}
              placeholder="Unit"
              aria-label={`Unit ${index + 1}`}
              onChange={(event) => update(index, "unit", event.target.value)}
            />
          </div>
        ))}

        <button
          className="link"
          type="button"
          onClick={() => setRows((prior) => [...prior, EMPTY])}
        >
          Add another result
        </button>

        <div className="form-gap">
          <button className="btn btn-primary" type="submit" disabled={!ready || state.busy}>
            Check against thresholds
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Checking every value against its threshold" />}
      {state.error !== null && <Failure detail={state.error} onRetry={submit} />}

      {state.data !== null && (
        <CriticalFindings
          findings={state.data.critical_findings}
          unitMismatches={state.data.unit_mismatches}
          hasCritical={state.data.has_critical_value}
        />
      )}
    </main>
  );
}
