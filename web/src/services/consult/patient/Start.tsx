import { useState } from "react";

/* Consent gates the control rather than being collected and ignored.
 *
 * The DPDP Act requires it to be explicit and logged, and the backend enforces
 * the same thing from the other side: a session with no recorded consent
 * returns 403 on its first turn. */

interface Props {
  readonly busy: string | null;
  readonly onStart: (granted: boolean) => void;
}

export function Start({ busy, onStart }: Props): JSX.Element {
  const [granted, setGranted] = useState(false);

  return (
    <main className="patient screen">
      <p className="meta">Nidana</p>

      <h1 className="statement start-statement">
        Tell us what&rsquo;s wrong. We&rsquo;ll tell you how urgently to see a
        doctor, and which one.
      </h1>

      <p className="body secondary start-note">
        This is not a diagnosis. Everything stays on this device.
      </p>

      <label className="checkbox start-consent" htmlFor="consent">
        <input
          type="checkbox"
          id="consent"
          checked={granted}
          onChange={(event) => setGranted(event.target.checked)}
        />
        <span>I agree to my answers being recorded for this session.</span>
      </label>

      <div className="start-action">
        <button
          className="btn btn-primary"
          disabled={!granted || busy !== null}
          onClick={() => onStart(granted)}
        >
          Start
        </button>
      </div>

      <p className="label start-emergency">
        If this is an emergency, go to a hospital now.
      </p>

      {busy !== null && (
        <p className="loading start-status" role="status">
          {busy}
        </p>
      )}
    </main>
  );
}
