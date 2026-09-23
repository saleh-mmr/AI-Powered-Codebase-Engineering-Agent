import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError } from '../../lib/api/http';
import type { SearchMode } from '../search/api';
import {
  askRepository,
  getAnswerSettings,
  type Answer,
  type AnswerSettings,
} from './api';
import { GroundedAnswer } from './GroundedAnswer';

interface Props {
  repositoryId: string;
  csrf: string;
  onExpired: () => void;
  conversationId?: string;
  onSaved?: () => void;
  onBusy?: (busy: boolean) => void;
}
export function AnswerPanel({
  repositoryId,
  csrf,
  onExpired,
  conversationId,
  onSaved,
  onBusy,
}: Props) {
  const id = useId();
  const [settings, setSettings] = useState<AnswerSettings | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<SearchMode>('keyword');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [answeredQuestion, setAnsweredQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void getAnswerSettings(repositoryId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) {
          setSettings(next);
          setConfigError(null);
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) onExpired();
        else setConfigError('Unable to load answer settings. Retry below.');
      });
    return () => controller.abort();
  }, [repositoryId, onExpired, revision]);
  useEffect(() => () => request.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const submittedQuestion = question.trim();
    setBusy(true);
    onBusy?.(true);
    setError(null);
    setAnswer(null);
    setAnsweredQuestion(submittedQuestion);
    try {
      const result = await askRepository(
        repositoryId,
        submittedQuestion,
        mode,
        csrf,
        controller.signal,
        conversationId,
      );
      if (!controller.signal.aborted) {
        setAnswer(result);
        if (conversationId) onSaved?.();
      }
    } catch (reason) {
      if (controller.signal.aborted) return;
      if (reason instanceof ApiError && reason.status === 401) onExpired();
      else
        setError(
          reason instanceof ApiError
            ? reason.message
            : 'Answer request failed or timed out. A provider charge may have occurred. Retry deliberately.',
        );
    } finally {
      if (!controller.signal.aborted) {
        setBusy(false);
        onBusy?.(false);
      }
    }
  }
  return (
    <section
      className="index-inspector answer-panel"
      aria-label="Ask the repository"
    >
      <div className="card-heading">
        <h3>Ask the repository</h3>
        <span className="eyebrow">GROUNDED Q&A</span>
      </div>
      <p>
        Ask one question about this snapshot. Prepare the selected search mode
        above first.{' '}
        {conversationId
          ? 'Validated answers are saved here. Each question is answered independently; history is not model memory yet.'
          : 'This is a temporary question; select a conversation above to save it.'}
      </p>
      {!settings && !configError && (
        <p role="status">Loading answer settings…</p>
      )}
      {configError && <p role="alert">{configError}</p>}
      {!settings?.enabled && settings && (
        <p>
          AI answers are disabled. Enable them in server configuration to
          continue.
        </p>
      )}
      <button
        className="text-button"
        disabled={busy}
        onClick={() => setRevision((v) => v + 1)}
      >
        Refresh answer settings
      </button>
      {settings?.enabled && (
        <p className="field-help">
          Asking sends your question and retrieved source code to OpenAI and
          incurs API charges. {settings.model}: estimated $
          {settings.input_price_per_million}/million input tokens and $
          {settings.output_price_per_million}/million output tokens.
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
          disabled={busy}
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
          maxLength={512}
          rows={3}
          value={question}
          disabled={busy}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="How does verify_access_token reject expired tokens?"
        />
        <button
          type="submit"
          disabled={busy || !settings?.enabled || !question.trim()}
        >
          {busy ? 'Generating answer…' : 'Ask with sources'}
        </button>
      </form>
      {busy && (
        <p role="status">
          Retrieving evidence and generating an answer. This can take up to a
          minute.
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {answer && conversationId && (
        <p role="status">
          Answer saved. You can reopen it in this conversation.
        </p>
      )}
      {answer && !conversationId && (
        <>
          <p className="answer-question">Question: {answeredQuestion}</p>
          <GroundedAnswer answer={answer} />
        </>
      )}
    </section>
  );
}
