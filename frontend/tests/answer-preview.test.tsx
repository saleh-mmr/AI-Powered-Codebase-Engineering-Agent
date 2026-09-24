import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { consumeEvents } from '../src/features/runs/events';
import { RunTimeline } from '../src/features/runs/RunTimeline';

function status(sequence: number, state: string) {
  return `id: ${sequence}\nevent: run.status\ndata: ${JSON.stringify({ run_id: 'r1', sequence, status: state, occurred_at: '2026-09-24T12:00:00Z' })}\n\n`;
}
function preview(revision: number, text: string, runId = 'r1') {
  return `event: answer.preview\ndata: ${JSON.stringify({ run_id: runId, revision, text })}\n\n`;
}
const end = 'event: stream.end\ndata: {}\n\n';
const encoder = new TextEncoder();
function response(text: string) {
  return new Response(text, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('provisional answer transport', () => {
  it('replaces snapshots, ignores older revisions, and keeps lifecycle IDs independent', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        response(
          status(1, 'queued') +
            status(2, 'running') +
            preview(3, 'Draft') +
            preview(2, 'Old') +
            preview(4, 'Draft grows') +
            status(3, 'completed') +
            preview(4, '') +
            end,
        ),
      );
    vi.stubGlobal('fetch', fetcher);
    const events = vi.fn();
    const drafts = vi.fn();
    await consumeEvents(
      'r1',
      0,
      events,
      new AbortController().signal,
      undefined,
      drafts,
    );
    expect(events).toHaveBeenCalledTimes(3);
    expect(drafts.mock.calls.map((call) => call[0].text)).toEqual([
      'Draft',
      'Draft grows',
      '',
    ]);
    expect(fetcher.mock.calls[0][0]).toContain('?preview=true');
  });
  it.each([preview(1, 'wrong owner', 'other'), preview(1, 'x'.repeat(16001))])(
    'rejects invalid preview payloads',
    async (text) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(text)));
      await expect(
        consumeEvents(
          'r1',
          0,
          vi.fn(),
          new AbortController().signal,
          undefined,
          vi.fn(),
        ),
      ).rejects.toThrow();
    },
  );
});

describe('provisional answer UI', () => {
  it.each(['completed', 'failed', 'cancelled'])(
    'renders escaped text without source links, then clears it on %s',
    async (terminal) => {
      let push: ReadableStreamDefaultController<Uint8Array> | undefined;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          push = controller;
        },
      });
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          new Response(body, {
            headers: { 'Content-Type': 'text/event-stream' },
          }),
        ),
      );
      const changed = vi.fn();
      const { container } = render(
        <RunTimeline
          runId="r1"
          runStatus="running"
          onChanged={changed}
          onExpired={vi.fn()}
        />,
      );
      await act(async () => {
        push?.enqueue(
          encoder.encode(
            status(1, 'queued') +
              status(2, 'running') +
              preview(1, '<img src=x onerror=alert(1)> draft'),
          ),
        );
      });
      expect(
        await screen.findByRole('heading', {
          name: 'Draft — not yet validated',
        }),
      ).toBeInTheDocument();
      expect(
        screen.getByLabelText('Provisional answer text'),
      ).toHaveTextContent('<img src=x onerror=alert(1)> draft');
      expect(container.querySelector('img')).toBeNull();
      expect(screen.queryByRole('link')).toBeNull();
      expect(changed).toHaveBeenCalledTimes(2); // Preview writes do not trigger repeated REST refreshes.
      await act(async () => {
        push?.enqueue(
          encoder.encode(status(3, terminal) + preview(1, '') + end),
        );
      });
      expect(await screen.findByText('Timeline complete.')).toBeInTheDocument();
      expect(screen.queryByLabelText('Provisional answer text')).toBeNull();
    },
  );
  it('hides a stale preview when polling discovers failure even if SSE is stalled', async () => {
    let push: ReadableStreamDefaultController<Uint8Array> | undefined;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        push = controller;
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(body, {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
    );
    const changed = vi.fn(),
      expired = vi.fn();
    const { rerender, unmount } = render(
      <RunTimeline
        runId="r1"
        runStatus="running"
        onChanged={changed}
        onExpired={expired}
      />,
    );
    await act(async () => {
      push?.enqueue(encoder.encode(preview(1, 'stale draft')));
    });
    expect(await screen.findByText('stale draft')).toBeInTheDocument();
    rerender(
      <RunTimeline
        runId="r1"
        runStatus="failed"
        onChanged={changed}
        onExpired={expired}
      />,
    );
    expect(screen.queryByLabelText('Provisional answer text')).toBeNull();
    unmount();
    push?.close();
  });
});
