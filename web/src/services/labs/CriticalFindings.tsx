import { Coverage } from "../../components/Coverage";
import type { CriticalFindingResponse } from "../../lib/types";

/* What the deterministic layer found, and what it could not check.
 *
 * `unit_mismatches` is shown above the findings rather than below them,
 * because an empty findings list means something different when that list is
 * not empty: those analytes were skipped, not cleared.
 *
 * `unverified` on a finding means the threshold it fired against is a
 * placeholder nobody signed. That belongs beside the number, not in a footer.
 */

interface Props {
  readonly findings: readonly CriticalFindingResponse[];
  readonly unitMismatches: readonly string[];
  readonly hasCritical: boolean;
}

export function CriticalFindings({
  findings,
  unitMismatches,
  hasCritical,
}: Props): JSX.Element {
  return (
    <section className="result">
      {unitMismatches.length > 0 && (
        <Coverage
          title="Not checked"
          explanation="No threshold could be applied to these, because the units in the report do not match the units the threshold is written in. They were skipped, not cleared."
          items={unitMismatches}
        />
      )}

      {hasCritical ? (
        <>
          <p className="urgency-marker" data-band="U1">
            <span>Critical value</span>
          </p>
          <ul className="plain finding-list">
            {findings.map((finding) => (
              <li key={`${finding.analyte}-${finding.value}`} className="finding">
                <p className="finding-headline">
                  {finding.analyte} {finding.value} {finding.unit}
                  <span className="finding-flag"> {finding.flag}</span>
                </p>
                <p className="body">{finding.message}</p>
                <p className="meta">
                  Threshold {finding.threshold} {finding.unit} &middot;{" "}
                  {finding.source}
                </p>
                {finding.unverified && (
                  <p className="body finding-unverified">
                    This threshold is a placeholder. No clinician has verified
                    it against this laboratory&rsquo;s assay, so treat the
                    number as structural rather than clinical.
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="body">
          No critical value found among the analytes that could be checked.
        </p>
      )}
    </section>
  );
}
