import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { consumeEvents, type RunEvent } from './events';

interface Props {
  runId: string;
  runStatus?: string;
  onChanged: () => void;
  onExpired: () => void;
}

export function RunTimeline({ runId, runStatus, onChanged, onExpired }: Props) {
  const [preview, setPreview] = useState('');
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connection, setConnection] = useState('Connecting to live updates…');
  useEffect(() => {
    const controller = new AbortController();
    let cursor = 0;
    let terminalSeen = false;
    let previewRevision = -1;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function connect() {
      let delay = 1000;
      try {
        const result = await consumeEvents(
          runId,
          cursor,
          (event) => {
            if (controller.signal.aborted) return;
            cursor = event.sequence;
            if (['completed', 'failed', 'cancelled'].includes(event.status)) {
              terminalSeen = true;
              setPreview('');
            }
            failures = 0;
            setEvents((previous) =>
              [
                ...previous.filter((item) => item.sequence !== event.sequence),
                event,
              ].sort((a, b) => a.sequence - b.sequence),
            );
            setConnection('Live updates connected.');
            onChanged();
          },
          controller.signal,
          () => {
            if (!controller.signal.aborted)
              setConnection('Live updates connected.');
          },
          (value) => {
            if (
              !controller.signal.aborted &&
              !terminalSeen &&
              value.revision >= previewRevision
            ) {
              previewRevision = value.revision;
              setPreview(value.text);
            }
          },
        );
        if (controller.signal.aborted) return;
        if (result === 'complete') {
          setPreview('');
          setConnection('Timeline complete.');
          return;
        }
        failures = 0;
      } catch (reason) {
        if (controller.signal.aborted) return;
        setPreview('');
        if (reason instanceof ApiError && reason.status === 401) {
          onExpired();
          return;
        }
        setConnection(
          'Live updates interrupted. Status polling continues; reconnecting…',
        );
        if (
          reason instanceof ApiError &&
          [403, 404, 409, 422].includes(reason.status)
        ) {
          setConnection(
            'Timeline unavailable. Refresh the conversation to recover.',
          );
          return;
        }
        failures += 1;
        delay =
          reason instanceof ApiError && reason.status === 429
            ? 60000
            : Math.min(15000, 1000 * 2 ** Math.min(failures, 4));
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => {
          void connect();
        }, delay);
    }
    void connect();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [runId, onChanged, onExpired]);
  return (
    <section className="run-timeline" aria-label="Latest answer timeline">
      <h5>Latest answer timeline</h5>
      <p className="field-help" role="status">
        {connection}
      </p>
      {preview && (!runStatus || runStatus === 'running') && (
        <section className="answer-preview" aria-label="Provisional answer">
          <h5>Draft — not yet validated</h5>
          <p>
            This text may change or be discarded. Source links appear only after
            validation.
          </p>
          <pre aria-label="Provisional answer text">{preview}</pre>
        </section>
      )}
      <ol>
        {events.map((event) => (
          <li key={event.sequence}>
            {event.status} ·{' '}
            <time dateTime={event.occurred_at}>
              {new Date(event.occurred_at).toLocaleTimeString()}
            </time>
          </li>
        ))}
      </ol>
      <p className="field-help">
        Run-state updates appear here. The grounded answer is published after
        validation.
      </p>
    </section>
  );
}
