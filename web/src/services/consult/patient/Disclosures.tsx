/* What the patient is told when a rule ran on a model's reading.
 *
 * The backend recomputes this per response and its docstring is explicit: a
 * client showing a triage outcome must show these with it. A band produced
 * partly by criteria no clinician signed, presented as though it were not, is
 * the failure the attestation state exists to prevent.
 *
 * Rendered as plain text below the outcome rather than as a dismissible
 * notice. A disclosure with a close button is a disclosure the patient can be
 * one tap away from never having seen.
 */

interface Props {
  readonly disclosures: readonly string[];
}

export function Disclosures({ disclosures }: Props): JSX.Element | null {
  if (disclosures.length === 0) return null;

  return (
    <section className="disclosures" aria-label="How this advice was checked">
      <p className="label">How this advice was checked</p>
      <p className="body secondary">
        Some of the safety checks behind this advice were reviewed by software,
        not signed off by a doctor. Treat it as a guide and see a doctor as
        described above.
      </p>
      <ul className="plain disclosure-list">
        {disclosures.map((line) => (
          <li key={line} className="meta">
            {line}
          </li>
        ))}
      </ul>
    </section>
  );
}
