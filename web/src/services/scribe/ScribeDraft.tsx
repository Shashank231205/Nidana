import { useState } from "react";
import { createEncounter, draftNote, signNote } from "../../lib/client";
import { useAsync, Busy, Failure } from "../../components/Async";
import { Coverage } from "../../components/Coverage";
import type { NoteResponse } from "../../lib/types";

/* Turn a transcript into a note, then sign it.
 *
 * Audio capture is not built. Transcription runs on the clinic's own machine
 * and the browser's Web Speech API would ship audio to a vendor, which the
 * on-premise guarantee forbids outright — so the transcript is entered as text
 * here, and the shape it is sent in is the shape the ASR path will produce.
 *
 * Signing is a separate deliberate act after reading what the gate dropped.
 * A screen that drafted and signed in one step would have the clinician
 * signing a note whose omissions they never saw.
 */

interface Turn {
  readonly speaker: "clinician" | "patient" | "family";
  readonly text: string;
}

const EMPTY: Turn = { speaker: "patient", text: "" };

export function ScribeDraft({ actor }: { readonly actor: string }): JSX.Element {
  const [encounterId, setEncounterId] = useState("");
  const [turns, setTurns] = useState<readonly Turn[]>([EMPTY]);
  const [signed, setSigned] = useState(false);
  const { state, run } = useAsync<NoteResponse>();

  const filled = turns.filter((turn) => turn.text.trim().length > 0);
  const ready = filled.length > 0;

  const submit = (): void => {
    if (!ready) return;
    setSigned(false);
    void run(async () => {
      const id =
        encounterId.trim().length > 0
          ? encounterId.trim()
          : (await createEncounter()).encounter_id;
      setEncounterId(id);

      /* Timings are sequential placeholders. The segment shape requires them
       * and text entry has none; the ASR path supplies the real ones. */
      const transcript = {
        segments: filled.map((turn, index) => ({
          text: turn.text.trim(),
          speaker: turn.speaker,
          audio_start_ms: index * 1000,
          audio_end_ms: (index + 1) * 1000,
        })),
      };
      return draftNote(id, transcript, {
        subject_type: "encounter",
        subject_id: id,
      });
    });
  };

  const sign = (): void => {
    if (encounterId.trim().length === 0) return;
    void run(async () => {
      await signNote(encounterId.trim(), actor);
      setSigned(true);
      return state.data as NoteResponse;
    });
  };

  const update = (index: number, patch: Partial<Turn>): void => {
    setTurns((prior) =>
      prior.map((turn, at) => (at === index ? { ...turn, ...patch } : turn)),
    );
  };

  return (
    <main className="page page-narrow">
      <h1 className="page-title">Draft a note</h1>
      <p className="page-intro">
        Enter what was said. Every statement in the note is checked against the
        transcript, and anything the transcript does not support is dropped.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {turns.map((turn, index) => (
          <div className="turn-row" key={index}>
            <label className="visually-hidden" htmlFor={`speaker-${index}`}>
              Who spoke, turn {index + 1}
            </label>
            <select
              className="field field-select"
              id={`speaker-${index}`}
              value={turn.speaker}
              onChange={(event) =>
                update(index, { speaker: event.target.value as Turn["speaker"] })
              }
            >
              <option value="patient">Patient</option>
              <option value="clinician">Clinician</option>
              <option value="family">Family</option>
            </select>
            <textarea
              className="field"
              rows={2}
              value={turn.text}
              placeholder="What was said"
              aria-label={`What was said, turn ${index + 1}`}
              onChange={(event) => update(index, { text: event.target.value })}
            />
          </div>
        ))}

        <button
          className="link"
          type="button"
          onClick={() => setTurns((prior) => [...prior, EMPTY])}
        >
          Add another turn
        </button>

        <div className="form-gap">
          <button className="btn btn-primary" type="submit" disabled={!ready || state.busy}>
            Draft the note
          </button>
        </div>
      </form>

      {state.busy && <Busy doing="Writing the note and checking every claim against the transcript" />}
      {state.error !== null && <Failure detail={state.error} onRetry={submit} />}

      {state.data !== null && !signed && (
        <section className="result">
          {state.data.fabrication_count > 0 ? (
            <Coverage
              title={`${state.data.fabrication_count} claim${state.data.fabrication_count === 1 ? "" : "s"} dropped`}
              explanation="The model wrote these and the transcript did not support them, so they were removed from the note. Read what remains knowing these are absent."
              items={state.data.dropped}
            />
          ) : (
            <p className="body">
              Every statement in the note is supported by the transcript.
            </p>
          )}

          <div className="form-gap">
            <p className="body secondary">
              Signing records this note against your name, {actor}. There is no
              login, so that name is self-declared.
            </p>
            <button className="btn btn-primary" onClick={sign} disabled={state.busy}>
              Sign this note
            </button>
          </div>
        </section>
      )}

      {signed && (
        <section className="result">
          <p className="body">Signed by {actor}.</p>
        </section>
      )}
    </main>
  );
}
