import type { Service } from "./services";
import { hrefFor } from "./useRoute";

/* The screens inside one service.
 *
 * Plain links under the header rule. Not tabs with borders and not a
 * segmented control: every service has a different number of screens and a
 * control that looks like a toggle implies they are alternatives rather than
 * places.
 */

interface Props {
  readonly service: Service;
  readonly active: string | null;
}

export function SubNav({ service, active }: Props): JSX.Element {
  return (
    <nav className="sub-nav" aria-label={`${service.label} screens`}>
      {service.screens.map((screen) => (
        <a
          key={screen.id}
          className="sub-link"
          href={hrefFor(service.id, screen.id)}
          aria-current={screen.id === active ? "page" : undefined}
        >
          {screen.label}
        </a>
      ))}
    </nav>
  );
}
