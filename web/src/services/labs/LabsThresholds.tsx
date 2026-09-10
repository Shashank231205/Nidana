import { useEffect } from "react";
import { readThresholds } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import type { ThresholdsResponse } from "../../lib/types";

/* Which critical value thresholds this deployment is running, and which of
 * them nobody has signed.
 *
 * A critical value means contact someone now. What counts as one differs
 * between laboratories, because it depends on the assay and the population, so
 * a threshold nobody verified is a number the deployment inherited rather than
 * chose. This screen exists so that fact is visible rather than buried in a
 * YAML file.
 */

export function LabsThresholds(): JSX.Element {
  const { state, run } = useAsync<ThresholdsResponse>();

  useEffect(() => {
    void run(readThresholds);
  }, [run]);

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Critical value thresholds</h1>
      <p className="page-intro">
        The analytes this deployment checks, and whether a clinician has
        verified each threshold against the laboratory&rsquo;s own assay.
      </p>

      {state.busy && <Busy doing="Reading the thresholds" />}
      {state.error !== null && (
        <Failure detail={state.error} onRetry={() => void run(readThresholds)} />
      )}

      {state.data !== null && (
        <section className="result">
          <p className="body">
            {state.data.count} threshold{state.data.count === 1 ? "" : "s"}{" "}
            loaded.
          </p>

          {state.data.unverified.length === 0 ? (
            <p className="body">Every threshold has been verified.</p>
          ) : (
            <>
              <p className="statement threshold-count">
                {state.data.unverified.length} of {state.data.count} unverified
              </p>
              <p className="body">
                These carry placeholder numbers that cannot fire as a real
                critical value. A clinician must set each against the
                laboratory&rsquo;s own assay and the current published source
                before this deployment can be released.
              </p>
              <ul className="plain threshold-list">
                {state.data.unverified.map((analyte) => (
                  <li key={analyte} className="data">
                    {analyte}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </main>
  );
}
