import { useReadiness } from './useReadiness';

export function SystemStatus() {
  const { state, refresh } = useReadiness();
  return (
    <section className="status-card" aria-labelledby="status-title">
      <div className="card-heading">
        <span className="eyebrow">SYSTEM STATUS</span>
        <span className={`badge ${state.status}`}>
          {state.status === 'ready'
            ? 'Connected'
            : state.status === 'error'
              ? 'Needs attention'
              : 'Checking'}
        </span>
      </div>
      <h2 id="status-title">Your foundation, connected.</h2>
      <p>One live check across the API and database.</p>
      <div className="service-row">
        <div>
          <strong>React workspace</strong>
          <span>Application loaded in your browser</span>
        </div>
        <span className="indicator" aria-label="Available" />
      </div>
      <div className="service-row">
        <div>
          <strong>FastAPI + PostgreSQL</strong>
          <span>Database connection and pgvector extension</span>
        </div>
        <span
          className={`indicator ${state.status}`}
          aria-label={state.status}
        />
      </div>
      <div
        className="status-message"
        role={state.status === 'error' ? 'alert' : 'status'}
        aria-live="polite"
      >
        {state.status === 'loading' && 'Checking backend readiness…'}
        {state.status === 'ready' &&
          `All checks passed. Last checked at ${state.checkedAt.toLocaleTimeString()}.`}
        {state.status === 'error' && state.message}
      </div>
      <button onClick={refresh} disabled={state.status === 'loading'}>
        {state.status === 'loading' ? 'Checking…' : 'Check connection'}
      </button>
    </section>
  );
}
