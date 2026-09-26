import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RunUsage } from '../src/features/runs/RunUsage';

function respond(value: unknown) {
  return new Response(JSON.stringify(value), {
    headers: { 'Content-Type': 'application/json' },
  });
}
describe('call receipts', () => {
  it('loads on demand and distinguishes unknown charges from the known subtotal', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      respond({
        tracked: true,
        known_cost_usd: '0',
        unknown_calls: 1,
        items: [
          {
            id: 'receipt',
            kind: 'generation',
            model: 'test',
            input_rate: '0.4',
            output_rate: '1.6',
            input_tokens: null,
            output_tokens: null,
            estimated_cost_usd: null,
            started_at: '2026-09-26',
            finished_at: null,
          },
        ],
      }),
    );
    vi.stubGlobal('fetch', fetcher);
    render(<RunUsage runId="r1" onExpired={vi.fn()} />);
    expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole('button', { name: 'Call usage receipts' }),
    );
    expect(await screen.findByText(/Unknown calls: 1/)).toBeInTheDocument();
    expect(
      screen.getByText(/Usage unknown; charges may have occurred/),
    ).toBeInTheDocument();
    expect(fetcher.mock.calls[0][0]).toContain('/answer-runs/r1/usage');
  });
  it('labels legacy runs rather than inventing a zero bill', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        respond({
          tracked: false,
          known_cost_usd: '0',
          unknown_calls: 0,
          items: [],
        }),
      ),
    );
    render(<RunUsage runId="old" onExpired={vi.fn()} />);
    fireEvent.click(
      screen.getByRole('button', { name: 'Call usage receipts' }),
    );
    expect(
      await screen.findByText(/older run has no per-call tracking/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Known subtotal/)).not.toBeInTheDocument();
  });
  it('recovers from request failure without showing stale amounts', async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue(
        respond({
          tracked: true,
          known_cost_usd: '0',
          unknown_calls: 0,
          items: [],
        }),
      );
    vi.stubGlobal('fetch', fetcher);
    render(<RunUsage runId="r1" onExpired={vi.fn()} />);
    fireEvent.click(
      screen.getByRole('button', { name: 'Call usage receipts' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load receipts',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Refresh receipts' }));
    expect(
      await screen.findByText(/No provider attempts recorded yet/),
    ).toBeInTheDocument();
  });
});
