import { useConsult } from "./services/consult/patient/useConsult";
import { Start } from "./services/consult/patient/Start";
import { Question } from "./services/consult/patient/Question";
import { Emergency } from "./services/consult/patient/Emergency";
import { Outcome } from "./services/consult/patient/Outcome";
import { ErrorScreen } from "./services/consult/patient/ErrorScreen";

/* One screen is visible at a time.
 *
 * The switch is exhaustive over Phase, so a phase added without a screen is a
 * compile error rather than a blank page.
 */

export function App(): JSX.Element {
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
