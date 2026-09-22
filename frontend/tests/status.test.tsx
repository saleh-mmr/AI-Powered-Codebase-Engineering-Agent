import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SystemStatus } from '../src/features/system/SystemStatus';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('backend readiness', () => {
  it('shows loading, then a real successful response', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ status: 'ok', service: 'repopilot-api' }),
        ),
    );
    render(<SystemStatus />);
    expect(screen.getByRole('button')).toBeDisabled();
    expect(await screen.findByText(/All checks passed/)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeEnabled();
  });
  it('shows a safe dependency error and lets the user retry', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(
        jsonResponse({ status: 'ok', service: 'repopilot-api' }),
      );
    vi.stubGlobal('fetch', fetcher);
    render(<SystemStatus />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'database is not ready',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Check connection' }));
    expect(await screen.findByText(/All checks passed/)).toBeInTheDocument();
  });
  it('rejects a malformed success response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ status: 'ready' })),
    );
    render(<SystemStatus />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'unexpected health response',
    );
  });
  it('handles a network failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    );
    render(<SystemStatus />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Failed to fetch',
    );
  });
});
