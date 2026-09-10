import { SERVICES } from "./services";
import { hrefFor } from "./useRoute";

/* The wordmark, the five services, and who is at the machine.
 *
 * Not shown on the patient triage flow. A patient mid-triage has nowhere to
 * go — every other service is a clinician tool — and the emergency screen is
 * terminal by design, so a nav link beside "go to a hospital now" is a way out
 * of an instruction that must not have one.
 *
 * The active service is marked by weight and a rule, not a filled pill. The
 * urgency palette is never used here: red in this product means emergency.
 */

interface Props {
  readonly active: string | null;
  readonly actor: string | null;
  readonly onChangeActor: () => void;
}

export function Header({ active, actor, onChangeActor }: Props): JSX.Element {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <a className="wordmark" href="#/" aria-label="Nidana, home">
          Nidana
        </a>

        <nav className="service-nav" aria-label="Services">
          {SERVICES.map((service) => (
            <a
              key={service.id}
              className="service-link"
              href={hrefFor(service.id)}
              aria-current={service.id === active ? "page" : undefined}
            >
              {service.label}
            </a>
          ))}
        </nav>

        {actor !== null && (
          <button className="actor" onClick={onChangeActor} title="Change who is signed in">
            {actor}
          </button>
        )}
      </div>
    </header>
  );
}
