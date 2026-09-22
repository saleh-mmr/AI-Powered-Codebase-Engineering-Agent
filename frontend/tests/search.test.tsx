import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RepositorySearch } from '../src/features/search/RepositorySearch';
const job = {
  id: 'j',
  status: 'completed',
  stage: 'completed',
  mode: 'keyword',
  documents_stored: 1,
  reserved_tokens: 0,
  input_tokens: 0,
  token_budget: 200000,
  price_per_million: 0,
  error_message: null,
};
const state = {
  enabled_semantic: false,
  latest: job,
  keyword: job,
  hybrid: null,
};
const result = {
  commit_sha: 'a'.repeat(40),
  mode: 'keyword',
  pipeline_version: 'hybrid-v1',
  provider_profile: 'none',
  duration_ms: 12,
  context_tokens: 80,
  context_omitted: 0,
  query_tokens: 0,
  estimated_query_cost_usd: 0,
  results: [
    {
      chunk_id: 'c',
      path: 'auth.py',
      symbol: 'verify_token',
      start_line: 2,
      end_line: 4,
      content: '<script>untrusted</script>',
      score: 0.02,
      channel_ranks: { lexical: 1, symbol: 1 },
    },
  ],
  context: [{ citation_id: 'C1', chunk_id: 'c' }],
};
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
describe('retrieval inspection', () => {
  it('submits an authorized query and shows escaped provenance and channel ranks', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, options?: RequestInit) => {
        if (url.endsWith('/query')) {
          expect(options?.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          expect(JSON.parse(String(options?.body)).query).toBe('verify_token');
          return Promise.resolve(json(result));
        }
        return Promise.resolve(json(state));
      }),
    );
    const { container } = render(
      <RepositorySearch
        repositoryId="repo"
        csrf="proof"
        onExpired={() => {}}
      />,
    );
    await screen.findByText(
      'Search preparation (keyword): completed · 1 chunks stored',
    );
    fireEvent.change(screen.getByLabelText('Question or symbol'), {
      target: { value: 'verify_token' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search code' }));
    expect(await screen.findByText('auth.py · L2–4 · C1')).toBeInTheDocument();
    expect(screen.getByText('<script>untrusted</script>')).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    expect(screen.getByText(/lexical #1 · symbol #1/)).toBeInTheDocument();
  });
  it('queues the free mode and clearly separates semantic configuration', async () => {
    let created = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string, options?: RequestInit) => {
        if (url.endsWith('/prepare')) {
          expect(JSON.parse(String(options?.body))).toEqual({
            mode: 'keyword',
          });
          created = true;
          return Promise.resolve(json({ ...job, status: 'queued' }, 202));
        }
        return Promise.resolve(
          json({
            ...state,
            keyword: null,
            latest: created ? { ...job, status: 'queued' } : null,
          }),
        );
      }),
    );
    render(
      <RepositorySearch
        repositoryId="repo"
        csrf="proof"
        onExpired={() => {}}
      />,
    );
    await screen.findByText(
      'Prepare the selected search mode after building the source index.',
    );
    expect(
      screen.getByRole('option', {
        name: 'Hybrid + semantic (external embedding API)',
      }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole('button', { name: 'Prepare selected search' }),
    );
    expect(
      await screen.findByRole('button', { name: 'Cancel search preparation' }),
    ).toBeInTheDocument();
  });
  it('shows empty results and provider errors without inventing answers', async () => {
    let fail = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve(
          url.endsWith('/query')
            ? fail
              ? json(
                  {
                    error: { message: 'Embedding provider is unavailable.' },
                  },
                  503,
                )
              : json({ ...result, results: [], context: [] })
            : json(state),
        ),
      ),
    );
    render(
      <RepositorySearch
        repositoryId="repo"
        csrf="proof"
        onExpired={() => {}}
      />,
    );
    await screen.findByText(
      'Search preparation (keyword): completed · 1 chunks stored',
    );
    fireEvent.change(screen.getByLabelText('Question or symbol'), {
      target: { value: 'unknown' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search code' }));
    expect(
      await screen.findByText(/No matching code found/),
    ).toBeInTheDocument();
    fail = true;
    fireEvent.click(screen.getByRole('button', { name: 'Search code' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Embedding provider is unavailable.',
    );
  });
});
