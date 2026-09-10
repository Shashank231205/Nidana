import { Disclosures } from "./Disclosures";
import { BAND_TEXT, specialtyText } from "../../../lib/text";
import type { Triage } from "../../../lib/types";

/* Hierarchy is deliberately inverted: the band is a small marker and the
 * return criteria dominate. The criteria are the safety net that makes a
 * non-diagnostic system safe, so they carry the most weight on the page.
 *
 * The disclosures sit below the criteria and above nothing. They are part of
 * the outcome, not a footnote to it.
 */

interface Props {
  readonly triage: Triage | null;
  readonly disclosures: readonly string[];
  readonly onRestart: () => void;
}

export function Outcome({ triage, disclosures, onRestart }: Props): JSX.Element {
  const band = triage?.band;
  const criteria = triage?.return_criteria ?? [];
  const specialty = triage?.specialty;

  return (
    <main className="patient screen">
      {band !== undefined && (
        <p className="urgency-marker" data-band={band}>
          <span>{BAND_TEXT[band]}</span>
        </p>
      )}

      {specialty !== undefined && (
        <p className="criterion outcome-specialty">
          See {specialtyText(specialty)}.
        </p>
      )}

      {criteria.length > 0 && (
        <div className="return-criteria">
          <p className="label">Go to a hospital immediately if:</p>
          <ul className="plain criteria-list">
            {criteria.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <Disclosures disclosures={disclosures} />

      <hr className="rule outcome-divider" />

      <div className="outcome-actions">
        <button className="btn btn-secondary" onClick={onRestart}>
          Start again
        </button>
      </div>
    </main>
  );
}
