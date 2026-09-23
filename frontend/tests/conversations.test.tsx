import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ConversationWorkspace } from '../src/features/conversations/ConversationWorkspace';
import { ConversationTranscript } from '../src/features/conversations/ConversationTranscript';
const settings = {
  enabled: true,
  embeddings_enabled: false,
  model: 'test',
  max_output_tokens: 1200,
  input_price_per_million: 0.4,
  output_price_per_million: 1.6,
};
const conversation = {
  id: 'c1',
  repository_id: 'r',
  title: 'Authentication',
  message_count: 0,
  created_at: '2026-09-23',
  updated_at: '2026-09-23',
};
const answer = {
  answer_id: 'a1',
  status: 'answered',
  claims: [{ text: 'It returns True.', citation_ids: ['C1'] }],
  limitation: '',
  evidence: [
    {
      citation_id: 'C1',
      chunk_id: 'ch',
      path: 'auth.py',
      commit_sha: 'a'.repeat(40),
      start_line: 1,
      end_line: 1,
      content: 'return True',
    },
  ],
  commit_sha: 'a'.repeat(40),
  retrieval_mode: 'keyword',
  prompt_version: 'grounded-v1',
  model: 'test',
  input_tokens: 100,
  output_tokens: 30,
  estimated_generation_cost_usd: 0.0001,
  estimated_retrieval_cost_usd: 0,
  context_tokens: 80,
  context_omitted: 0,
  duration_ms: 10,
};
const pair = [
  {
    id: 'm1',
    turn_id: 'a1',
    position: 1,
    role: 'user',
    content: 'What does check do?',
    token_count: null,
    answer: null,
    created_at: '2026-09-23',
  },
  {
    id: 'm2',
    turn_id: 'a1',
    position: 2,
    role: 'assistant',
    content: 'It returns True.',
    token_count: 30,
    answer,
    created_at: '2026-09-23',
  },
];
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
const expired = () => {};
describe('saved conversation UI', () => {
  it('creates, saves, and reopens an answer after remount without another paid request', async () => {
    let created = false,
      saved = false,
      calls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string, options?: RequestInit) => {
        if (path.endsWith('/answers')) return Promise.resolve(json(settings));
        if (path.endsWith('/conversations') && options?.method === 'POST') {
          expect(options.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          expect(JSON.parse(String(options.body))).toEqual({
            title: 'Authentication',
          });
          created = true;
          return Promise.resolve(json(conversation, 201));
        }
        if (path.endsWith('/messages') && options?.method === 'POST') {
          expect(path).toBe('/api/conversations/c1/messages');
          expect(JSON.parse(String(options.body))).toEqual({
            question: 'What does check do?',
            mode: 'keyword',
          });
          saved = true;
          calls++;
          return Promise.resolve(json(answer, 201));
        }
        if (path.endsWith('/messages'))
          return Promise.resolve(
            json({ items: saved ? pair : [], next_before: null }),
          );
        return Promise.resolve(
          json({
            items: created
              ? [{ ...conversation, message_count: saved ? 2 : 0 }]
              : [],
          }),
        );
      }),
    );
    const first = render(
      <ConversationWorkspace
        repositoryId="r"
        csrf="proof"
        onExpired={expired}
      />,
    );
    await screen.findByText(
      'No conversations yet. Create one to keep your answers.',
    );
    fireEvent.change(screen.getByLabelText('Conversation title'), {
      target: { value: 'Authentication' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Create conversation' }),
    );
    await screen.findByText(
      'No saved messages yet. Ask your first question below.',
    );
    await screen.findByText(/test: estimated/);
    fireEvent.change(screen.getByLabelText('Question about the code'), {
      target: { value: 'What does check do?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask with sources' }));
    expect(
      await screen.findByText(
        'Answer saved. You can reopen it in this conversation.',
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText('It returns True.')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'C1' })).toHaveLength(1);
    first.unmount();
    render(
      <ConversationWorkspace
        repositoryId="r"
        csrf="proof"
        onExpired={expired}
      />,
    );
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Authentication · 1 saved answers',
      }),
    );
    expect(await screen.findByText('It returns True.')).toBeInTheDocument();
    expect(calls).toBe(1);
  });
  it('requires explicit deletion confirmation and keeps the temporary question available', async () => {
    let removed = false;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string, options?: RequestInit) => {
        if (options?.method === 'DELETE') {
          expect(options.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          removed = true;
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        return Promise.resolve(
          json(
            path.endsWith('/answers')
              ? settings
              : path.endsWith('/messages')
                ? { items: [], next_before: null }
                : { items: removed ? [] : [conversation] },
          ),
        );
      }),
    );
    render(
      <ConversationWorkspace
        repositoryId="r"
        csrf="proof"
        onExpired={expired}
      />,
    );
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Authentication · 0 saved answers',
      }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Delete conversation' }),
    );
    expect(removed).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Keep conversation' }));
    expect(
      screen.queryByRole('button', { name: 'Confirm deletion' }),
    ).toBeNull();
    fireEvent.click(
      screen.getByRole('button', { name: 'Delete conversation' }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }));
    await screen.findByText(
      'No conversations yet. Create one to keep your answers.',
    );
    expect(
      screen.getByRole('button', { name: 'Temporary question' }),
    ).toHaveAttribute('aria-pressed', 'true');
  });
  it('paginates history and retries failed reads without resubmitting a question', async () => {
    let fail = true;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((path: string, options?: RequestInit) => {
        expect(options?.method).toBeUndefined();
        if (fail) return Promise.resolve(json({}, 503));
        const older = path.includes('?before=3');
        return Promise.resolve(
          json({
            items: older
              ? pair
              : [
                  {
                    ...pair[0],
                    id: 'm3',
                    position: 3,
                    content: 'A newer question',
                  },
                ],
            next_before: older ? null : 3,
          }),
        );
      }),
    );
    render(<ConversationTranscript conversationId="c1" onExpired={expired} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'do not resubmit your question',
    );
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry history' }));
    expect(
      await screen.findByText('Question: A newer question'),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Load older messages' }),
    );
    expect(await screen.findByText('It returns True.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Load older messages' }),
    ).toBeNull();
  });
  it('handles expired sessions without showing another user history', async () => {
    const onExpired = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(json({ error: { message: 'Sign in.' } }, 401)),
    );
    render(
      <ConversationWorkspace
        repositoryId="r"
        csrf="proof"
        onExpired={onExpired}
      />,
    );
    await waitFor(() => expect(onExpired).toHaveBeenCalled());
    expect(screen.queryByText('Authentication')).toBeNull();
  });
});
