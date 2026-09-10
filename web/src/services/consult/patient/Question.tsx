import { useEffect, useRef, useState } from "react";

/* One question at a time. The patient never sees a previous question, a
 * progress bar, or a history above the current turn.
 *
 * Speech is the primary path in the design and the mic is the largest control,
 * but transcription runs on the clinic's own machine and that endpoint is not
 * built. The browser's Web Speech API is not a substitute: it ships audio to a
 * vendor's servers, which the on-premise guarantee forbids outright. So the
 * mic reports that speech is unavailable and the text path carries the turn.
 *
 * Transcription, when it exists, is confirmed before it is sent. Recognition
 * on Indian-accented medical speech fails often, and silently submitting a
 * wrong transcription corrupts the record.
 */

interface Props {
  readonly question: string;
  readonly turnIndex: number;
  readonly busy: string | null;
  readonly onAnswer: (utterance: string) => void;
}

export function Question({
  question,
  turnIndex,
  busy,
  onAnswer,
}: Props): JSX.Element {
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const [micNote, setMicNote] = useState<string | null>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setTyping(false);
    setText("");
    setMicNote(null);
  }, [question]);

  useEffect(() => {
    if (typing) field.current?.focus();
  }, [typing]);

  const send = (): void => {
    const utterance = text.trim();
    if (utterance.length === 0 || busy !== null) return;
    onAnswer(utterance);
  };

  return (
    <main className="patient screen">
      <p className="label">Question {turnIndex + 1}</p>

      <h1 className="question">{question}</h1>

      {!typing && (
        <div>
          <div className="mic-block">
            <button
              className="mic"
              data-state="idle"
              aria-label="Tap to speak your answer"
              onClick={() =>
                setMicNote(
                  "Speaking isn't available yet on this device. Please type your answer.",
                )
              }
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <rect x="9" y="2" width="6" height="11" rx="3" />
                <path d="M5 11a7 7 0 0 0 14 0" />
                <path d="M12 18v4" />
              </svg>
            </button>
            <p className="label mic-hint" role={micNote === null ? undefined : "status"}>
              {micNote ?? "Tap to speak"}
            </p>
          </div>

          <div className="type-instead">
            <button className="link" onClick={() => setTyping(true)}>
              Type instead
            </button>
          </div>
        </div>
      )}

      {typing && (
        <div>
          <label className="visually-hidden" htmlFor="utterance">
            Your answer
          </label>
          <textarea
            className="field"
            id="utterance"
            ref={field}
            rows={2}
            value={text}
            placeholder="Type your answer"
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
          />
          <div className="confirm-actions">
            <button
              className="btn btn-primary"
              disabled={text.trim().length === 0 || busy !== null}
              onClick={send}
            >
              Send
            </button>
          </div>
        </div>
      )}

      {busy !== null && (
        <p className="loading question-status" role="status">
          {busy}
        </p>
      )}
    </main>
  );
}
