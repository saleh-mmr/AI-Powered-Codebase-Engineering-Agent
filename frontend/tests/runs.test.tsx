import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RunComposer } from '../src/features/runs/RunComposer';
const settings = {
  enabled: true,
  embeddings_enabled: false,
  model: 'test',
  max_output_tokens: 1200,
  input_price_per_million: 0.4,
  output_price_per_million: 1.6,
};
const run = {
  id: 'r1',
  conversation_id: 'c1',
  request_key: 'key',
  question: 'How does check work?',
  mode: 'keyword',
  status: 'queued',
  model: 'test',
  source_index_id: 'source',
  usage_state: 'not_started',
  input_tokens: null,
  output_tokens: null,
  estimated_cost_usd: null,
  error_code: null,
  error_message: null,
  created_at: '2026-09-23',
  started_at: null,
  finished_at: null,
};
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
const noop = () => {};
describe('durable answer UI', () => {
  it('recovers an active run from the server and cancels it without resubmission', async () => {
    let cancelled = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string, options?: RequestInit) => {
        if (path.endsWith('/cancel')) {
          expect(options?.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          cancelled = true;
          return Promise.resolve(json({ ...run, status: 'cancelled' }));
        }
        expect(options?.method).toBeUndefined();
        return Promise.resolve(
          json(
            path.endsWith('/answers')
              ? settings
              : {
                  items: [
                    { ...run, status: cancelled ? 'cancelled' : 'queued' },
                  ],
                },
          ),
        );
      }),
    );
    render(
      <RunComposer
        repositoryId="repo"
        conversationId="c1"
        csrf="proof"
        onExpired={noop}
        onCompleted={noop}
      />,
    );
    expect(
      await screen.findByText(/An answer is queued or running/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Queue answer' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel answer' }));
    expect(await screen.findByText('cancelled')).toBeInTheDocument();
  });
  it('reuses the exact idempotency key after an uncertain submission', async () => {
    const bodies: unknown[] = [];
    let accepted = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string, options?: RequestInit) => {
        if (options?.method === 'POST') {
          bodies.push(JSON.parse(String(options.body)));
          if (bodies.length === 1)
            return Promise.reject(new TypeError('Connection lost'));
          accepted = true;
          return Promise.resolve(json(run, 202));
        }
        return Promise.resolve(
          json(
            path.endsWith('/answers')
              ? settings
              : { items: accepted ? [run] : [] },
          ),
        );
      }),
    );
    render(
      <RunComposer
        repositoryId="repo"
        conversationId="c1"
        csrf="proof"
        onExpired={noop}
        onCompleted={noop}
      />,
    );
    await screen.findByText('No answer runs yet.');
    fireEvent.change(screen.getByLabelText('Question about the code'), {
      target: { value: 'How does check work?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Queue answer' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Submission status is uncertain',
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Retry same submission' }),
    );
    await screen.findByText(/An answer is queued or running/);
    expect(bodies).toHaveLength(2);
    expect(bodies[0]).toEqual(bodies[1]);
  });
  it('distinguishes failed unknown usage from recorded completion and refreshes history once', async () => {
    let complete = false;
    const done = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string) =>
        Promise.resolve(
          json(
            path.endsWith('/answers')
              ? settings
              : {
                  items: [
                    complete
                      ? {
                          ...run,
                          status: 'completed',
                          usage_state: 'recorded',
                          input_tokens: 100,
                          output_tokens: 30,
                          estimated_cost_usd: 0.0001,
                        }
                      : {
                          ...run,
                          status: 'failed',
                          usage_state: 'unknown',
                          error_code: 'answer_worker_lost',
                          error_message: 'Worker stopped; no automatic retry.',
                        },
                  ],
                },
          ),
        ),
      ),
    );
    render(
      <RunComposer
        repositoryId="repo"
        conversationId="c1"
        csrf="proof"
        onExpired={noop}
        onCompleted={done}
      />,
    );
    expect(
      await screen.findByText(/Usage is not confirmed/),
    ).toBeInTheDocument();
    expect(done).not.toHaveBeenCalled();
    complete = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh run status' }));
    await waitFor(() => expect(done).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole('button', { name: 'Refresh run status' }));
    await screen.findByText(/100 input/);
    expect(done).toHaveBeenCalledOnce();
  });
});
