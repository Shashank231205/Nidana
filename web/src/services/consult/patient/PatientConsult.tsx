import { useConsult } from "./useConsult";
import { Start } from "./Start";
import { Question } from "./Question";
import { Emergency } from "./Emergency";
import { Outcome } from "./Outcome";
import { ErrorScreen } from "./ErrorScreen";

/* The patient triage flow. One screen at a time, no header, no way out of the
 * emergency screen.
 *
 * The switch is exhaustive over Phase, so a phase added without a screen is a
 * compile error rather than a blank page.
 */

export function PatientConsult(): JSX.Element {
  const { state, begin, answer, restart } = useConsult();

  switch (state.phase) {
    case "start":
      return <Start busy={state.busy} onStart={begin} />;
    case "question":
      return (
        <Question
          question={state.turn?.question ?? ""}
          turnIndex={state.turn?.turn_index ?? 0}
          busy={state.busy}
          onAnswer={answer}
        />
      );
    case "emergency":
      return <Emergency emergency={state.turn?.emergency ?? null} />;
    case "outcome":
      return (
        <Outcome
          triage={state.turn?.triage ?? null}
          disclosures={state.disclosures}
          onRestart={restart}
        />
      );
    case "error":
      return <ErrorScreen detail={state.error} onRestart={restart} />;
  }
}
