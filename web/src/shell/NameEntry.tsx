import { useState } from "react";
import { Logo } from "./Logo";

/* Ask who is at the machine, and be honest about what that is worth.
 *
 * This name becomes `actor` on a forensic custody entry and `signed_by` on a
 * clinical note. Nothing verifies it. A record that reads "Dr Sharma signed
 * this" when anyone could type those words is worse than one that admits the
 * name is self-declared, so the screen says it in one line rather than
 * implying a login that does not exist.
 */

interface Props {
  readonly onSubmit: (name: string) => void;
}

export function NameEntry({ onSubmit }: Props): JSX.Element {
  const [name, setName] = useState("");
  const ready = name.trim().length > 0;

  return (
    <main className="entry">
      <p className="wordmark entry-mark">
        <Logo size={34} />
      </p>

      <form
        className="entry-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onSubmit(name);
        }}
      >
        <label className="label" htmlFor="actor-name">
          Your name
        </label>
        <input
          className="field"
          id="actor-name"
          value={name}
          autoComplete="name"
          autoFocus
          onChange={(event) => setName(event.target.value)}
        />

        <p className="body secondary entry-note">
          This name is recorded against everything you sign or amend. There is
          no login yet, so nothing verifies it. Type the name you would put on
          the record.
        </p>

        <button className="btn btn-primary" type="submit" disabled={!ready}>
          Continue
        </button>
      </form>
    </main>
  );
}
