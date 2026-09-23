import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../../lib/api/http';
import { getAnswerSettings, type AnswerSettings } from '../answers/api';
import type { SearchMode } from '../search/api';
import {
  cancelRun,
  listRuns,
  submitRun,
  type AnswerRun,
  type Submission,
} from './api';
interface Props {
  repositoryId: string;
  conversationId: string;
  csrf: string;
  onExpired: () => void;
  onCompleted: () => void;
}
export function RunComposer({
  repositoryId,
  conversationId,
  csrf,
  onExpired,
  onCompleted,
}: Props) {
  const id = useId();
  const [settings, setSettings] = useState<AnswerSettings | null>(null);
  const [runs, setRuns] = useState<AnswerRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<SearchMode>('keyword');
  const [pending, setPending] = useState<Submission | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const completed = useRef(new Set<string>());
  const active = runs.some(
    (run) => run.status === 'queued' || run.status === 'running',
  );
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      let delay = 5000;
      try {
        const [next, configuration] = await Promise.all([
          listRuns(conversationId, controller.signal),
          getAnswerSettings(repositoryId, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        setSettings(configuration);
        setRuns(next);
        setStatusError(null);
        setLoading(false);
        setPending((previous) =>
          previous &&
          next.some((run) => run.request_key === previous.request_key)
            ? null
            : previous,
        );
        for (const run of next)
          if (run.status === 'completed' && !completed.current.has(run.id)) {
            completed.current.add(run.id);
            onCompleted();
          }
        delay = next.some(
          (run) => run.status === 'queued' || run.status === 'running',
        )
          ? 2000
          : 10000;
      } catch (reason) {
        if (controller.signal.aborted) return;
        setLoading(false);
        if (reason instanceof ApiError && reason.status === 401) {
          onExpired();
          return;
        }
        setStatusError(
          'Unable to read run status. Your run may still be working. Retrying…',
        );
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => {
          void poll();
        }, delay);
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [conversationId, repositoryId, onExpired, onCompleted, revision]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = pending ?? {
      question: question.trim(),
      mode,
      request_key: crypto.randomUUID(),
    };
    setPending(data);
    setBusy(true);
    setError(null);
    try {
      const result = await submitRun(conversationId, data, csrf);
      setRuns((previous) =>
        [result, ...previous.filter((item) => item.id !== result.id)].slice(
          0,
          20,
        ),
      );
      setPending(null);
      setQuestion('');
      setRevision((value) => value + 1);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) onExpired();
      if (
        reason instanceof ApiError &&
        [400, 401, 403, 404, 409, 422, 429].includes(reason.status)
      )
        setPending(null);
      setError(
        reason instanceof ApiError
          ? reason.message
          : 'Submission status is uncertain. Retry the same submission below; its key prevents creating a second run.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function cancel(id: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await cancelRun(id, csrf);
      setRuns((previous) =>
        previous.map((item) => (item.id === id ? result : item)),
      );
      setRevision((v) => v + 1);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) onExpired();
      else
        setError(
          reason instanceof ApiError
            ? reason.message
            : 'Unable to cancel. Refresh status before retrying.',
        );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="index-inspector" aria-label="Background answers">
      <h4>Ask in the background</h4>
      <p>
        Follow-up questions can use up to three recent answered turns from the
        same source index. Older or oversized turns may be omitted. Name the
        function or file if a follow-up is ambiguous. You can close this view
        and reopen the conversation to check progress.
      </p>
      <button
        disabled={busy}
        className="text-button"
        onClick={() => setRevision((v) => v + 1)}
      >
        Refresh run status
      </button>
      {loading && <p role="status">Loading answer runs…</p>}
      {statusError && <p role="status">{statusError}</p>}
      {settings && !settings.enabled && (
        <p>AI answers are disabled in server configuration.</p>
      )}
      {settings?.enabled && (
        <p className="field-help">
          Submitting sends the question, selected recent turns, and retrieved
          code to OpenAI when the worker starts, and can incur API charges.
          Model: {settings.model}.
        </p>
      )}
      <form
        className="search-form"
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <label htmlFor={`${id}-mode`}>Answer retrieval mode</label>
        <select
          id={`${id}-mode`}
          value={mode}
          disabled={busy || !!pending || active}
          onChange={(event) =>
            setMode(event.target.value === 'hybrid' ? 'hybrid' : 'keyword')
          }
        >
          <option value="keyword">Keyword + symbols</option>
          <option value="hybrid" disabled={!settings?.embeddings_enabled}>
            Hybrid + semantic
          </option>
        </select>
        <label htmlFor={`${id}-question`}>Question about the code</label>
        <textarea
          id={`${id}-question`}
          required
          rows={3}
          maxLength={512}
          value={pending?.question ?? question}
          disabled={busy || !!pending || active}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button
          type="submit"
          disabled={
            busy ||
            loading ||
            !!statusError ||
            !settings?.enabled ||
            active ||
            (!pending && !question.trim())
          }
        >
          {busy
            ? 'Saving…'
            : pending
              ? 'Retry same submission'
              : 'Queue answer'}
        </button>
      </form>
      {active && (
        <p role="status">
          An answer is queued or running. No need to keep this page open.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {!loading && runs.length === 0 && !statusError && (
        <p>No answer runs yet.</p>
      )}
      <ol className="answer-runs">
        {runs.map((run) => (
          <li key={run.id}>
            <p>
              <strong>{run.status}</strong> · {run.question}
            </p>
            {run.error_message && (
              <p className="form-error">{run.error_message}</p>
            )}
            {run.status === 'completed' && (
              <p>Saved in the conversation history above.</p>
            )}
            {run.usage_state === 'recorded' ? (
              <p className="field-help">
                {run.input_tokens} input / {run.output_tokens} output tokens ·
                estimated total ${run.estimated_cost_usd?.toFixed(6)}
              </p>
            ) : (
              run.usage_state === 'unknown' && (
                <p className="field-help">
                  Usage is not confirmed. Provider charges may have occurred.
                </p>
              )
            )}
            {(run.status === 'queued' || run.status === 'running') && (
              <>
                <button
                  disabled={busy}
                  onClick={() => {
                    void cancel(run.id);
                  }}
                >
                  Cancel answer
                </button>
                <p className="field-help">
                  Cancellation stops publication. It cannot guarantee stopping a
                  provider call already in progress.
                </p>
              </>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
