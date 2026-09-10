import { useState } from "react";
import { checkPrescription } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { Coverage } from "../../components/Coverage";
import type { CheckResponse } from "../../lib/types";

/* Check a medication list before it is dispensed.
 *
 * The two availability flags are shown on every result, not only when
 * something is missing. An empty findings list reads as "no interactions
 * found", and what is true in this build is "interactions were not checked" —
 * the dataset needs a commercial licence and none is configured. A pharmacist
 * who cannot see that distinction is being misled by silence.
 */

interface Line {
  readonly writtenAs: string;
  readonly molecules: string;
}

const EMPTY: Line = { writtenAs: "", molecules: "" };

/* A UUID for the record this check belongs to. The backend requires one and
 * this screen has no patient record behind it, so it is generated per check
 * and carries no identity. */
const newId = (): string =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : "00000000-0000-4000-8000-000000000000";

export function RxCheck({ actor }: { readonly actor: string }): JSX.Element {
  const [lines, setLines] = useState<readonly Line[]>([EMPTY, EMPTY]);
  const { state, run } = useAsync<CheckResponse>();

  const filled = lines.filter(
    (line) => line.writtenAs.trim().length > 0 && line.molecules.trim().length > 0,
  );
  const ready = filled.length > 0;

  const submit = (): void => {
    if (!ready) return;
    const sourceId = newId();
    const medications = {
      medications: filled.map((line, index) => ({
        written_as: line.writtenAs.trim(),
        molecules: line.molecules
          .split(",")
          .map((name) => name.trim().toLowerCase())
          .filter((name) => name.length > 0)
          .map((name) => ({ name })),
        resolution: "resolved",
        resolution_confidence: 1.0,
        provenance: {
          source_type: "examiner_entry",
          source_id: sourceId,
          examiner_id: actor,
          text: `${line.writtenAs.trim()} (${line.molecules.trim()})`,
          field_path: `medications.${index}`,
        },
      })),
    };
    void run(() =>
      checkPrescription(medications, {
        subject_type: "prescription",
        subject_id: sourceId,
      }),
    );
  };

  const update = (index: number, field: keyof Line, value: string): void => {
    setLines((prior) =>
      prior.map((line, at) => (at === index ? { ...line, [field]: value } : line)),
    );
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Check a prescription</h1>
      <p className="page-intro">
        Enter each medication as written and the molecules it contains. Indian
        formulations are combination-heavy, so a two-brand prescription is often
        a four-molecule question.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {lines.map((line, index) => (
          <div className="result-row" key={index}>
            <input
              className="field"
              value={line.writtenAs}
              placeholder="Brand as written"
              aria-label={`Medication ${index + 1}, as written`}
              onChange={(event) => update(index, "writtenAs", event.target.value)}
            />
            <input
              className="field"
              value={line.molecules}
              placeholder="Molecules, comma separated"
              aria-label={`Medication ${index + 1}, molecules`}
              onChange={(event) => update(index, "molecules", event.target.value)}
            />
          </div>
        ))}

        <button
          className="link"
          type="button"
          onClick={() => setLines((prior) => [...prior, EMPTY])}
        >
          Add another medication
        </button>

        <div className="form-gap">
          <button className="btn btn-primary" type="submit" disabled={!ready || state.busy}>
            Run every check
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Running every check that can run" />}
      {state.error !== null && <Failure detail={state.error} onRetry={submit} />}

      {state.data !== null && <Result result={state.data} />}
    </main>
  );
}

function Result({ result }: { readonly result: CheckResponse }): JSX.Element {
  return (
    <section className="result">
      {!result.interaction_checking_available && (
        <Coverage
          title="Interactions were not checked"
          explanation="No interaction dataset is configured on this deployment, so no medication pair was examined for interactions. This is not the same as finding none."
        />
      )}

      {result.interaction_checking_available &&
        result.molecules_not_interaction_checked.length > 0 && (
          <Coverage
            title="Molecules the dataset does not cover"
            explanation="These were skipped rather than cleared. Their interactions are unknown to this deployment."
            items={result.molecules_not_interaction_checked}
          />
        )}

      {result.blocks_dispensing && (
        <p className="urgency-marker" data-band="U1">
          <span>Do not dispense</span>
        </p>
      )}

      {result.findings.length === 0 ? (
        <p className="body">
          Nothing flagged by the checks that could run.
        </p>
      ) : (
        <ul className="plain finding-list">
          {result.findings.map((finding, index) => (
            <li key={`${finding.kind}-${index}`} className="finding">
              <p className="finding-headline">
                {finding.kind.replace(/_/g, " ")}
                <span className="finding-flag"> {finding.severity}</span>
              </p>
              <p className="body">{finding.message}</p>
              <p className="meta">
                {finding.written_as.join(", ")} &middot; {finding.source}
              </p>
              {finding.blocks_dispensing && (
                <p className="body finding-blocking">This blocks dispensing.</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {!result.brand_resolution_available && (
        <p className="meta result-note">
          Brand resolution is not configured, so molecules were taken as typed
          rather than resolved from a brand index.
        </p>
      )}
    </section>
  );
}
