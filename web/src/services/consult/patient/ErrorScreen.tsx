/* The backend writes every error detail to state the remedy, so it is shown
 * rather than replaced with a generic message. */

interface Props {
  readonly detail: string | null;
  readonly onRestart: () => void;
}

export function ErrorScreen({ detail, onRestart }: Props): JSX.Element {
  return (
    <main className="patient screen">
      <h1 className="statement">Something went wrong.</h1>
      {detail !== null && <p className="body secondary error-detail">{detail}</p>}
      <div className="error-action">
        <button className="btn btn-secondary" onClick={onRestart}>
          Start again
        </button>
      </div>
    </main>
  );
}
