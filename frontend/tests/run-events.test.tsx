import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { consumeEvents } from '../src/features/runs/events';
import { RunTimeline } from '../src/features/runs/RunTimeline';

function frame(sequence: number, status = 'queued') {
  return `id: ${sequence}\nevent: run.status\ndata: ${JSON.stringify({ run_id: 'r1', sequence, status, occurred_at: '2026-09-23T12:00:00Z' })}\n\n`;
}
function stream(parts: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const part of parts) controller.enqueue(encoder.encode(part));
        controller.close();
      },
    }),
    { headers: { 'Content-Type': 'text/event-stream' } },
  );
}
const end = 'event: stream.end\ndata: {}\n\n';
afterEach(() => vi.useRealTimers());

describe('SSE transport', () => {
  it('decodes fragmented CRLF frames and ignores duplicate IDs on replay', async () => {
    const text = (
      ': heartbeat\n\n' +
      frame(1) +
      frame(2, 'running') +
      end
    ).replace(/\n/g, '\r\n');
    const fetcher = vi.fn().mockResolvedValue(stream([...text]));
    vi.stubGlobal('fetch', fetcher);
    const receive = vi.fn();
    expect(
      await consumeEvents('r1', 1, receive, new AbortController().signal),
    ).toBe('complete');
    expect(receive).toHaveBeenCalledOnce();
    expect(receive.mock.calls[0][0].sequence).toBe(2);
    expect(fetcher.mock.calls[0][1].headers['Last-Event-ID']).toBe('1');
    expect(fetcher.mock.calls[0][1].credentials).toBe('same-origin');
  });
  it.each([
    frame(2),
    frame(1).replace('r1', 'other'),
    'event: run.status\ndata: {}\n\n',
    'x'.repeat(66000),
  ])('rejects a malformed or out-of-sequence frame', async (text) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stream([text])));
    await expect(
      consumeEvents('r1', 0, vi.fn(), new AbortController().signal),
    ).rejects.toThrow();
  });
  it('treats truncated EOF as interrupted, not completed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(stream([frame(1)])));
    await expect(
      consumeEvents('r1', 0, vi.fn(), new AbortController().signal),
    ).rejects.toThrow(/without a control frame/);
  });
  it('surfaces in-stream session expiry', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          stream(['event: stream.error\ndata: {"code":"unauthenticated"}\n\n']),
        ),
    );
    await expect(
      consumeEvents('r1', 0, vi.fn(), new AbortController().signal),
    ).rejects.toMatchObject({ status: 401 });
  });
});

describe('run timeline', () => {
  it('reconnects with its last ID without duplicating timeline items or submitting work', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(stream([frame(1)]))
      .mockResolvedValueOnce(
        stream([frame(1), frame(2, 'running'), frame(3, 'completed'), end]),
      );
    vi.stubGlobal('fetch', fetcher);
    const changed = vi.fn();
    render(<RunTimeline runId="r1" onChanged={changed} onExpired={vi.fn()} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText(/Live updates interrupted/)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(screen.getByText('Timeline complete.')).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(changed).toHaveBeenCalledTimes(3);
    expect(fetcher.mock.calls[1][1].headers['Last-Event-ID']).toBe('1');
    expect(
      fetcher.mock.calls.every((call) => call[1].method === undefined),
    ).toBe(true);
  });
  it('stops on session expiry and aborts on unmount', async () => {
    const expired = vi.fn();
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response('{}', { status: 401 }));
    vi.stubGlobal('fetch', fetcher);
    const { unmount } = render(
      <RunTimeline runId="r1" onChanged={vi.fn()} onExpired={expired} />,
    );
    await waitFor(() => expect(expired).toHaveBeenCalledOnce());
    unmount();
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
  });
});
