import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { GroundedAnswer } from '../answers/GroundedAnswer';
import { getMessages, type MessagePage } from './api';
interface Props {
  conversationId: string;
  onExpired: () => void;
}
export function ConversationTranscript({ conversationId, onExpired }: Props) {
  const [messages, setMessages] = useState<MessagePage['items']>([]);
  const [before, setBefore] = useState<number | null>(null);
  const [next, setNext] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void getMessages(conversationId, before, controller.signal)
      .then((page) => {
        if (controller.signal.aborted) return;
        setMessages((old) =>
          before === null ? page.items : [...page.items, ...old],
        );
        setNext(page.next_before);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) onExpired();
        else
          setError(
            'Unable to load saved messages. Retry history loading; do not resubmit your question.',
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [conversationId, before, revision, onExpired]);
  return (
    <section className="conversation-transcript" aria-label="Saved messages">
      <h4>Saved questions and answers</h4>
      <button
        disabled={loading}
        onClick={() => {
          setLoading(true);
          setBefore(null);
          setRevision((v) => v + 1);
        }}
      >
        Refresh history
      </button>
      {loading && <p role="status">Loading history…</p>}
      {error && (
        <>
          <p role="alert">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              setRevision((v) => v + 1);
            }}
          >
            Retry history
          </button>
        </>
      )}
      {next !== null && !error && (
        <button
          disabled={loading}
          onClick={() => {
            setLoading(true);
            setBefore(next);
          }}
        >
          Load older messages
        </button>
      )}
      {!loading && !error && messages.length === 0 && (
        <p>No saved messages yet. Ask your first question below.</p>
      )}
      {messages.map((message) => (
        <div className={`saved-message saved-${message.role}`} key={message.id}>
          {message.role === 'assistant' && message.answer ? (
            <GroundedAnswer answer={message.answer} />
          ) : (
            <p className="answer-question">
              {message.role === 'user' ? 'Question: ' : ''}
              {message.content}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}
