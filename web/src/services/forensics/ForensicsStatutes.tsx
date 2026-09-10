import { useState } from "react";
import { lookUpStatute } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import type { StatuteResponse } from "../../lib/types";

/* IPC to BNS, and back.
 *
 * The Bharatiya Nyaya Sanhita replaced the Indian Penal Code on 1 July 2024
 * and renumbered nearly everything. A report citing IPC 302 and one citing
 * BNS 103 name the same offence, and someone reading an archived file needs to
 * know that.
 *
 * This screen translates numbers. It does not say which section applies to an
 * injury — that is a lawyer's judgement and `legally_reviewed` is false on
 * every response, which is shown rather than hidden.
 */

export function ForensicsStatutes(): JSX.Element {
  const [numbering, setNumbering] = useState<"ipc" | "bns">("ipc");
  const [section, setSection] = useState("");
  const { state, run } = useAsync<StatuteResponse>();

  const search = (): void => {
    const trimmed = section.trim();
    if (trimmed.length > 0) void run(() => lookUpStatute(numbering, trimmed));
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Statute lookup</h1>
      <p className="page-intro">
        Translate a section number between the Indian Penal Code and the
        Bharatiya Nyaya Sanhita, which replaced it on 1 July 2024.
      </p>

      <form
        className="lookup-form"
        onSubmit={(event) => {
          event.preventDefault();
          search();
        }}
      >
        <div className="lookup-row">
          <label className="visually-hidden" htmlFor="numbering">
            Which code the number is from
          </label>
          <select
            className="field field-select"
            id="numbering"
            value={numbering}
            onChange={(event) => setNumbering(event.target.value as "ipc" | "bns")}
          >
            <option value="ipc">IPC</option>
            <option value="bns">BNS</option>
          </select>

          <label className="visually-hidden" htmlFor="section">
            Section number
          </label>
          <input
            className="field"
            id="section"
            value={section}
            placeholder="302"
            onChange={(event) => setSection(event.target.value)}
          />

          <button className="btn btn-primary" type="submit" disabled={state.busy}>
            Look up
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Looking up the section" />}
      {state.error !== null && <Failure detail={state.error} onRetry={search} />}

      {state.data !== null && <Matches result={state.data} />}
    </main>
  );
}

function Matches({ result }: { readonly result: StatuteResponse }): JSX.Element {
  if (result.matches.length === 0) {
    return (
      <section className="result">
        <p className="body">
          No correspondence recorded for {result.numbering.toUpperCase()}{" "}
          {result.query}. The table covers the sections a medico-legal report
          commonly cites, not the whole code.
        </p>
      </section>
    );
  }

  return (
    <section className="result">
      {result.matches.map((match) => (
        <article key={`${match.ipc}-${match.bns ?? "repealed"}`} className="statute">
          <p className="statute-pair">
            <span className="statute-code">IPC {match.ipc}</span>
            <span className="statute-arrow" aria-hidden="true">
              →
            </span>
            <span className="statute-code">
              {match.bns === null ? "repealed" : `BNS ${match.bns}`}
            </span>
          </p>
          <p className="body statute-title">{match.title}</p>

          {match.repealed && (
            <p className="body secondary">
              The BNS deleted this section with no counterpart.
            </p>
          )}
          {match.changed && !match.repealed && (
            <p className="body secondary">
              The wording changed, not only the number. Read the new section
              before relying on the old one.
            </p>
          )}
          {match.note !== null && <p className="body secondary">{match.note}</p>}
        </article>
      ))}

      {/* Shown on every result, never suppressed. The table renumbers; it does
          not decide which section fits an injury. */}
      <p className="disclaimer">
        {result.legally_reviewed
          ? "This correspondence has been reviewed by a lawyer."
          : "This correspondence has not been checked by a lawyer. It translates section numbers and does not say which section applies to a case."}
      </p>
    </section>
  );
}
