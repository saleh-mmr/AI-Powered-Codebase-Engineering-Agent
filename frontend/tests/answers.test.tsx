import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GroundedAnswer } from '../src/features/answers/GroundedAnswer';
import { answerSchema } from '../src/features/answers/api';
import { AnswerPanel } from '../src/features/answers/AnswerPanel';
const settings = {
  enabled: true,
  embeddings_enabled: false,
  model: 'test-model',
  max_output_tokens: 1200,
  input_price_per_million: 0.4,
  output_price_per_million: 1.6,
};
const answer = {
  answer_id: 'answer-1',
  status: 'answered',
  claims: [{ text: 'It prints hello.', citation_ids: ['C1'] }],
  limitation: '',
  evidence: [
    {
      citation_id: 'C1',
      chunk_id: 'chunk',
      path: 'app.py',
      commit_sha: 'a'.repeat(40),
      start_line: 1,
      end_line: 1,
      content: '<script>untrusted</script>',
    },
  ],
  commit_sha: 'a'.repeat(40),
  retrieval_mode: 'keyword',
  prompt_version: 'grounded-v1',
  model: 'test-model',
  input_tokens: 100,
  output_tokens: 40,
  estimated_generation_cost_usd: 0.000104,
  estimated_retrieval_cost_usd: 0,
  context_tokens: 80,
  context_omitted: 0,
  duration_ms: 1200,
};
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}
async function ask() {
  await screen.findByText(/test-model: estimated/);
  fireEvent.change(screen.getByLabelText('Question about the code'), {
    target: { value: 'What does hello do?' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Ask with sources' }));
}
describe('grounded answer panel', () => {
  it('submits CSRF and renders working source anchors without executing HTML', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, opts?: RequestInit) => {
        if (opts?.method === 'POST') {
          expect(opts.headers).toMatchObject({ 'X-CSRF-Token': 'proof' });
          expect(JSON.parse(String(opts.body))).toEqual({
            question: 'What does hello do?',
            mode: 'keyword',
          });
          return Promise.resolve(json(answer));
        }
        return Promise.resolve(json(settings));
      }),
    );
    const { container } = render(
      <AnswerPanel repositoryId="r" csrf="proof" onExpired={() => {}} />,
    );
    await ask();
    expect(await screen.findByText('It prints hello.')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'C1' });
    expect(link).toHaveAttribute('href', '#answer-answer-1-C1');
    expect(container.querySelector('#answer-answer-1-C1')).not.toBeNull();
    expect(screen.getByText('<script>untrusted</script>')).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    expect(
      screen.getByText(/Question: What does hello do/),
    ).toBeInTheDocument();
  });
  it('keeps disabled configuration usable without a model key', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(json({ ...settings, enabled: false })),
    );
    render(<AnswerPanel repositoryId="r" csrf="p" onExpired={() => {}} />);
    await screen.findByText(/AI answers are disabled/);
    expect(
      screen.getByRole('button', { name: 'Ask with sources' }),
    ).toBeDisabled();
  });
  it('shows loading, prevents repeated submission, and handles empty evidence', async () => {
    let resolve: ((value: Response) => void) | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, opts?: RequestInit) =>
        opts?.method === 'POST'
          ? new Promise<Response>((done) => {
              resolve = done;
            })
          : Promise.resolve(json(settings)),
      ),
    );
    render(<AnswerPanel repositoryId="r" csrf="p" onExpired={() => {}} />);
    await ask();
    expect(
      screen.getByRole('button', { name: 'Generating answer…' }),
    ).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Retrieving evidence');
    resolve?.(
      json({
        ...answer,
        status: 'insufficient_evidence',
        claims: [],
        evidence: [],
        model: null,
        limitation: 'No source evidence was retrieved.',
      }),
    );
    expect(await screen.findByText('Not enough evidence')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'C1' })).toBeNull();
  });
  it('shows provider errors and handles expired sessions', async () => {
    let status = 503;
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation((_url: string, opts?: RequestInit) =>
          Promise.resolve(
            opts?.method === 'POST'
              ? json({ error: { message: 'Provider unavailable.' } }, status)
              : json(settings),
          ),
        ),
    );
    const expired = vi.fn();
    render(<AnswerPanel repositoryId="r" csrf="p" onExpired={expired} />);
    await ask();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Provider unavailable.',
    );
    status = 401;
    fireEvent.click(screen.getByRole('button', { name: 'Ask with sources' }));
    await waitFor(() => expect(expired).toHaveBeenCalledOnce());
  });
  it('recovers from a settings failure and surfaces refusal', async () => {
    let fail = true;
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((_url: string, opts?: RequestInit) =>
        Promise.resolve(
          opts?.method === 'POST'
            ? json({
                ...answer,
                status: 'refused',
                claims: [],
                limitation: 'The model declined this request.',
              })
            : fail
              ? json({}, 503)
              : json(settings),
        ),
      ),
    );
    render(<AnswerPanel repositoryId="r" csrf="p" onExpired={() => {}} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load answer settings',
    );
    fail = false;
    fireEvent.click(
      screen.getByRole('button', { name: 'Refresh answer settings' }),
    );
    await ask();
    expect(await screen.findByText('Request declined')).toBeInTheDocument();
  });
});

describe('conversation context provenance', () => {
  it('displays included history and safely reads answers saved before 7C1', () => {
    const { rerender } = render(
      <GroundedAnswer answer={answerSchema.parse(answer)} />,
    );
    expect(
      screen.getByText(/Conversation context: 0 prior turns/),
    ).toBeInTheDocument();
    rerender(
      <GroundedAnswer
        answer={answerSchema.parse({
          ...answer,
          history_turn_ids: ['previous-turn'],
          history_tokens: 64,
          history_policy: 'recent-pairs-v1',
        })}
      />,
    );
    expect(
      screen.getByText(/Conversation context: 1 prior turns/),
    ).toHaveTextContent('64 estimated history tokens');
    expect(
      screen.getByText(/Earlier answers are not citation evidence/),
    ).toBeInTheDocument();
  });
});
