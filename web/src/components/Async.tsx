/* Loading and error states, shared by every clinician screen.
 *
 * The loading state names the operation rather than spinning. A clinician
 * waiting on a slow on-premise box needs to know which of several slow things
 * is happening, and "Checking interactions" answers that where a spinner does
 * not.
 */

import { useCallback, useState } from "react";
import { ApiError } from "../lib/http";

export function Busy({ doing }: { readonly doing: string }): JSX.Element {
  return (
    <p className="loading" role="status">
      {doing}
    </p>
  );
}

export function Failure({
  detail,
  onRetry,
}: {
  readonly detail: string;
  readonly onRetry?: () => void;
}): JSX.Element {
  return (
    <section className="failure" role="alert">
      <p className="label">That did not work</p>
      <p className="body">{detail}</p>
      {onRetry !== undefined && (
        <button className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </section>
  );
}

export interface AsyncState<T> {
  readonly data: T | null;
  readonly busy: boolean;
  readonly error: string | null;
}

/** Run one request, holding what it returned or why it failed.
 *
 * The backend writes error detail to state the remedy, so it is surfaced
 * verbatim rather than replaced with a generic message.
 */
export function useAsync<T>(): {
  state: AsyncState<T>;
  run: (work: () => Promise<T>) => Promise<void>;
  reset: () => void;
} {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    busy: false,
    error: null,
  });

  const run = useCallback(async (work: () => Promise<T>): Promise<void> => {
    setState({ data: null, busy: true, error: null });
    try {
      const data = await work();
      setState({ data, busy: false, error: null });
    } catch (cause) {
      setState({
        data: null,
        busy: false,
        error:
          cause instanceof ApiError
            ? cause.detail
            : "Something went wrong on this device.",
      });
    }
  }, []);

  const reset = useCallback((): void => {
    setState({ data: null, busy: false, error: null });
  }, []);

  return { state, run, reset };
}
