/* The consultation state machine.
 *
 * Separated from rendering so the sequence can be tested without a DOM: the
 * ordering constraint it enforces is a safety property, not a presentation
 * detail.
 *
 * The ordering: a session is created, consent is recorded, and only then may a
 * turn be taken. `POST /turns` returns 403 on a session with no recorded
 * consent, so this is the backend's rule and not a convention invented here.
 */

import { useCallback, useState } from "react";
import { ApiError, createSession, recordConsent, submitTurn } from "../../../lib/client";
import { SHAPE } from "../../../lib/types";
import type { TurnResponse } from "../../../lib/types";

export type Phase = "start" | "question" | "emergency" | "outcome" | "error";

export interface ConsultState {
  readonly phase: Phase;
  readonly sessionId: string | null;
  readonly turn: TurnResponse | null;
  readonly busy: string | null;
  readonly error: string | null;
  /** Rules in force that run on a model's reading rather than a signature.
   *
   * Held on the session rather than read off the latest turn: the outcome
   * screen must show them, and it renders after `complete`, whose response
   * carries the same list. Keeping the last non-empty list means a disclosure
   * cannot be lost by a response that happens to omit it. */
  readonly disclosures: readonly string[];
}

const INITIAL: ConsultState = {
  phase: "start",
  sessionId: null,
  turn: null,
  busy: null,
  error: null,
  disclosures: [],
};

const phaseFor = (turn: TurnResponse): Phase => {
  switch (turn.shape) {
    case SHAPE.NEXT_QUESTION:
      return "question";
    case SHAPE.TERMINAL_EMERGENCY:
      return "emergency";
    case SHAPE.COMPLETED_TRIAGE:
      return "outcome";
  }
};

const messageFor = (cause: unknown): string =>
  cause instanceof ApiError
    ? cause.detail
    : "Something went wrong on this device.";

export function useConsult(): {
  state: ConsultState;
  begin: (granted: boolean) => Promise<void>;
  answer: (utterance: string) => Promise<void>;
  restart: () => void;
} {
  const [state, setState] = useState<ConsultState>(INITIAL);

  /** Create the session and record consent before the first question.
   *
   * Both calls happen here because a session without consent takes no turns:
   * splitting them would leave a session that exists and can do nothing. */
  const begin = useCallback(async (granted: boolean): Promise<void> => {
    setState((prior) => ({ ...prior, busy: "Starting your session", error: null }));
    try {
      const session = await createSession();
      await recordConsent(session.session_id, granted);
      const turn = await submitTurn(session.session_id, "I would like to start.");
      setState({
        phase: phaseFor(turn),
        sessionId: session.session_id,
        turn,
        busy: null,
        error: null,
        disclosures: turn.disclosures,
      });
    } catch (cause) {
      setState({ ...INITIAL, phase: "error", error: messageFor(cause) });
    }
  }, []);

  const answer = useCallback(
    async (utterance: string): Promise<void> => {
      const sessionId = state.sessionId;
      if (sessionId === null) return;
      setState((prior) => ({ ...prior, busy: "Checking your answer", error: null }));
      try {
        const turn = await submitTurn(sessionId, utterance);
        setState((prior) => ({
          phase: phaseFor(turn),
          sessionId,
          turn,
          busy: null,
          error: null,
          disclosures:
            turn.disclosures.length > 0 ? turn.disclosures : prior.disclosures,
        }));
      } catch (cause) {
        setState((prior) => ({
          ...prior,
          busy: null,
          phase: "error",
          error: messageFor(cause),
        }));
      }
    },
    [state.sessionId],
  );

  const restart = useCallback((): void => setState(INITIAL), []);

  return { state, begin, answer, restart };
}
