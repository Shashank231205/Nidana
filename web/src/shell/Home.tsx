import { SERVICES } from "./services";
import { hrefFor } from "./useRoute";

/* Where a clinician lands. Five services, what each one does, nothing else.
 *
 * Deliberately not cards. Five identical rounded boxes would say the services
 * are interchangeable, and they are not: Consult sees patients, Forensics
 * produces evidence. A list with a name and a sentence says what a card says,
 * without the furniture.
 */

interface Props {
  readonly actor: string;
}

export function Home({ actor }: Props): JSX.Element {
  return (
    <main className="home">
      <p className="label">Signed in as {actor}</p>
      <h1 className="statement home-statement">What are you working on?</h1>

      <ul className="plain home-list">
        {SERVICES.map((service) => (
          <li key={service.id} className="home-item">
            <a className="home-link" href={hrefFor(service.id)}>
              {service.label}
            </a>
            <p className="body secondary home-summary">{service.summary}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
