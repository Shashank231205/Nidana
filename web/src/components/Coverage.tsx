/* What was not checked, stated as plainly as what was.
 *
 * Every service in this product reports its own gaps — Rx names the molecules
 * it could not check, Labs the analytes whose units did not match, Scribe the
 * claims the groundedness gate dropped. The reason is the same in each case:
 * an empty findings list reads as "nothing wrong", and what may be true is
 * "this was not examined".
 *
 * So the gap is never a muted footnote. It sits at the same weight as the
 * findings, above them where nothing was checked at all.
 */

interface Props {
  readonly title: string;
  /** Why this matters, in one sentence a clinician would accept. */
  readonly explanation: string;
  readonly items?: readonly string[];
}

export function Coverage({ title, explanation, items }: Props): JSX.Element {
  return (
    <section className="coverage" aria-label={title}>
      <p className="label">{title}</p>
      <p className="body">{explanation}</p>
      {items !== undefined && items.length > 0 && (
        <ul className="plain coverage-list">
          {items.map((item) => (
            <li key={item} className="data">
              {item}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
