import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { getRunUsage, type RunUsageData } from './api';

export function RunUsage({
  runId,
  onExpired,
}: {
  runId: string;
  onExpired: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<RunUsageData | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void getRunUsage(runId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) onExpired();
        else setError(true);
      });
    return () => controller.abort();
  }, [runId, open, revision, onExpired]);
  return (
    <div>
      <button
        className="text-button"
        aria-expanded={open}
        onClick={() => {
          setData(null);
          setError(false);
          setOpen(!open);
        }}
      >
        Call usage receipts
      </button>
      {open && (
        <div aria-label="Call usage receipts">
          <button
            onClick={() => {
              setData(null);
              setError(false);
              setRevision(revision + 1);
            }}
          >
            Refresh receipts
          </button>
          {error ? (
            <p role="alert">Unable to load receipts. Try refreshing.</p>
          ) : !data ? (
            <p role="status">Loading receipts…</p>
          ) : (
            <>
              {!data.tracked ? (
                <p>
                  This older run has no per-call tracking. Missing receipts do
                  not mean zero cost.
                </p>
              ) : (
                <>
                  <p>
                    Known subtotal: ${Number(data.known_cost_usd).toFixed(6)}.
                    Unknown calls: {data.unknown_calls}.
                  </p>
                  {data.items.length === 0 && (
                    <p>No provider attempts recorded yet.</p>
                  )}
                  <ul>
                    {data.items.map((item) => (
                      <li key={item.id}>
                        {item.kind === 'generation'
                          ? 'Answer generation'
                          : 'Query embedding'}{' '}
                        · {item.model}:{' '}
                        {item.input_tokens === null
                          ? 'Usage unknown; charges may have occurred.'
                          : `${item.input_tokens} input / ${item.output_tokens} output tokens · estimated $${Number(item.estimated_cost_usd).toFixed(6)}`}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <p className="field-help">
                Estimates use rates captured at call start. Unknown calls are
                excluded from the subtotal. Cancellation does not undo provider
                charges. Refresh for late receipts. Indexing and standalone
                requests are outside this run.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
