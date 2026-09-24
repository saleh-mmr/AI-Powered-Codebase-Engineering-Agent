import { useEffect, useState } from 'react';
import { ApiError } from '../../lib/api/http';
import { consumeEvents, type RunEvent } from './events';

interface Props {
  runId: string;
  onChanged: () => void;
  onExpired: () => void;
}

export function RunTimeline({ runId, onChanged, onExpired }: Props) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connection, setConnection] = useState('Connecting to live updates…');
  useEffect(() => {
    const controller = new AbortController();
    let cursor = 0;
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
        );
        if (controller.signal.aborted) return;
        if (result === 'complete') {
          setConnection('Timeline complete.');
          return;
        }
        failures = 0;
      } catch (reason) {
        if (controller.signal.aborted) return;
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
