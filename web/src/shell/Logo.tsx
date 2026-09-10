/* The Nidana mark.
 *
 * Nidana is the Sanskrit and Ayurvedic term for the cause of a disease, and
 * for the process of finding it. The mark says that rather than decorating
 * the name: a stack of three rules narrowing to a point, which is what
 * differential reasoning looks like drawn.
 *
 * Drawn rather than fetched. The product runs on-premise with no network
 * egress, so an image request would be a runtime dependency it cannot have,
 * and an inline SVG takes the surrounding text colour for free.
 */

interface Props {
  /** Height of the glyph in pixels. The wordmark scales with it. */
  readonly size?: number;
  readonly withWord?: boolean;
}

export function Logo({ size = 22, withWord = true }: Props): JSX.Element {
  return (
    <span className="logo" aria-label="Nidana">
      <svg
        className="logo-glyph"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        {/* Three findings narrowing to one conclusion. */}
        <path
          d="M2 5h20M4.5 12h15M9 19h6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="square"
        />
        {/* The conclusion itself, in the accent: the one thing the reasoning
            arrives at, and the only mark that is not a rule. */}
        <circle cx="12" cy="19" r="2.6" fill="var(--accent)" stroke="none" />
      </svg>
      {withWord && <span className="logo-word">Nidana</span>}
    </span>
  );
}
