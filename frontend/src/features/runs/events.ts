import { z } from 'zod';
import { ApiError } from '../../lib/api/http';

const eventSchema = z.object({
  run_id: z.string(),
  sequence: z.number().int().min(1).max(3),
  status: z.enum(['queued', 'running', 'completed', 'failed', 'cancelled']),
  occurred_at: z.string(),
});
export type RunEvent = z.infer<typeof eventSchema>;

// Fetch supports our required same-origin header, AbortSignal and HTTP error handling.
// Native EventSource cannot set that header. The wire protocol remains ordinary SSE.
export async function consumeEvents(
  runId: string,
  cursor: number,
  onEvent: (event: RunEvent) => void,
  signal: AbortSignal,
  onConnected?: () => void,
): Promise<'complete' | 'reconnect'> {
  const response = await fetch(
    `/api/answer-runs/${encodeURIComponent(runId)}/events`,
    {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'text/event-stream',
        'X-RepoPilot-Request': '1',
        'Last-Event-ID': String(cursor),
      },
      signal: AbortSignal.any([signal, AbortSignal.timeout(35000)]),
    },
  );
  if (!response.ok)
    throw new ApiError(
      response.status,
      'Unable to connect to the run timeline.',
    );
  if (
    !response.headers.get('content-type')?.startsWith('text/event-stream') ||
    !response.body
  )
    throw new Error('Expected an event stream');
  onConnected?.();
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '';
  let bytes = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done)
        throw new Error('Event stream ended without a control frame');
      bytes += part.value.byteLength;
      if (bytes > 65536) throw new Error('Event stream exceeds limit');
      buffer += decoder.decode(part.value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      if (buffer.length > 8192) throw new Error('Event frame exceeds limit');
      let end: number;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        let type = '';
        let id = '';
        const data: string[] = [];
        for (const line of frame.split('\n')) {
          if (line.startsWith(':')) continue;
          const colon = line.indexOf(':');
          const name = colon < 0 ? line : line.slice(0, colon);
          const value =
            colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (name === 'event') type = value;
          if (name === 'id') id = value;
          if (name === 'data') data.push(value);
        }
        if (!type) continue; // Heartbeat/comment frames.
        if (type === 'run.status') {
          const event = eventSchema.parse(JSON.parse(data.join('\n')));
          if (event.run_id !== runId || id !== String(event.sequence))
            throw new Error('Invalid event identity');
          if (event.sequence <= cursor) continue;
          if (event.sequence !== cursor + 1)
            throw new Error('Event sequence gap');
          onEvent(event);
          cursor = event.sequence;
        } else if (type === 'stream.end') {
          return 'complete';
        } else if (type === 'stream.reconnect') {
          return 'reconnect';
        } else if (type === 'stream.error') {
          const error = z
            .object({ code: z.string() })
            .parse(JSON.parse(data.join('\n')));
          throw new ApiError(
            error.code === 'unauthenticated' ? 401 : 503,
            'Run timeline is unavailable.',
          );
        } else {
          throw new Error('Unknown stream event');
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
