import { capabilityText } from "../../../lib/text";
import type { Emergency as EmergencyData } from "../../../lib/types";

/* Terminal. No back, no close, no dismiss, no continue-anyway.
 *
 * The capability list is not decoration: sending someone to the nearest
 * hospital is wrong if it cannot treat them, so what the hospital must be able
 * to do is named in words the patient can act on.
 */

interface Props {
  readonly emergency: EmergencyData | null;
}

export function Emergency({ emergency }: Props): JSX.Element {
  const capabilities = emergency?.capabilities_required ?? [];

  return (
    <main className="screen">
      <p className="urgency-band">Go to a hospital now.</p>

      <div className="patient emergency-body">
        <p className="criterion">
          Your answers suggest something that needs to be checked immediately. Do
          not wait. Do not drive yourself.
        </p>

        {capabilities.length > 0 && (
          <div className="emergency-capabilities">
            <p className="label">The hospital needs to have</p>
            <ul className="plain capability-list">
              {capabilities.map((key) => (
                <li key={key}>{capabilityText(key)}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="emergency-action">
          <p className="body emergency-call">Call 108</p>
        </div>
      </div>
    </main>
  );
}
